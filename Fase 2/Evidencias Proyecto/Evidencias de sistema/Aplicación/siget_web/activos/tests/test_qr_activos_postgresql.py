"""Generación QR separada de las escrituras del inventario."""

from unittest.mock import patch

import requests
from django.db import connection
from django.test import override_settings

from activos.models import Activo
from activos.qr import generar_qr_activo
from activos.qr_client import ErrorGeneracionQR
from activos.tests.test_qr_client import CONFIG, respuesta_svg
from usuarios.tests.test_integracion_postgresql import PostgreSQLTestBase


@override_settings(**CONFIG)
class QRActivosPostgreSQLTests(PostgreSQLTestBase):
    def test_generacion_no_modifica_activo_ni_crea_registro_qr(self):
        activo = self.activo()
        antes = Activo.objects.values().get(pk=activo.pk)
        with patch("activos.qr_client.requests.post", return_value=respuesta_svg()) as post:
            imagen = generar_qr_activo(activo)
        self.assertEqual(imagen.payload, activo.codigo_inventario)
        self.assertEqual(post.call_args.kwargs["data"]["data"], activo.codigo_inventario)
        self.assertEqual(Activo.objects.values().get(pk=activo.pk), antes)
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM codigo_qr")
            self.assertEqual(cursor.fetchone()[0], 0)

    def test_fallo_y_reintento_conservan_el_activo_confirmado(self):
        activo = self.activo()
        antes = Activo.objects.values().get(pk=activo.pk)
        with patch("activos.qr_client.requests.post", side_effect=requests.Timeout):
            with self.assertRaises(ErrorGeneracionQR):
                generar_qr_activo(activo)
        self.assertEqual(Activo.objects.values().get(pk=activo.pk), antes)
        with patch("activos.qr_client.requests.post", return_value=respuesta_svg()):
            self.assertEqual(generar_qr_activo(activo).payload, activo.codigo_inventario)
        self.assertEqual(Activo.objects.values().get(pk=activo.pk), antes)
