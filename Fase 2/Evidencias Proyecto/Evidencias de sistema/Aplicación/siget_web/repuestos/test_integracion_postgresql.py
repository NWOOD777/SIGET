from decimal import Decimal
from unittest.mock import patch

from django.db import DatabaseError

from usuarios.tests.test_integracion_postgresql import PostgreSQLTestBase
from usuarios.models import BitacoraAuditoria
from .models import Repuesto, MovimientoRepuesto


class IngresoRepuestoPostgreSQLTests(PostgreSQLTestBase):

    URL = "/api/repuestos/ingresos/"

    def datos(self, cantidad=5, costo="15000.00"):
        return {
            "nombre": "Memoria RAM DDR4",
            "cantidad": cantidad,
            "costo_unitario": costo,
        }

    def test_registrar_repuesto_nuevo(self):
        respuesta = self.cliente(self.admin).post(
            self.URL, self.datos(), format="json"
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.data)

        repuesto = Repuesto.objects.get()

        self.assertEqual(
            repuesto.codigo_repuesto,
            f"REP-{repuesto.id_repuesto:04d}"
        )
        self.assertEqual(repuesto.stock_actual, 5)
        self.assertEqual(repuesto.precio_unitario, Decimal("15000.00"))
        self.assertTrue(respuesta.data["repuesto_creado"])

        movimiento = MovimientoRepuesto.objects.get(repuesto=repuesto)

        self.assertEqual(movimiento.tipo_movimiento, "INGRESO_COMPRA")
        self.assertEqual(movimiento.cantidad, 5)
        self.assertEqual(movimiento.usuario, self.admin)

    def test_codigos_automaticos_unicos(self):
        cliente = self.cliente(self.admin)

        primera = cliente.post(self.URL, self.datos(), format="json")

        segunda = cliente.post(
            self.URL,
            {
                "nombre": "Disco SSD",
                "cantidad": 3,
                "costo_unitario": "20000.00",
            },
            format="json",
        )

        self.assertEqual(primera.status_code, 201, primera.data)
        self.assertEqual(segunda.status_code, 201, segunda.data)

        codigos = list(
            Repuesto.objects.values_list("codigo_repuesto", flat=True)
        )

        self.assertEqual(len(codigos), 2)
        self.assertEqual(len(set(codigos)), 2)
        self.assertTrue(all(c.startswith("REP-") for c in codigos))

    def test_incrementar_stock_y_costo_promedio(self):
        repuesto = Repuesto.objects.create(
            codigo_repuesto="REP-EXISTENTE",
            nombre="Memoria RAM DDR4",
            stock_actual=10,
            precio_unitario=Decimal("2000.00"),
        )

        respuesta = self.cliente(self.admin).post(
            self.URL,
            {
                "id_repuesto": repuesto.id_repuesto,
                "cantidad": 5,
                "costo_unitario": "3000.00",
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.data)

        repuesto.refresh_from_db()

        self.assertEqual(repuesto.stock_actual, 15)
        self.assertEqual(repuesto.precio_unitario, Decimal("2333.33"))
        self.assertEqual(repuesto.codigo_repuesto, "REP-EXISTENTE")
        self.assertFalse(respuesta.data["repuesto_creado"])
        self.assertEqual(Repuesto.objects.count(), 1)
        self.assertEqual(MovimientoRepuesto.objects.count(), 1)

    def test_repuesto_existente_inexistente(self):
        respuesta = self.cliente(self.admin).post(
            self.URL,
            {
                "id_repuesto": 999999,
                "cantidad": 5,
                "costo_unitario": "3000.00",
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 404)
        self.assertFalse(MovimientoRepuesto.objects.exists())

    def test_cantidad_invalida_no_modifica_stock(self):
        for cantidad in (0, -5):
            respuesta = self.cliente(self.admin).post(
                self.URL,
                self.datos(cantidad=cantidad),
                format="json",
            )

            self.assertEqual(respuesta.status_code, 400, respuesta.data)

        self.assertFalse(Repuesto.objects.exists())
        self.assertFalse(MovimientoRepuesto.objects.exists())

    def test_campos_obligatorios(self):
        for campo in ("nombre", "cantidad"):
            datos = self.datos()
            datos.pop(campo)

            respuesta = self.cliente(self.admin).post(
                self.URL, datos, format="json"
            )

            self.assertEqual(respuesta.status_code, 400, respuesta.data)
            self.assertIn(campo, respuesta.data)

        self.assertFalse(Repuesto.objects.exists())

    def test_rbac_solo_administrador(self):
        for usuario in (self.tecnico, self.solicitante):
            respuesta = self.cliente(usuario).post(
                self.URL, self.datos(), format="json"
            )

            self.assertEqual(respuesta.status_code, 403, respuesta.data)

        self.assertFalse(Repuesto.objects.exists())

    def test_rollback_si_falla_movimiento(self):
        with patch(
            "repuestos.services.MovimientoRepuesto.objects.create",
            side_effect=DatabaseError("Fallo simulado"),
        ):
            with self.assertRaises(DatabaseError):
                self.cliente(self.admin).post(
                    self.URL, self.datos(), format="json"
                )

        self.assertFalse(Repuesto.objects.exists())
        self.assertFalse(MovimientoRepuesto.objects.exists())

    def test_ingreso_registra_auditoria(self):
        respuesta = self.cliente(self.admin).post(
            self.URL, self.datos(), format="json"
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.data)

        repuesto = Repuesto.objects.get()

        auditoria = BitacoraAuditoria.objects.get(
            modulo="REPUESTOS",
            accion="INGRESO_COMPRA",
        )

        self.assertEqual(auditoria.id_usuario, self.admin)
        self.assertEqual(auditoria.entidad_afectada, "repuesto")
        self.assertEqual(auditoria.id_registro_afectado, repuesto.pk)
        self.assertIn(
            repuesto.codigo_repuesto,
            auditoria.detalle_evento,
        )

    def test_rollback_si_falla_auditoria(self):
        with patch(
            "repuestos.services.registrar_auditoria",
            side_effect=DatabaseError("Fallo simulado de auditoría"),
        ):
            with self.assertRaises(DatabaseError):
                self.cliente(self.admin).post(
                    self.URL, self.datos(), format="json"
                )

        self.assertFalse(Repuesto.objects.exists())
        self.assertFalse(MovimientoRepuesto.objects.exists())
        self.assertFalse(
            BitacoraAuditoria.objects.filter(modulo="REPUESTOS").exists()
        )