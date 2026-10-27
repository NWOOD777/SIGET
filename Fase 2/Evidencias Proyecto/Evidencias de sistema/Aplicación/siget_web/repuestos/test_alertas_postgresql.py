
from unittest.mock import patch

from django.db import DatabaseError

from usuarios.models import BitacoraAuditoria
from usuarios.tests.test_integracion_postgresql import PostgreSQLTestBase

from .models import Repuesto


class AlertasRepuestosPostgreSQLTests(PostgreSQLTestBase):

    URL_ALERTAS = "/api/repuestos/alertas/"

    def setUp(self):
        super().setUp()

        self.repuesto = Repuesto.objects.create(
            codigo_repuesto="REP-PRUEBA",
            nombre="Memoria RAM DDR4",
            stock_actual=8,
            stock_minimo=5,
        )

    def url_minimo(self):
        return (
            f"/api/repuestos/"
            f"{self.repuesto.id_repuesto}/stock-minimo/"
        )

    def test_inventario_normal_sin_alertas(self):
        respuesta = self.cliente(self.admin).get(
            self.URL_ALERTAS
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["total_alertas"], 0)
        self.assertEqual(
            respuesta.data["estado_general"],
            "NORMAL",
        )
        self.assertEqual(respuesta.data["alertas"], [])

    def test_alerta_activada_por_stock_critico(self):
        self.repuesto.stock_actual = 5
        self.repuesto.save(update_fields=["stock_actual"])

        respuesta = self.cliente(self.admin).get(
            self.URL_ALERTAS
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["total_alertas"], 1)

        alerta = respuesta.data["alertas"][0]

        self.assertEqual(alerta["stock_actual"], 5)
        self.assertEqual(alerta["stock_minimo"], 5)
        self.assertEqual(alerta["estado"], "Stock Crítico")
        self.assertEqual(alerta["cantidad_sugerida"], 1)

    def test_listado_multiples_repuestos_criticos(self):
        self.repuesto.stock_actual = 2
        self.repuesto.save(update_fields=["stock_actual"])

        Repuesto.objects.create(
            codigo_repuesto="REP-PRUEBA-2",
            nombre="Disco SSD",
            stock_actual=1,
            stock_minimo=3,
        )

        respuesta = self.cliente(self.admin).get(
            self.URL_ALERTAS
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["total_alertas"], 2)

        codigos = {
            alerta["codigo_repuesto"]
            for alerta in respuesta.data["alertas"]
        }

        self.assertEqual(
            codigos,
            {"REP-PRUEBA", "REP-PRUEBA-2"},
        )

    def test_actualizar_minimo_activa_alerta(self):
        respuesta = self.cliente(self.admin).patch(
            self.url_minimo(),
            {"stock_minimo": 10},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)

        self.repuesto.refresh_from_db()

        self.assertEqual(self.repuesto.stock_minimo, 10)
        self.assertEqual(respuesta.data["estado"], "Stock Crítico")
        self.assertEqual(respuesta.data["cantidad_sugerida"], 3)

        alertas = self.cliente(self.admin).get(
            self.URL_ALERTAS
        )

        self.assertEqual(alertas.data["total_alertas"], 1)

    def test_actualizar_minimo_desactiva_alerta(self):
        self.repuesto.stock_minimo = 10
        self.repuesto.save(update_fields=["stock_minimo"])

        respuesta = self.cliente(self.admin).patch(
            self.url_minimo(),
            {"stock_minimo": 5},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["estado"], "Normal")

        alertas = self.cliente(self.admin).get(
            self.URL_ALERTAS
        )

        self.assertEqual(alertas.data["total_alertas"], 0)

    def test_rbac_solo_administrador(self):
        for usuario in (self.tecnico, self.solicitante):
            respuesta = self.cliente(usuario).patch(
                self.url_minimo(),
                {"stock_minimo": 10},
                format="json",
            )

            self.assertEqual(respuesta.status_code, 403)

            consulta = self.cliente(usuario).get(
                self.URL_ALERTAS
            )

            self.assertEqual(consulta.status_code, 403)

        self.repuesto.refresh_from_db()
        self.assertEqual(self.repuesto.stock_minimo, 5)

    def test_minimo_negativo_rechazado(self):
        respuesta = self.cliente(self.admin).patch(
            self.url_minimo(),
            {"stock_minimo": -1},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)

        self.repuesto.refresh_from_db()
        self.assertEqual(self.repuesto.stock_minimo, 5)

    def test_repuesto_inexistente(self):
        respuesta = self.cliente(self.admin).patch(
            "/api/repuestos/999999/stock-minimo/",
            {"stock_minimo": 10},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 404)

    def test_actualizacion_registra_auditoria(self):
        respuesta = self.cliente(self.admin).patch(
            self.url_minimo(),
            {"stock_minimo": 10},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200)

        auditoria = BitacoraAuditoria.objects.get(
            modulo="REPUESTOS",
            accion="ACTUALIZAR_STOCK_MINIMO",
        )

        self.assertEqual(auditoria.id_usuario, self.admin)
        self.assertEqual(
            auditoria.id_registro_afectado,
            self.repuesto.pk,
        )

    def test_rollback_si_falla_auditoria(self):
        with patch(
            "repuestos.services.registrar_auditoria",
            side_effect=DatabaseError("Fallo simulado"),
        ):
            with self.assertRaises(DatabaseError):
                self.cliente(self.admin).patch(
                    self.url_minimo(),
                    {"stock_minimo": 10},
                    format="json",
                )

        self.repuesto.refresh_from_db()
        self.assertEqual(self.repuesto.stock_minimo, 5)
