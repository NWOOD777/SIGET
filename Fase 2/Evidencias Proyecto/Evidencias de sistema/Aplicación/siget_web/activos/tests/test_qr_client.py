"""Transporte, validación vectorial y comprobación del proveedor QR."""

import os
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import skipUnless
from unittest.mock import MagicMock, patch
from xml.etree import ElementTree

import requests
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from activos.models import Activo
from activos.qr import generar_qr_activo
from activos.qr_client import MAX_BYTES, ErrorGeneracionQR, ImagenQR, generar_qr

SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="406" height="406"><rect width="406" height="406" style="fill:rgb(255, 255, 255);fill-opacity:1"/><path d="M 1,1 l 2,0 0,2 -2,0 z" style="fill:rgb(0, 0, 0)"/></svg>'
URL_PROVEEDOR = "https://api.qrserver.com/v1/create-qr-code/"
CONFIG = dict(QR_SERVER_URL=URL_PROVEEDOR, QR_SERVER_CONNECT_TIMEOUT_SECONDS=5, QR_SERVER_READ_TIMEOUT_SECONDS=15, QR_SERVER_SIZE=300)


def respuesta_svg(contenido=SVG, status=200, headers=None):
    response = MagicMock(status_code=status, headers=headers if headers is not None else {"Content-Type": "image/svg+xml"})
    response.__enter__.return_value = response
    response.iter_content.return_value = [contenido]
    return response


@override_settings(**CONFIG)
class QRServerClientTests(SimpleTestCase):
    def test_envia_solo_el_identificador_y_recibe_svg_escalable(self):
        response = respuesta_svg()
        with patch("activos.qr_client.requests.post", return_value=response) as post:
            imagen = generar_qr("ACT-0001")
        args, kwargs = post.call_args
        self.assertEqual(args, (CONFIG["QR_SERVER_URL"],))
        self.assertEqual(
            kwargs["data"],
            {"data": "ACT-0001", "size": "300x300", "format": "svg", "ecc": "M", "qzone": "4", "charset-source": "UTF-8", "charset-target": "UTF-8"},
        )
        self.assertEqual(kwargs["headers"], {"Accept": "image/svg+xml"})
        self.assertEqual(kwargs["timeout"], (5, 15))
        self.assertFalse(kwargs["allow_redirects"])
        self.assertTrue(kwargs["stream"])
        raiz = ElementTree.fromstring(imagen.contenido)
        self.assertEqual(raiz.get("width"), "300")
        self.assertEqual(raiz.get("height"), "300")
        self.assertEqual(raiz.get("viewBox"), "0 0 406 406")
        self.assertEqual((imagen.payload, imagen.formato, imagen.tipo_contenido), ("ACT-0001", "SVG", "image/svg+xml"))
        response.__exit__.assert_called_once()

    def test_codigos_invalidos_no_salen_del_backend(self):
        for codigo in [
            None,
            True,
            1234,
            "",
            "ACT-1",
            "act-0001",
            "ACT-0001\n",
            "ACT-0001 ",
            "ACT-" + "1" * 47,
            "11.111.111-1",
            "user@example.invalid",
            "https://example.invalid",
            "ACT-٠٠٠١",
        ]:
            with self.subTest(codigo=codigo), patch("activos.qr_client.requests.post") as post:
                with self.assertRaises(ErrorGeneracionQR) as error:
                    generar_qr(codigo)
                self.assertEqual(error.exception.codigo, "codigo_invalido")
                post.assert_not_called()

    def test_configuracion_invalida_no_realiza_solicitudes(self):
        for cambio in [
            dict(QR_SERVER_URL="http://api.qrserver.com/v1/create-qr-code/"),
            dict(QR_SERVER_URL="https://otro.example.invalid/"),
            dict(QR_SERVER_URL="https://user:secreto@api.qrserver.com/v1/create-qr-code/"),
            dict(QR_SERVER_URL=URL_PROVEEDOR + "?data=otro"),
            dict(QR_SERVER_SIZE=0),
            dict(QR_SERVER_SIZE=1001),
            dict(QR_SERVER_SIZE=True),
            dict(QR_SERVER_CONNECT_TIMEOUT_SECONDS=0),
            dict(QR_SERVER_READ_TIMEOUT_SECONDS=float("nan")),
            dict(QR_SERVER_READ_TIMEOUT_SECONDS=61),
        ]:
            with self.subTest(cambio=cambio), override_settings(**cambio), patch("activos.qr_client.requests.post") as post:
                with self.assertRaises(ErrorGeneracionQR) as error:
                    generar_qr("ACT-0001")
                self.assertEqual(error.exception.codigo, "configuracion_invalida")
                self.assertNotIn("secreto", str(error.exception))
                post.assert_not_called()

    def test_rechaza_redirecciones_y_errores_http(self):
        for status, transitorio in [(302, False), (400, False), (429, True), (500, True), (503, True)]:
            with self.subTest(status=status), patch("activos.qr_client.requests.post", return_value=respuesta_svg(status=status)) as post:
                with self.assertRaises(ErrorGeneracionQR) as error:
                    generar_qr("ACT-0001")
                self.assertEqual(error.exception.transitorio, transitorio)
                self.assertIn(str(status), str(error.exception))
                self.assertEqual(post.call_count, 1)

    def test_errores_de_red_se_registran_sin_cuerpo_ni_datos_del_request(self):
        for exc, codigo in [
            (requests.Timeout("DATO_PRIVADO"), "tiempo_agotado"),
            (requests.ConnectionError("DATO_PRIVADO"), "sin_conexion"),
            (requests.RequestException("DATO_PRIVADO"), "error_red"),
        ]:
            with self.subTest(codigo=codigo), patch("activos.qr_client.requests.post", side_effect=exc):
                with self.assertLogs("activos.qr_client", level="WARNING") as logs, self.assertRaises(ErrorGeneracionQR) as error:
                    generar_qr("ACT-0001")
                self.assertEqual(error.exception.codigo, codigo)
                self.assertTrue(error.exception.transitorio)
                self.assertNotIn("DATO_PRIVADO", str(logs.output) + str(error.exception))
                self.assertNotIn("ACT-0001", str(logs.output))

    def test_respuesta_tiene_que_ser_svg_y_de_tamano_acotado(self):
        for headers, contenido in [
            ({"Content-Type": "text/html"}, b"<html>Error</html>"),
            ({}, SVG),
            ({"Content-Type": "image/svg+xml", "Content-Length": str(MAX_BYTES + 1)}, SVG),
            ({"Content-Type": "image/svg+xml", "Content-Length": "invalido"}, SVG),
            ({"Content-Type": "image/svg+xml", "Content-Length": "-1"}, SVG),
            ({"Content-Type": "image/svg+xml"}, b"x" * (MAX_BYTES + 1)),
        ]:
            response = respuesta_svg(contenido, headers=headers)
            with self.subTest(headers=headers), patch("activos.qr_client.requests.post", return_value=response):
                with self.assertRaises(ErrorGeneracionQR):
                    generar_qr("ACT-0001")
                response.__exit__.assert_called_once()

    def test_rechaza_svg_activo_invalido_o_con_recursos_externos(self):
        casos = [
            b"",
            b"\xff\xfe",
            b"<svg",
            SVG.replace(b'406" height', b'NaN" height', 1),
            SVG.replace(b'height="406"', b'height="500"', 1),
            SVG.replace(b"<path ", b"<script/> <path ", 1),
            SVG.replace(b"<rect ", b"<foreignObject/> <rect ", 1),
            SVG.replace(b"<path ", b'<path onclick="alert(1)" ', 1),
            SVG.replace(b"<path ", b'<path href="file:///etc/passwd" ', 1),
            SVG.replace(b"fill:rgb(0, 0, 0)", b"fill:url(https://otro.example.invalid/)"),
            b'<!DOCTYPE svg [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>' + SVG,
            b'<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300"/>',
        ]
        for contenido in casos:
            with self.subTest(contenido=contenido[:50]), patch("activos.qr_client.requests.post", return_value=respuesta_svg(contenido)):
                with self.assertRaises(ErrorGeneracionQR) as error:
                    generar_qr("ACT-0001")
                self.assertEqual(error.exception.codigo, "respuesta_invalida")

    def test_lee_varios_bloques_y_acepta_mime_con_charset(self):
        response = respuesta_svg(headers={"Content-Type": "image/svg+xml; charset=utf-8"})
        response.iter_content.return_value = [SVG[:50], b"", SVG[50:]]
        with patch("activos.qr_client.requests.post", return_value=response):
            self.assertEqual(generar_qr("ACT-0001").payload, "ACT-0001")

    def test_activo_no_guardado_no_invoca_al_proveedor(self):
        with patch("activos.qr.generar_qr") as proveedor:
            with self.assertRaises(ErrorGeneracionQR):
                generar_qr_activo(Activo(codigo_inventario="ACT-0001"))
            proveedor.assert_not_called()


class ComandoQRTests(SimpleTestCase):
    def test_guarda_la_imagen_y_muestra_su_verificacion(self):
        with (
            TemporaryDirectory() as tmp,
            patch("activos.management.commands.verificar_qr.generar_qr", return_value=ImagenQR(payload="ACT-0001", contenido=SVG)),
        ):
            destino = Path(tmp) / "codigo.svg"
            salida = StringIO()
            call_command("verificar_qr", codigo="ACT-0001", salida=destino, stdout=salida)
            self.assertEqual(destino.read_bytes(), SVG)
            self.assertIn("SHA-256", salida.getvalue())

    def test_no_sobrescribe_archivos_ni_invoca_api_para_salida_invalida(self):
        with TemporaryDirectory() as tmp, patch("activos.management.commands.verificar_qr.generar_qr") as proveedor:
            destino = Path(tmp) / "codigo.svg"
            destino.write_bytes(b"original")
            with self.assertRaises(CommandError):
                call_command("verificar_qr", codigo="ACT-0001", salida=destino)
            self.assertEqual(destino.read_bytes(), b"original")
            with self.assertRaises(CommandError):
                call_command("verificar_qr", codigo="ACT-0001", salida=Path(tmp) / "codigo.html")
            proveedor.assert_not_called()

    def test_error_del_proveedor_no_genera_archivo(self):
        with (
            TemporaryDirectory() as tmp,
            patch(
                "activos.management.commands.verificar_qr.generar_qr",
                side_effect=ErrorGeneracionQR("Tiempo agotado", codigo="tiempo_agotado", transitorio=True),
            ),
        ):
            destino = Path(tmp) / "codigo.svg"
            with self.assertRaises(CommandError):
                call_command("verificar_qr", codigo="ACT-0001", salida=destino)
            self.assertFalse(destino.exists())


@skipUnless(os.environ.get("SIGET_TEST_QR_LIVE") == "1", "Requiere activar SIGET_TEST_QR_LIVE=1 para consultar al proveedor externo.")
@override_settings(**CONFIG)
class QRServerLiveTests(SimpleTestCase):
    def test_recibe_un_svg_real_con_el_identificador_solicitado(self):
        imagen = generar_qr("ACT-9999")
        raiz = ElementTree.fromstring(imagen.contenido)
        self.assertEqual(raiz.tag, "{http://www.w3.org/2000/svg}svg")
        self.assertEqual(raiz.findtext("{http://www.w3.org/2000/svg}desc"), "ACT-9999")
        self.assertEqual(imagen.formato, "SVG")
