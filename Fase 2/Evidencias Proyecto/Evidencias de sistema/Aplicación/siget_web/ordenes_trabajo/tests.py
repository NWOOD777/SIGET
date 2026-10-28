
from django.test import SimpleTestCase
from usuarios.tests.test_integracion_postgresql import PostgreSQLTestBase

from .serializers import (
    AsignarRepuestoOTSerializer,
    AnularAsignacionRepuestoOTSerializer,
)


from decimal import Decimal

from activos.models import EstadoActivo
from ordenes_trabajo.models import OrdenRepuesto
from ordenes_trabajo.services import crear_orden_trabajo, iniciar_reparacion
from repuestos.models import MovimientoRepuesto, Repuesto
from tickets.tests.test_estados_tickets import EstadoFixture
from usuarios.models import BitacoraAuditoria


class AsignarRepuestoOTSerializerTests(SimpleTestCase):

    def setUp(self):
        self.datos_validos = {
            "id_repuesto": 1,
            "cantidad": 2,
        }

    def test_asignacion_valida(self):
        serializer = AsignarRepuestoOTSerializer(
            data=self.datos_validos
        )
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
        serializer = AnularAsignacionRepuestoOTSerializer(
            data={"motivo": "Repuesto no utilizado"}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_motivo_obligatorio(self):
        serializer = AnularAsignacionRepuestoOTSerializer(
            data={}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("motivo", serializer.errors)

    def test_motivo_vacio(self):
        serializer = AnularAsignacionRepuestoOTSerializer(
            data={"motivo": ""}
        )
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
        activo.id_estado_activo = EstadoActivo.objects.get(
            nombre="En revisión"
        )
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

        self.url = (
            f"/api/ordenes-trabajo/{self.orden.pk}/repuestos/"
        )

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

        asignacion = OrdenRepuesto.objects.get(
            id_orden=self.orden
        )
        self.assertEqual(asignacion.cantidad, 2)
        self.assertFalse(asignacion.anulado)

        self.assertTrue(
            MovimientoRepuesto.objects.filter(
                repuesto=self.repuesto,
                tipo_movimiento="SALIDA_TALLER",
                cantidad=2,
            ).exists()
        )

        self.assertTrue(
            BitacoraAuditoria.objects.filter(
                accion="REPUESTO_ASIGNADO"
            ).exists()
        )

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

        asignacion_id = asignacion_respuesta.data[
            "id_orden_repuesto"
        ]

        respuesta = self.cliente(self.tecnico).post(
            f"{self.url}{asignacion_id}/anular/",
            {"motivo": "Repuesto no utilizado"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)

        self.repuesto.refresh_from_db()
        self.assertEqual(self.repuesto.stock_actual, 5)

        asignacion = OrdenRepuesto.objects.get(
            pk=asignacion_id
        )
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

        asignacion_id = asignacion_respuesta.data[
            "id_orden_repuesto"
        ]
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
            MovimientoRepuesto.objects.filter(
                tipo_movimiento="DEVOLUCION_TALLER"
            ).count(),
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
