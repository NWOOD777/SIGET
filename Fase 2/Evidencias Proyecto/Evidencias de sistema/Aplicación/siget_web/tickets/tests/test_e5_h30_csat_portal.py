"""Pruebas unitarias de formulario, serializador y portal web para E5-H30 (CSAT)."""

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.http import HttpResponse
from django.test import Client, SimpleTestCase, override_settings
from django.urls import include, path, resolve, reverse

from tickets.forms import EvaluacionCSATForm
from tickets.models import EvaluacionCSAT, Ticket
from tickets.serializers import EvaluacionCSATCreateSerializer
from tickets.services import ESTADO_TICKET_CERRADO
from usuarios.models import Usuario
from usuarios.services import ROL_USUARIO_SOLICITANTE

urlpatterns = [
    path("solicitudes/", include("asignaciones.web_urls")),
    path("tickets/", include("tickets.web_urls")),
    path("", include("usuarios.urls")),
    path("", lambda request: HttpResponse("Inicio"), name="inicio"),
]


class EvaluacionCSATFormTests(SimpleTestCase):
    def test_solo_expone_calificacion_estrellas_y_comentario(self):
        form = EvaluacionCSATForm()

        self.assertFalse(form.is_bound)
        self.assertEqual(set(form.fields), {"calificacion_estrellas", "comentario"})
        self.assertTrue(form.fields["calificacion_estrellas"].required)
        self.assertFalse(form.fields["comentario"].required)

    def test_valores_limite_e_intermedios_validos_con_y_sin_comentario(self):
        for puntuacion in (1, 2, 3, 4, 5, "1", "5", " 4 "):
            with self.subTest(puntuacion=puntuacion):
                form = EvaluacionCSATForm(data={"calificacion_estrellas": puntuacion})
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.cleaned_data["calificacion_estrellas"], int(str(puntuacion).strip()))
                self.assertIsNone(form.cleaned_data["comentario"])

        form_con_comentario = EvaluacionCSATForm(
            data={
                "calificacion_estrellas": "5",
                "comentario": "  Excelente atención.\nResolvieron rápido.  ",
            }
        )
        self.assertTrue(form_con_comentario.is_valid(), form_con_comentario.errors)
        self.assertEqual(form_con_comentario.cleaned_data["calificacion_estrellas"], 5)
        self.assertEqual(
            form_con_comentario.cleaned_data["comentario"],
            "Excelente atención.\nResolvieron rápido.",
        )

    def test_comentario_vacio_o_solo_espacios_se_normaliza_a_none(self):
        for comentario in ("", "   ", "\n\t  "):
            with self.subTest(comentario=repr(comentario)):
                form = EvaluacionCSATForm(
                    data={"calificacion_estrellas": "4", "comentario": comentario}
                )
                self.assertTrue(form.is_valid(), form.errors)
                self.assertIsNone(form.cleaned_data["comentario"])

    def test_rechaza_puntuaciones_ausentes_booleanas_decimales_y_fuera_de_rango(self):
        casos_invalidos = (
            {},
            {"calificacion_estrellas": None},
            {"calificacion_estrellas": ""},
            {"calificacion_estrellas": "   "},
            {"calificacion_estrellas": True},
            {"calificacion_estrellas": False},
            {"calificacion_estrellas": 0},
            {"calificacion_estrellas": 6},
            {"calificacion_estrellas": -1},
            {"calificacion_estrellas": 3.0},
            {"calificacion_estrellas": 3.5},
            {"calificacion_estrellas": Decimal("3.0")},
            {"calificacion_estrellas": Decimal("4.5")},
            {"calificacion_estrellas": "3.0"},
            {"calificacion_estrellas": "3,5"},
            {"calificacion_estrellas": "cinco"},
        )
        for datos in casos_invalidos:
            with self.subTest(datos=datos):
                form = EvaluacionCSATForm(data=datos)
                self.assertFalse(form.is_valid())
                self.assertIn("calificacion_estrellas", form.errors)

    def test_ignora_campos_manipulados(self):
        form = EvaluacionCSATForm(
            data={
                "calificacion_estrellas": "5",
                "comentario": "Todo bien",
                "id_ticket": "999",
                "id_usuario": "999",
                "id_tecnico_asignado": "999",
                "fecha_evaluacion": "2020-01-01T00:00:00Z",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(set(form.cleaned_data), {"calificacion_estrellas", "comentario"})


class EvaluacionCSATSerializerTests(SimpleTestCase):
    def test_acepta_enteros_y_cadenas_de_formulario_entre_1_y_5(self):
        for valor in (1, 3, 5, "1", "5"):
            with self.subTest(valor=valor):
                serializer = EvaluacionCSATCreateSerializer(
                    data={"calificacion_estrellas": valor, "comentario": "  Buen soporte "}
                )
                self.assertTrue(serializer.is_valid(), serializer.errors)
                datos = serializer.validated_data
                assert isinstance(datos, dict)
                self.assertEqual(datos["calificacion_estrellas"], int(valor))
                self.assertEqual(datos["comentario"], "Buen soporte")

    def test_rechaza_booleanos_decimales_nulos_y_fuera_de_rango(self):
        for valor in (None, "", True, False, 0, 6, -3, 3.0, 4.2, Decimal("3.0"), "3.0", "abc", [5]):
            with self.subTest(valor=repr(valor)):
                serializer = EvaluacionCSATCreateSerializer(
                    data={"calificacion_estrellas": valor}
                )
                self.assertFalse(serializer.is_valid())
                self.assertIn("calificacion_estrellas", serializer.errors)

    def test_rechaza_comentario_no_textual(self):
        for comentario in (123, ["texto"], {"a": 1}):
            with self.subTest(comentario=type(comentario).__name__):
                serializer = EvaluacionCSATCreateSerializer(
                    data={"calificacion_estrellas": 4, "comentario": comentario}
                )
                self.assertFalse(serializer.is_valid())
                self.assertIn("comentario", serializer.errors)


@override_settings(ROOT_URLCONF=__name__)
class PortalCSATWebUnitTests(SimpleTestCase):
    def setUp(self):
        self.client_csrf = Client(enforce_csrf_checks=True)
        self.solicitante = Usuario(
            id_usuario=7,
            nombres="Ana",
            apellidos="Pérez",
            correo="ana@siget.test",
            rut="12345678-9",
            activo=True,
        )

    def _ticket(self, estado=ESTADO_TICKET_CERRADO):
        instancia = Ticket(
            id_ticket=42,
            codigo_ticket="TCK-2026-0042",
            asunto="Problema con correo",
            descripcion="No sincroniza bandeja",
            fecha_creacion=datetime(2026, 10, 20, 14, 30, tzinfo=timezone.utc),
        )
        instancia._state.fields_cache["id_estado_ticket"] = SimpleNamespace(nombre=estado)
        instancia._state.fields_cache["id_prioridad"] = SimpleNamespace(nombre="Media")
        instancia._state.fields_cache["id_activo"] = None
        instancia._state.fields_cache["id_tecnico_asignado"] = SimpleNamespace(
            nombres="Carlos", apellidos="Soto"
        )
        return instancia

    def test_rutas_web_detalle_y_csat_resuelven(self):
        self.assertEqual(reverse("tickets_web:detalle", args=[42]), "/tickets/42/")
        self.assertEqual(reverse("tickets_web:evaluar_csat", args=[42]), "/tickets/42/csat/")
        self.assertEqual(resolve("/tickets/42/").view_name, "tickets_web:detalle")
        self.assertEqual(resolve("/tickets/42/csat/").view_name, "tickets_web:evaluar_csat")

    def test_detalle_ticket_cerrado_sin_evaluacion_muestra_formulario_csat(self):
        ticket = self._ticket(ESTADO_TICKET_CERRADO)
        with (
            patch("tickets.web_views.obtener_usuario_actual", return_value=self.solicitante),
            patch(
                "tickets.web_views.usuario_tiene_rol",
                side_effect=lambda u, r: r == ROL_USUARIO_SOLICITANTE,
            ),
            patch("tickets.web_views._ticket_propio", return_value=ticket),
            patch("tickets.web_views.obtener_evaluacion_csat_ticket", return_value=None),
        ):
            response = self.client.get("/tickets/42/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Calificación de servicio (CSAT)")
        self.assertContains(response, 'name="calificacion_estrellas"')
        self.assertContains(response, 'name="comentario"')
        self.assertContains(response, "Enviar calificación")

    def test_detalle_ticket_no_cerrado_muestra_explicacion_y_oculta_formulario(self):
        for estado in ("Abierto", "En Proceso", "En Espera", "Resuelto"):
            with self.subTest(estado=estado):
                ticket = self._ticket(estado)
                with (
                    patch("tickets.web_views.obtener_usuario_actual", return_value=self.solicitante),
                    patch(
                        "tickets.web_views.usuario_tiene_rol",
                        side_effect=lambda u, r: r == ROL_USUARIO_SOLICITANTE,
                    ),
                    patch("tickets.web_views._ticket_propio", return_value=ticket),
                    patch("tickets.web_views.obtener_evaluacion_csat_ticket", return_value=None),
                ):
                    response = self.client.get("/tickets/42/")

                self.assertEqual(response.status_code, 200)
                self.assertContains(
                    response,
                    "La calificación de satisfacción estará disponible únicamente cuando el ticket haya finalizado su atención",
                )
                self.assertNotContains(response, 'name="calificacion_estrellas"')

    def test_detalle_ticket_evaluado_muestra_solo_lectura_y_escapa_comentario(self):
        ticket = self._ticket(ESTADO_TICKET_CERRADO)
        evaluacion = EvaluacionCSAT(
            id_evaluacion=9,
            calificacion_estrellas=4,
            comentario='<script>alert("xss")</script>\nMuy buena atención',
            fecha_evaluacion=datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc),
        )
        with (
            patch("tickets.web_views.obtener_usuario_actual", return_value=self.solicitante),
            patch(
                "tickets.web_views.usuario_tiene_rol",
                side_effect=lambda u, r: r == ROL_USUARIO_SOLICITANTE,
            ),
            patch("tickets.web_views._ticket_propio", return_value=ticket),
            patch("tickets.web_views.obtener_evaluacion_csat_ticket", return_value=evaluacion),
        ):
            response = self.client.get("/tickets/42/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Evaluación registrada en modo de solo lectura.")
        self.assertContains(response, "4 de 5 estrellas")
        self.assertContains(response, "&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;")
        self.assertNotContains(response, '<script>alert("xss")</script>')
        self.assertNotContains(response, 'name="calificacion_estrellas"')

    def test_envio_post_sin_csrf_es_rechazado_con_403(self):
        response = self.client_csrf.post(
            "/tickets/42/",
            data={"calificacion_estrellas": "5", "comentario": "Gracias"},
        )
        self.assertEqual(response.status_code, 403)
