"""Persistencia, autorización y concurrencia del flujo de etiquetas QR."""

import os
from unittest import skipUnless
from unittest.mock import patch
from xml.etree import ElementTree

import requests
from django.db import connection
from django.test import override_settings

from activos.models import Activo, CodigoQR
from activos.tests.test_qr_client import CONFIG, respuesta_svg
from usuarios.models import BitacoraAuditoria
from usuarios.tests.test_integracion_postgresql import PostgreSQLTestBase


@override_settings(**CONFIG)
class EtiquetasQRPostgreSQLTests(PostgreSQLTestBase):
    def setUp(self):
        super().setUp()
        self.equipo = self.activo()
        self.url = f"/api/activos/{self.equipo.pk}/qr/"
        proveedor_patch = patch("activos.qr_client.requests.post", return_value=respuesta_svg())
        self.proveedor = proveedor_patch.start()
        self.addCleanup(proveedor_patch.stop)

    def generar(self, reimprimir=False):
        return self.cliente(self.admin).post(self.url, {"reimprimir": reimprimir}, format="json")

    def test_generacion_asocia_identificador_y_audita_sin_modificar_activo(self):
        antes = Activo.objects.values().get(pk=self.equipo.pk)

        def respuesta(*args, **kwargs):
            self.assertFalse(connection.in_atomic_block)
            return respuesta_svg()

        self.proveedor.side_effect = respuesta
        r = self.generar()
        self.assertEqual(r.status_code, 200, r.data)
        qr = CodigoQR.objects.get(id_activo=self.equipo)
        self.assertEqual(qr.payload_qr, self.equipo.codigo_inventario)
        self.assertEqual(qr.formato_imagen, "SVG")
        self.assertEqual(qr.veces_reimpreso, 0)
        self.assertEqual(r.data["id_qr"], qr.pk)
        self.assertIn("<", r.data["svg"])
        self.assertEqual(Activo.objects.values().get(pk=self.equipo.pk), antes)
        evento = BitacoraAuditoria.objects.get(accion="GENERAR_QR")
        self.assertEqual(evento.id_usuario.pk, self.admin.pk)
        self.assertEqual(evento.id_registro_afectado, qr.pk)
        self.assertNotIn(self.admin.rut, evento.detalle_evento)

    def test_consulta_no_invoca_api_y_generacion_repetida_conserva_asociacion(self):
        cliente = self.cliente(self.admin)
        self.assertFalse(cliente.get(self.url).data["generado"])
        self.proveedor.assert_not_called()
        primero = self.generar().data
        segundo = self.generar().data
        self.assertEqual(primero["id_qr"], segundo["id_qr"])
        self.assertEqual(primero["fecha_generacion"], segundo["fecha_generacion"])
        self.assertEqual(segundo["veces_reimpreso"], 0)
        self.assertEqual(CodigoQR.objects.count(), 1)
        self.assertEqual(BitacoraAuditoria.objects.filter(accion="GENERAR_QR").count(), 1)
        self.proveedor.reset_mock()
        estado = cliente.get(self.url)
        self.assertTrue(estado.data["generado"])
        self.assertNotIn("svg", estado.data)
        self.proveedor.assert_not_called()

    def test_reimpresion_mantiene_identificador_fecha_e_historial(self):
        antes = self.generar().data
        respuesta = self.generar(reimprimir=True)
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        for campo in ("id_qr", "payload_qr", "fecha_generacion", "codigo_inventario"):
            self.assertEqual(antes[campo], respuesta.data[campo])
        self.assertEqual(respuesta.data["veces_reimpreso"], 1)
        self.assertTrue(BitacoraAuditoria.objects.filter(accion="REIMPRIMIR_QR").exists())
        self.assertEqual(self.proveedor.call_args.kwargs["data"]["data"], antes["payload_qr"])

    def test_reimprimir_sin_etiqueta_o_activo_inexistente_no_llama_proveedor(self):
        self.assertEqual(self.generar(reimprimir=True).status_code, 404)
        self.assertEqual(self.cliente(self.admin).post("/api/activos/999999/qr/", {}, format="json").status_code, 404)
        self.proveedor.assert_not_called()

    def test_solo_admin_real_puede_generar_y_consultar(self):
        for usuario in (None, self.tecnico, self.solicitante):
            cliente = self.cliente(usuario)
            for metodo in (cliente.get, cliente.post):
                r = metodo(self.url)
                self.assertIn(r.status_code, (401, 403))
        self.proveedor.assert_not_called()
        self.assertFalse(CodigoQR.objects.exists())

    def test_datos_invalidos_y_csrf_no_generan_etiqueta(self):
        r = self.cliente(self.admin).post(self.url, {"reimprimir": "incorrecto"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.cliente(self.admin, csrf=True).post(self.url, {}, format="json").status_code, 403)
        self.proveedor.assert_not_called()

    def test_timeout_no_modifica_datos_y_admite_reintento(self):
        antes = Activo.objects.values().get(pk=self.equipo.pk)
        self.proveedor.side_effect = requests.Timeout
        r = self.generar()
        self.assertEqual(r.status_code, 503)
        self.assertTrue(r.data["reintentable"])
        self.assertEqual(r.data["codigo"], "tiempo_agotado")
        self.assertEqual(Activo.objects.values().get(pk=self.equipo.pk), antes)
        self.assertFalse(CodigoQR.objects.exists())
        self.assertFalse(BitacoraAuditoria.objects.filter(accion="GENERAR_QR").exists())
        self.proveedor.side_effect = None
        self.assertEqual(self.generar().status_code, 200)

    def test_fallo_de_reimpresion_conserva_contador_y_fecha(self):
        self.generar()
        antes = CodigoQR.objects.values().get(id_activo=self.equipo)
        self.proveedor.return_value = respuesta_svg(status=503)
        self.assertEqual(self.generar(reimprimir=True).status_code, 503)
        self.assertEqual(CodigoQR.objects.values().get(id_activo=self.equipo), antes)

    def test_respuesta_invalida_no_persiste(self):
        self.proveedor.return_value = respuesta_svg(b"<script/>")
        self.assertEqual(self.generar().status_code, 503)
        self.assertFalse(CodigoQR.objects.exists())

    def test_concurrencia_crea_una_asociacion_y_no_pierde_reimpresiones(self):
        resultados = self.competir(lambda _: self.generar().status_code)
        self.assertEqual(resultados, [200, 200])
        self.assertEqual(CodigoQR.objects.count(), 1)
        self.assertEqual(BitacoraAuditoria.objects.filter(accion="GENERAR_QR").count(), 1)
        resultados = self.competir(lambda _: self.generar(reimprimir=True).status_code)
        self.assertEqual(resultados, [200, 200])
        self.assertEqual(CodigoQR.objects.get(id_activo=self.equipo).veces_reimpreso, 2)

    def test_fallo_de_auditoria_revierte_solo_la_asociacion_qr(self):
        with patch("activos.qr.auditar_evento_activos", side_effect=RuntimeError("Fallo de auditoría")):
            with self.assertRaises(RuntimeError):
                self.generar()
        self.assertTrue(Activo.objects.filter(pk=self.equipo.pk).exists())
        self.assertFalse(CodigoQR.objects.exists())

    def test_identificador_cambiado_durante_solicitud_no_asocia_otro_payload(self):
        def respuesta(*args, **kwargs):
            Activo.objects.filter(pk=self.equipo.pk).update(codigo_inventario="ACT-9999")
            return respuesta_svg()

        self.proveedor.side_effect = respuesta
        self.assertEqual(self.generar().status_code, 409)
        self.assertFalse(CodigoQR.objects.exists())


@skipUnless(os.environ.get("SIGET_TEST_QR_LIVE") == "1", "Requiere activar SIGET_TEST_QR_LIVE=1 para consultar al proveedor.")
@override_settings(**CONFIG)
class EtiquetasQRLiveTests(PostgreSQLTestBase):
    def test_endpoint_genera_y_persiste_etiqueta_real(self):
        activo = self.activo()
        respuesta = self.cliente(self.admin).post(f"/api/activos/{activo.pk}/qr/", {}, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["payload_qr"], activo.codigo_inventario)
        svg = ElementTree.fromstring(respuesta.data["svg"])
        self.assertEqual(svg.findtext("{http://www.w3.org/2000/svg}desc"), activo.codigo_inventario)
        self.assertEqual(CodigoQR.objects.get(id_activo=activo).payload_qr, activo.codigo_inventario)
