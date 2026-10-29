from decimal import Decimal

from django.test import SimpleTestCase

from activos.models import EstadoActivo
from ordenes_trabajo.models import OrdenRepuesto
from ordenes_trabajo.services import crear_orden_trabajo, iniciar_reparacion
from repuestos.models import MovimientoRepuesto, Repuesto
from tickets.tests.test_estados_tickets import EstadoFixture
from usuarios.models import BitacoraAuditoria
from usuarios.tests.test_integracion_postgresql import PostgreSQLTestBase

from .serializers import (
    AnularAsignacionRepuestoOTSerializer,
    AsignarRepuestoOTSerializer,
)


class AsignarRepuestoOTSerializerTests(SimpleTestCase):
    def setUp(self):
        self.datos_validos = {
            "id_repuesto": 1,
            "cantidad": 2,
        }

    def test_asignacion_valida(self):
        serializer = AsignarRepuestoOTSerializer(data=self.datos_validos)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_repuesto_obligatorio(self):
        datos = self.datos_validos.copy()
        datos.pop("id_repuesto")

        serializer = AsignarRepuestoOTSerializer(data=datos)

        self.assertFalse(serializer.is_valid())
        self.assertIn("id_repuesto", serializer.errors)

    def test_cantidad_obligatoria(self):
        datos = self.datos_validos.copy()
        datos.pop("cantidad")

        serializer = AsignarRepuestoOTSerializer(data=datos)

        self.assertFalse(serializer.is_valid())
        self.assertIn("cantidad", serializer.errors)

    def test_cantidad_cero(self):
        datos = {**self.datos_validos, "cantidad": 0}

        serializer = AsignarRepuestoOTSerializer(data=datos)

        self.assertFalse(serializer.is_valid())

    def test_cantidad_negativa(self):
        datos = {**self.datos_validos, "cantidad": -2}

        serializer = AsignarRepuestoOTSerializer(data=datos)

        self.assertFalse(serializer.is_valid())


class AnularAsignacionRepuestoOTSerializerTests(SimpleTestCase):
    def test_motivo_valido(self):
        serializer = AnularAsignacionRepuestoOTSerializer(data={"motivo": "Repuesto no utilizado"})
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_motivo_obligatorio(self):
        serializer = AnularAsignacionRepuestoOTSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn("motivo", serializer.errors)

    def test_motivo_vacio(self):
        serializer = AnularAsignacionRepuestoOTSerializer(data={"motivo": ""})
        self.assertFalse(serializer.is_valid())


class AsignacionRepuestosPostgreSQLTests(PostgreSQLTestBase):
    def test_rbac_solo_tecnico_puede_asignar(self):
        url = "/api/ordenes-trabajo/1/repuestos/"
        datos = {
            "id_repuesto": 1,
            "cantidad": 2,
        }

        for usuario in (self.admin, self.solicitante):
            respuesta = self.cliente(usuario).post(
                url,
                datos,
                format="json",
            )

            self.assertEqual(
                respuesta.status_code,
                403,
                respuesta.data,
            )

    def test_rbac_solo_tecnico_puede_anular(self):
        url = "/api/ordenes-trabajo/1/repuestos/1/anular/"
        datos = {
            "motivo": "Prueba de autorización",
        }

        for usuario in (self.admin, self.solicitante):
            respuesta = self.cliente(usuario).post(
                url,
                datos,
                format="json",
            )

            self.assertEqual(
                respuesta.status_code,
                403,
                respuesta.data,
            )


class AsignacionRepuestosIntegracionTests(EstadoFixture):
    def setUp(self):
        super().setUp()

        activo = self.activo()
        activo.id_estado_activo = EstadoActivo.objects.get(nombre="En revisión")
        activo.save(update_fields=["id_estado_activo"])

        self.ticket.id_activo = activo
        self.ticket.save(update_fields=["id_activo"])

        self.orden = crear_orden_trabajo(
            self.ticket.pk,
            self.tecnico,
            "Falla de memoria",
            "Revisión inicial",
        )

        iniciar_reparacion(self.orden.pk, self.tecnico)

        self.repuesto = Repuesto.objects.create(
            codigo_repuesto="REP-PRUEBA-OT",
            nombre="Memoria RAM de prueba",
            stock_actual=5,
            precio_unitario=Decimal("15000.00"),
        )

        self.url = f"/api/ordenes-trabajo/{self.orden.pk}/repuestos/"

    def asignar(self, cantidad=2):
        return self.cliente(self.tecnico).post(
            self.url,
            {
                "id_repuesto": self.repuesto.pk,
                "cantidad": cantidad,
            },
            format="json",
        )

    def test_asignacion_descuenta_stock_y_registra_movimiento(self):
        respuesta = self.asignar()

        self.assertEqual(respuesta.status_code, 201, respuesta.data)

        self.repuesto.refresh_from_db()
        self.assertEqual(self.repuesto.stock_actual, 3)

        asignacion = OrdenRepuesto.objects.get(id_orden=self.orden)
        self.assertEqual(asignacion.cantidad, 2)
        self.assertFalse(asignacion.anulado)

        self.assertTrue(
            MovimientoRepuesto.objects.filter(
                repuesto=self.repuesto,
                tipo_movimiento="SALIDA_TALLER",
                cantidad=2,
            ).exists()
        )

        self.assertTrue(BitacoraAuditoria.objects.filter(accion="REPUESTO_ASIGNADO").exists())

    def test_stock_insuficiente_no_modifica_inventario(self):
        respuesta = self.asignar(cantidad=6)

        self.assertEqual(respuesta.status_code, 400, respuesta.data)

        self.repuesto.refresh_from_db()
        self.assertEqual(self.repuesto.stock_actual, 5)
        self.assertFalse(OrdenRepuesto.objects.exists())

    def test_anulacion_reintegra_stock(self):
        asignacion_respuesta = self.asignar()
        self.assertEqual(
            asignacion_respuesta.status_code,
            201,
            asignacion_respuesta.data,
        )

        asignacion_id = asignacion_respuesta.data["id_orden_repuesto"]

        respuesta = self.cliente(self.tecnico).post(
            f"{self.url}{asignacion_id}/anular/",
            {"motivo": "Repuesto no utilizado"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)

        self.repuesto.refresh_from_db()
        self.assertEqual(self.repuesto.stock_actual, 5)

        asignacion = OrdenRepuesto.objects.get(pk=asignacion_id)
        self.assertTrue(asignacion.anulado)
        self.assertEqual(
            asignacion.motivo_anulacion,
            "Repuesto no utilizado",
        )

        self.assertTrue(
            MovimientoRepuesto.objects.filter(
                repuesto=self.repuesto,
                tipo_movimiento="DEVOLUCION_TALLER",
                cantidad=2,
            ).exists()
        )

    def test_anulacion_duplicada_no_reintegra_dos_veces(self):
        asignacion_respuesta = self.asignar()
        self.assertEqual(
            asignacion_respuesta.status_code,
            201,
            asignacion_respuesta.data,
        )

        asignacion_id = asignacion_respuesta.data["id_orden_repuesto"]
        url_anulacion = f"{self.url}{asignacion_id}/anular/"
        cliente = self.cliente(self.tecnico)

        primera = cliente.post(
            url_anulacion,
            {"motivo": "Repuesto no utilizado"},
            format="json",
        )
        self.assertEqual(primera.status_code, 200, primera.data)

        segunda = cliente.post(
            url_anulacion,
            {"motivo": "Segunda anulación"},
            format="json",
        )
        self.assertEqual(segunda.status_code, 400, segunda.data)

        self.repuesto.refresh_from_db()
        self.assertEqual(self.repuesto.stock_actual, 5)

        self.assertEqual(
            MovimientoRepuesto.objects.filter(tipo_movimiento="DEVOLUCION_TALLER").count(),
            1,
        )

    def test_consulta_excluye_anulados_del_costo(self):
        respuesta = self.asignar()
        self.assertEqual(respuesta.status_code, 201, respuesta.data)

        consulta = self.cliente(self.tecnico).get(self.url)
        self.assertEqual(consulta.status_code, 200, consulta.data)
        self.assertEqual(
            Decimal(consulta.data["resumen"]["costo_total_repuestos"]),
            Decimal("30000.00"),
        )

        asignacion_id = respuesta.data["id_orden_repuesto"]

        anulacion = self.cliente(self.tecnico).post(
            f"{self.url}{asignacion_id}/anular/",
            {"motivo": "Repuesto no utilizado"},
            format="json",
        )
        self.assertEqual(anulacion.status_code, 200, anulacion.data)

        consulta = self.cliente(self.tecnico).get(self.url)
        self.assertEqual(consulta.status_code, 200, consulta.data)
        self.assertEqual(
            Decimal(consulta.data["resumen"]["costo_total_repuestos"]),
            Decimal("0.00"),
        )
        self.assertTrue(consulta.data["repuestos"][0]["anulado"])

    def test_reintegro_recalcula_costo_promedio_despues_de_una_compra(self):
        from repuestos.services import registrar_ingreso_repuesto

        asignacion = self.asignar().data["id_orden_repuesto"]
        registrar_ingreso_repuesto({"id_repuesto": self.repuesto.pk, "cantidad": 2, "costo_unitario": Decimal("25000.00")}, self.admin)
        respuesta = self.cliente(self.tecnico).post(
            f"{self.url}{asignacion}/anular/", {"motivo": "Pieza no utilizada"}, format="json"
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.repuesto.refresh_from_db()
        self.assertEqual(self.repuesto.stock_actual, 7)
        self.assertEqual(self.repuesto.precio_unitario, Decimal("17857.14"))

    def test_costo_historico_conserva_centavos_tras_cambiar_precio_del_catalogo(self):
        self.repuesto.precio_unitario = Decimal("15000.51")
        self.repuesto.save(update_fields=["precio_unitario"])
        self.asignar(cantidad=3)
        self.repuesto.precio_unitario = Decimal("20000.99")
        self.repuesto.save(update_fields=["precio_unitario"])
        respuesta = self.cliente(self.tecnico).get(self.url)
        self.assertEqual(respuesta.data["resumen"]["costo_total_repuestos"], "45001.53")
        self.assertEqual(respuesta.data["repuestos"][0]["costo_unitario"], "15000.51")

    def test_reintegro_fuera_del_limite_no_modifica_asignacion_ni_stock(self):
        asignacion = self.asignar().data["id_orden_repuesto"]
        self.repuesto.stock_actual = 2147483647
        self.repuesto.save(update_fields=["stock_actual"])
        respuesta = self.cliente(self.tecnico).post(
            f"{self.url}{asignacion}/anular/", {"motivo": "Pieza no utilizada"}, format="json"
        )
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.repuesto.refresh_from_db()
        self.assertEqual(self.repuesto.stock_actual, 2147483647)
        self.assertFalse(OrdenRepuesto.objects.get(pk=asignacion).anulado)
        self.assertFalse(MovimientoRepuesto.objects.filter(tipo_movimiento="DEVOLUCION_TALLER").exists())

    def test_cantidades_invalidas_no_generan_movimientos(self):
        for cantidad in [True, False, 1.5, "1.0", "-1", "٢", 2147483648, {}, []]:
            with self.subTest(cantidad=cantidad):
                respuesta = self.asignar(cantidad)
                self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.repuesto.refresh_from_db()
        self.assertEqual(self.repuesto.stock_actual, 5)
        self.assertFalse(OrdenRepuesto.objects.exists())

    def test_repuesto_inactivo_y_orden_fuera_de_reparacion_no_consumen(self):
        from .models import EstadoOrdenTrabajo

        self.repuesto.activo = False
        self.repuesto.save(update_fields=["activo"])
        self.assertEqual(self.asignar().status_code, 400)
        self.repuesto.activo = True
        self.repuesto.save(update_fields=["activo"])
        for estado in ["En Diagnóstico", "Pausada", "Completada"]:
            self.orden.id_estado_ot = EstadoOrdenTrabajo.objects.get(nombre=estado)
            self.orden.save(update_fields=["id_estado_ot"])
            self.assertEqual(self.asignar().status_code, 400)
        self.assertFalse(OrdenRepuesto.objects.exists())

    def test_dos_consumos_concurrentes_no_superan_el_stock(self):
        resultados = self.competir(lambda _: self.asignar(cantidad=4).status_code)
        self.assertEqual(sorted(resultados), [201, 400])
        self.repuesto.refresh_from_db()
        self.assertEqual(self.repuesto.stock_actual, 1)
        self.assertEqual(OrdenRepuesto.objects.count(), 1)

    def test_dos_anulaciones_concurrentes_reintegran_una_sola_vez(self):
        asignacion = self.asignar().data["id_orden_repuesto"]
        url = f"{self.url}{asignacion}/anular/"
        resultados = self.competir(lambda _: self.cliente(self.tecnico).post(url, {"motivo": "Pieza no utilizada"}, format="json").status_code)
        self.assertEqual(sorted(resultados), [200, 400])
        self.repuesto.refresh_from_db()
        self.assertEqual(self.repuesto.stock_actual, 5)
        self.assertEqual(MovimientoRepuesto.objects.filter(tipo_movimiento="DEVOLUCION_TALLER").count(), 1)

    def test_fallo_de_auditoria_revierte_consumo_y_reintegro(self):
        from unittest.mock import patch

        from .repuestos import anular_asignacion_repuesto, asignar_repuesto_orden

        with patch("ordenes_trabajo.repuestos.registrar_auditoria", side_effect=RuntimeError("Fallo de auditoría")):
            with self.assertRaises(RuntimeError):
                asignar_repuesto_orden(self.orden.pk, self.repuesto.pk, 2, self.tecnico)
        self.repuesto.refresh_from_db()
        self.assertEqual(self.repuesto.stock_actual, 5)
        self.assertFalse(OrdenRepuesto.objects.exists())
        asignacion = self.asignar().data["id_orden_repuesto"]
        with patch("ordenes_trabajo.repuestos.registrar_auditoria", side_effect=RuntimeError("Fallo de auditoría")):
            with self.assertRaises(RuntimeError):
                anular_asignacion_repuesto(self.orden.pk, asignacion, "Pieza no utilizada", self.tecnico)
        self.repuesto.refresh_from_db()
        self.assertEqual(self.repuesto.stock_actual, 3)
        self.assertFalse(OrdenRepuesto.objects.get(pk=asignacion).anulado)
        self.assertFalse(MovimientoRepuesto.objects.filter(tipo_movimiento="DEVOLUCION_TALLER").exists())

    def test_sql_impide_anulacion_sin_responsable_fecha_y_motivo(self):
        from django.db import IntegrityError, transaction

        asignacion = self.asignar().data["id_orden_repuesto"]
        with self.assertRaises(IntegrityError), transaction.atomic():
            OrdenRepuesto.objects.filter(pk=asignacion).update(anulado=True)
        self.assertFalse(OrdenRepuesto.objects.get(pk=asignacion).anulado)

    def test_consulta_del_catalogo_permite_tecnico_y_administrador(self):
        for usuario in [self.tecnico, self.admin]:
            self.assertEqual(self.cliente(usuario).get("/api/repuestos/").status_code, 200)
        self.assertEqual(self.cliente(self.solicitante).get("/api/repuestos/").status_code, 403)
