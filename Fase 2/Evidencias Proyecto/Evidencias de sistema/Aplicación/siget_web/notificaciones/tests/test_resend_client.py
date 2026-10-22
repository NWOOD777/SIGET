from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase, override_settings

from notificaciones.resend_client import ErrorCorreo, enviar_correo


@override_settings(RESEND_API_KEY="re_solo_pruebas", RESEND_TIMEOUT_SECONDS=10)
class ClienteResendTests(SimpleTestCase):
    datos = {"from": "SIGET <notificaciones@example.org>", "to": ["destino@example.org"], "subject": "Aviso", "text": "Texto", "html": "<p>Texto</p>"}

    @patch("notificaciones.resend_client.requests.post")
    def test_peticion_rest_con_timeout_y_idempotencia(self, http):
        http.return_value = Mock(status_code=200, json=Mock(return_value={"id": "id-aceptado"}))
        self.assertEqual(enviar_correo(self.datos, "evento-1"), "id-aceptado")
        self.assertEqual(http.call_args.args, ("https://api.resend.com/emails",))
        self.assertEqual(http.call_args.kwargs["timeout"], 10)
        self.assertEqual(http.call_args.kwargs["headers"]["Idempotency-Key"], "evento-1")

    @patch("notificaciones.resend_client.requests.post")
    def test_timeout_y_error_conexion_no_filtran_secretos(self, http):
        for error in (requests.Timeout("re_secreto"), requests.ConnectionError("re_secreto")):
            http.side_effect = error
            with self.assertRaises(ErrorCorreo) as ctx:
                enviar_correo(self.datos, "a")
            self.assertTrue(ctx.exception.transitorio)
            self.assertNotIn("re_secreto", str(ctx.exception))

    @patch("notificaciones.resend_client.requests.post")
    def test_errores_permanentes_y_transitorios(self, http):
        for status, transitorio in ((400, False), (401, False), (403, False), (422, False), (409, True), (429, True), (503, True)):
            http.return_value = Mock(status_code=status, headers={"Retry-After": "60"})
            with self.assertRaises(ErrorCorreo) as ctx:
                enviar_correo(self.datos, "a")
            self.assertEqual(ctx.exception.transitorio, transitorio)

    @patch("notificaciones.resend_client.requests.post")
    def test_respuesta_aceptada_sin_id_se_considera_indeterminada(self, http):
        for contenido in ({}, {"id": None}, {"id": ""}):
            http.return_value = Mock(status_code=200, json=Mock(return_value=contenido))
            with self.assertRaises(ErrorCorreo) as ctx:
                enviar_correo(self.datos, "a")
            self.assertTrue(ctx.exception.transitorio)

    @patch("notificaciones.resend_client.requests.post")
    def test_placeholder_no_hace_peticion(self, http):
        with override_settings(RESEND_API_KEY="REEMPLAZAR_CON_TU_API_KEY_DE_RESEND"), self.assertRaises(ErrorCorreo):
            enviar_correo(self.datos, "a")
        http.assert_not_called()

    @patch("notificaciones.resend_client.requests.post")
    def test_destinatario_invalido_no_hace_peticion(self, http):
        with self.assertRaises(ErrorCorreo):
            enviar_correo({**self.datos, "to": ["no-es-correo"]}, "a")
        http.assert_not_called()
