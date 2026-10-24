"""Pruebas unitarias del formulario y flujo web, sin base de datos."""

from types import SimpleNamespace
from unittest.mock import patch

from django.http import HttpResponse
from django.test import Client, SimpleTestCase, override_settings
from django.urls import include, path, resolve, reverse
from rest_framework.exceptions import ValidationError

from activos.models import Activo, ModeloActivo
from tickets.forms import TicketCreateForm
from tickets.models import Ticket
from usuarios.models import Usuario
from usuarios.services import ROL_USUARIO_SOLICITANTE

# Enrutamiento aislado para las pruebas de vistas web.
urlpatterns = [
    path("solicitudes/", include("asignaciones.web_urls")),
    path("tickets/", include("tickets.web_urls")),
    path("", include("usuarios.urls")),
    path("", lambda request: HttpResponse("Inicio"), name="inicio"),
]


class TicketCreateFormTests(SimpleTestCase):
    def test_solo_expone_asunto_descripcion_y_activo_opcional(self):
        form = TicketCreateForm()

        self.assertFalse(form.is_bound)
        self.assertEqual(set(form.fields), {"asunto", "descripcion", "id_activo"})
        self.assertFalse(form.campo_activo.required)
        self.assertEqual(form.campo_activo.empty_label, "Sin equipo específico")

    def test_entrada_valida(self):
        form = TicketCreateForm(
            data={"asunto": "Problema de acceso", "descripcion": "No puedo acceder al sistema."},
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data, {
            "asunto": "Problema de acceso", "descripcion": "No puedo acceder al sistema.", "id_activo": None,
        })

    def test_campos_ausentes_vacios_o_solo_espacios(self):
        for campo in ("asunto", "descripcion"):
            for valor in (None, "", "   \n\t"):
                with self.subTest(campo=campo, valor=valor):
                    datos = {"asunto": "Problema de acceso", "descripcion": "No puedo acceder."}
                    if valor is None:
                        del datos[campo]
                    else:
                        datos[campo] = valor
                    form = TicketCreateForm(data=datos)

                    self.assertFalse(form.is_valid())
                    self.assertEqual(set(form.errors), {campo})
                    self.assertEqual(form.errors.as_data()[campo][0].code, "required")

    def test_formulario_vacio_rechaza_ambos_campos(self):
        form = TicketCreateForm(data={})

        self.assertFalse(form.is_valid())
        self.assertEqual(set(form.errors), {"asunto", "descripcion"})

    def test_limpia_espacios_exteriores_y_preserva_contenido(self):
        form = TicketCreateForm(data={
            "asunto": "  Falla en teclado  ",
            "descripcion": " \nPrimera línea.\nSegunda línea con  espacios.\t ",
        })

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["asunto"], "Falla en teclado")
        self.assertEqual(
            form.cleaned_data["descripcion"], "Primera línea.\nSegunda línea con  espacios.",
        )

    def test_asunto_de_200_caracteres_es_valido(self):
        form = TicketCreateForm(data={"asunto": "á" * 200, "descripcion": "Detalle"})

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(len(form.cleaned_data["asunto"]), 200)

    def test_asunto_de_201_caracteres_es_rechazado(self):
        form = TicketCreateForm(data={"asunto": "a" * 201, "descripcion": "Detalle"})

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors.as_data()["asunto"][0].code, "max_length")

    def test_limite_del_asunto_se_aplica_despues_de_limpiar_espacios(self):
        form = TicketCreateForm(data={"asunto": "  " + "a" * 200 + "  ", "descripcion": "Detalle"})

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(len(form.cleaned_data["asunto"]), 200)

    def test_campos_adicionales_no_entran_en_los_datos_validados(self):
        form = TicketCreateForm(data={
            "asunto": "Problema de acceso",
            "descripcion": "No puedo acceder.",
            "id_usuario_solicitante": "999",
            "id_estado_ticket": "999",
            "codigo_ticket": "TCK-MANUAL",
            "id_tecnico_asignado": "999",
            "id_prioridad": "999",
        })

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(set(form.cleaned_data), {"asunto", "descripcion", "id_activo"})
        self.assertIsNone(form.cleaned_data["id_activo"])

    def test_etiqueta_del_activo_incluye_codigo_y_modelo(self):
        activo = Activo(id_activo=10, codigo_inventario="ACT-0010", id_modelo=ModeloActivo(nombre="Notebook de prueba"))
        self.assertEqual(
            TicketCreateForm().campo_activo.label_from_instance(activo),
            "ACT-0010 — Notebook de prueba",
        )

    def test_sin_usuario_no_acepta_identificadores_de_activos(self):
        form = TicketCreateForm(data={"asunto": "Falla", "descripcion": "Detalle", "id_activo": "10"})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors.as_data()["id_activo"][0].code, "invalid_choice")

    def test_activo_permitido_se_devuelve_como_instancia_validada(self):
        usuario = Usuario(id_usuario=3, activo=True)
        activo = Activo(id_activo=10)
        form = TicketCreateForm(
            data={"asunto": "Falla", "descripcion": "Detalle", "id_activo": "10"}, usuario=usuario,
        )
        with patch.object(form.campo_activo.queryset, "get", return_value=activo) as obtener:
            self.assertTrue(form.is_valid(), form.errors)
        obtener.assert_called_once_with(pk="10")
        self.assertEqual(form.cleaned_data["id_activo"], activo)

    def test_activo_no_permitido_o_malformado_es_rechazado(self):
        for identificador in ("10", "999999", "no-es-un-id"):
            with self.subTest(identificador=identificador):
                form = TicketCreateForm(data={"asunto": "Falla", "descripcion": "Detalle", "id_activo": identificador})
                self.assertFalse(form.is_valid())
                self.assertEqual(form.errors.as_data()["id_activo"][0].code, "invalid_choice")


@override_settings(ROOT_URLCONF=__name__, SESSION_ENGINE="django.contrib.sessions.backends.cache")
class TicketWebTests(SimpleTestCase):
    def setUp(self):
        self.usuario = Usuario(id_usuario=3, nombres="Ana", apellidos="Pérez", activo=True)
        self.ticket = SimpleNamespace(
            pk=50,
            codigo_ticket="TCK-0050",
            asunto="Problema de acceso",
            id_estado_ticket=SimpleNamespace(nombre="Abierto"),
            id_prioridad=SimpleNamespace(nombre="Medio"),
        )
        self.datos = {"asunto": "Problema de acceso", "descripcion": "No puedo acceder."}
        self.url = reverse("tickets_web:nuevo")
        self.confirmacion = reverse("tickets_web:confirmacion", kwargs={"pk": 50})
        self.obtener_usuario = self.parchear(
            "tickets.web_views.obtener_usuario_actual", return_value=self.usuario,
        )
        self.tiene_rol = self.parchear(
            "tickets.web_views.usuario_tiene_rol", return_value=True,
        )
        self.crear = self.parchear("tickets.web_views.crear_ticket", return_value=self.ticket)
        # El catálogo vacío se simula; los filtros reales se prueban en PostgreSQL.
        self.parchear("tickets.forms.Activo.objects.filter", return_value=Activo.objects.none())
        # get_object_or_404 usa un queryset real cuya lectura get está simulada.
        self.tickets = Ticket.objects.none()
        self.parchear(
            "tickets.web_views.Ticket.objects.select_related", return_value=self.tickets,
        )
        consulta = patch.object(self.tickets, "get", return_value=self.ticket)
        self.consultar = consulta.start()
        self.addCleanup(consulta.stop)

    def parchear(self, target, **kwargs):
        parche = patch(target, **kwargs)
        resultado = parche.start()
        self.addCleanup(parche.stop)
        return resultado

    def test_rutas_internas_y_namespace(self):
        from tickets.web_views import confirmacion_ticket, crear_ticket_web

        self.assertEqual(self.url, "/tickets/nuevo/")
        self.assertEqual(self.confirmacion, "/tickets/50/confirmacion/")
        self.assertIs(resolve(self.url).func, crear_ticket_web)
        self.assertIs(resolve(self.confirmacion).func, confirmacion_ticket)
        self.assertEqual(resolve(self.url).namespace, "tickets_web")

    def test_get_autorizado_muestra_formulario_y_csrf(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tickets/crear.html")
        self.assertIsInstance(response.context["form"], TicketCreateForm)
        self.assertContains(response, 'name="asunto"')
        self.assertContains(response, 'name="descripcion"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, "css/siget.css")
        self.tiene_rol.assert_called_once_with(self.usuario, ROL_USUARIO_SOLICITANTE)
        self.crear.assert_not_called()

    def test_formulario_no_expone_campos_controlados_por_el_servidor(self):
        response = self.client.get(self.url)

        for campo in (
            "id_usuario_solicitante", "id_estado_ticket", "codigo_ticket",
            "id_tecnico_asignado", "id_prioridad",
        ):
            with self.subTest(campo=campo):
                self.assertNotContains(response, f'name="{campo}"')

    def test_anonimo_no_accede_ni_crea(self):
        self.obtener_usuario.return_value = None

        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, self.datos).status_code, 403)
        self.assertEqual(self.client.get(self.confirmacion).status_code, 403)
        self.tiene_rol.assert_not_called()
        self.crear.assert_not_called()
        self.consultar.assert_not_called()

    def test_usuario_inactivo_no_accede_ni_crea(self):
        self.usuario.activo = False

        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, self.datos).status_code, 403)
        self.assertEqual(self.client.get(self.confirmacion).status_code, 403)
        self.tiene_rol.assert_not_called()
        self.crear.assert_not_called()
        self.consultar.assert_not_called()

    def test_usuario_sin_rol_solicitante_no_accede_ni_crea(self):
        self.tiene_rol.return_value = False

        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, self.datos).status_code, 403)
        self.assertEqual(self.client.get(self.confirmacion).status_code, 403)
        self.crear.assert_not_called()
        self.consultar.assert_not_called()

    def test_post_valido_reutiliza_servicio_y_redirige_a_confirmacion(self):
        response = self.client.post(
            self.url,
            {"asunto": "  Problema de acceso  ", "descripcion": "  No puedo acceder.  "},
            REMOTE_ADDR="127.0.0.1",
        )

        self.assertRedirects(response, self.confirmacion, fetch_redirect_response=False)
        self.crear.assert_called_once_with(
            solicitante=self.usuario,
            asunto="Problema de acceso",
            descripcion="No puedo acceder.",
            id_activo=None,
            ip_origen="127.0.0.1",
        )

    def test_post_manipulado_no_cambia_usuario_ni_campos_automaticos(self):
        response = self.client.post(self.url, {
            **self.datos,
            "id_usuario_solicitante": "999",
            "id_estado_ticket": "999",
            "codigo_ticket": "MANUAL",
            "id_tecnico_asignado": "999",
            "id_prioridad": "999",
        }, REMOTE_ADDR="127.0.0.1")

        self.assertRedirects(response, self.confirmacion, fetch_redirect_response=False)
        self.crear.assert_called_once_with(
            solicitante=self.usuario, **self.datos, id_activo=None, ip_origen="127.0.0.1",
        )

    def test_post_invalido_muestra_errores_y_conserva_descripcion(self):
        for asunto in ("", "   ", "a" * 201):
            with self.subTest(asunto=asunto):
                response = self.client.post(
                    self.url, {"asunto": asunto, "descripcion": "Detalle conservado"},
                )
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "tickets/crear.html")
                self.assertIn("asunto", response.context["form"].errors)
                self.assertContains(response, "Detalle conservado")
        self.crear.assert_not_called()

    def test_descripcion_invalida_conserva_asunto(self):
        response = self.client.post(self.url, {"asunto": "Problema de acceso", "descripcion": "  "})

        self.assertContains(response, "La descripción del ticket es obligatoria.")
        self.assertContains(response, "Problema de acceso")
        self.crear.assert_not_called()

    def test_errores_del_servicio_se_muestran_y_conservan_ambos_campos(self):
        for detalle, mensaje, campo in (
            ({"detail": "Ya existe un ticket activo."}, "Ya existe un ticket activo.", None),
            ({"asunto": ["Asunto inválido."]}, "Asunto inválido.", "asunto"),
            ({"descripcion": ["Descripción inválida."]}, "Descripción inválida.", "descripcion"),
            ({"id_prioridad": ["No hay prioridades configuradas."]}, "No hay prioridades configuradas.", None),
            (["Estado Abierto no configurado."], "Estado Abierto no configurado.", None),
        ):
            with self.subTest(detalle=detalle):
                self.crear.side_effect = ValidationError(detalle)
                response = self.client.post(self.url, self.datos)

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, mensaje)
                self.assertContains(response, "Problema de acceso")
                self.assertContains(response, "No puedo acceder.")
                if campo:
                    self.assertIn(campo, response.context["form"].errors)
                else:
                    self.assertTrue(response.context["form"].non_field_errors())

    def test_confirmacion_del_propietario_muestra_ticket(self):
        session = self.client.session
        session["ticket_recien_registrado"] = self.ticket.pk
        session.save()
        response = self.client.get(self.confirmacion)

        self.assertTemplateUsed(response, "tickets/confirmacion.html")
        for texto in ("TCK-0050", "Problema de acceso", "Abierto", "Medio"):
            self.assertContains(response, texto)
        self.consultar.assert_called_once_with(pk=50, id_usuario_solicitante=self.usuario)
        self.crear.assert_not_called()

    def test_confirmacion_ajena_o_inexistente_devuelve_404(self):
        self.consultar.side_effect = Ticket.DoesNotExist

        self.assertEqual(self.client.get(self.confirmacion).status_code, 404)
        self.consultar.assert_called_once_with(pk=50, id_usuario_solicitante=self.usuario)
        self.crear.assert_not_called()

    def test_actualizar_confirmacion_no_repite_creacion(self):
        for _ in range(2):
            self.assertRedirects(
                self.client.get(self.confirmacion),
                reverse("tickets_web:detalle", kwargs={"pk": self.ticket.pk}),
                fetch_redirect_response=False,
            )
        self.crear.assert_not_called()

    def test_csrf_ausente_invalido_u_origen_ajeno_bloquea_creacion(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.get(self.url)
        token = cliente.cookies["csrftoken"].value

        self.assertEqual(cliente.post(self.url, self.datos).status_code, 403)
        self.assertEqual(
            cliente.post(self.url, self.datos, HTTP_X_CSRFTOKEN="invalido").status_code, 403,
        )
        self.assertEqual(
            cliente.post(
                self.url, self.datos, HTTP_X_CSRFTOKEN=token,
                HTTP_ORIGIN="https://example.invalid",
            ).status_code,
            403,
        )
        self.crear.assert_not_called()

    def test_csrf_valido_permite_post_y_redireccion(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.get(self.url)

        response = cliente.post(
            self.url, self.datos, HTTP_X_CSRFTOKEN=cliente.cookies["csrftoken"].value,
        )

        self.assertRedirects(response, self.confirmacion, fetch_redirect_response=False)
        self.crear.assert_called_once()

    def test_metodos_no_admitidos_no_crean_ticket(self):
        self.assertEqual(self.client.put(self.url).status_code, 405)
        self.assertEqual(self.client.post(self.confirmacion).status_code, 405)
        self.crear.assert_not_called()

    def test_selector_opcional_visible_y_sin_activos_permite_ticket_general(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'name="id_activo"')
        self.assertContains(response, "Sin equipo específico")
        response = self.client.post(self.url, {**self.datos, "id_activo": ""})
        self.assertRedirects(response, self.confirmacion, fetch_redirect_response=False)
        self.assertIsNone(self.crear.call_args.kwargs["id_activo"])

    def test_id_de_activo_manipulado_se_rechaza_conservando_datos(self):
        for identificador in ("999", "-1", "no-es-un-id"):
            with self.subTest(identificador=identificador):
                response = self.client.post(self.url, {**self.datos, "id_activo": identificador})
                self.assertEqual(response.status_code, 200)
                self.assertIn("id_activo", response.context["form"].errors)
                self.assertContains(response, "Problema de acceso")
                self.assertContains(response, "No puedo acceder.")
        self.crear.assert_not_called()

    def test_activo_validado_se_envia_al_servicio(self):
        activo = Activo(id_activo=10)
        form = TicketCreateForm(data={**self.datos, "id_activo": "10"}, usuario=self.usuario)
        with (
            patch("tickets.web_views.TicketCreateForm", return_value=form) as construir,
            patch.object(form.campo_activo.queryset, "get", return_value=activo),
            patch("tickets.web_views.transaction.atomic"),
            patch("tickets.web_views.bloquear_operacion") as bloquear,
            patch("tickets.web_views.activos_reportables_por_usuario") as selector,
        ):
            selector.return_value.filter.return_value.exists.return_value = True
            response = self.client.post(self.url, {**self.datos, "id_activo": "10"})
        self.assertRedirects(response, self.confirmacion, fetch_redirect_response=False)
        self.assertEqual(construir.call_args.kwargs["usuario"], self.usuario)
        self.assertEqual(self.crear.call_args.kwargs["id_activo"], 10)
        self.assertEqual(self.crear.call_args.kwargs["solicitante"], self.usuario)
        bloquear.assert_called_once_with(70403, 10)
        selector.assert_called_once_with(self.usuario)

    def test_revalidacion_bajo_bloqueo_rechaza_activo_aunque_formulario_lo_acepto(self):
        activo = Activo(id_activo=10)
        form = TicketCreateForm(data={**self.datos, "id_activo": "10"}, usuario=self.usuario)
        with (
            patch("tickets.web_views.TicketCreateForm", return_value=form),
            patch.object(form.campo_activo.queryset, "get", return_value=activo),
            patch("tickets.web_views.transaction.atomic"),
            patch("tickets.web_views.bloquear_operacion") as bloquear,
            patch("tickets.web_views.activos_reportables_por_usuario") as selector,
        ):
            selector.return_value.filter.return_value.exists.return_value = False
            response = self.client.post(self.url, {**self.datos, "id_activo": "10"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "El equipo ya no tiene una asignación Activa a su nombre.")
        bloquear.assert_called_once_with(70403, 10)
        self.crear.assert_not_called()


@override_settings(ROOT_URLCONF="siget.urls", SESSION_ENGINE="django.contrib.sessions.backends.cache")
class TicketIntegracionPortalTests(SimpleTestCase):
    """Comprueba el enrutamiento real sin acceder a PostgreSQL ni Auth0."""

    def setUp(self):
        parche = patch("tickets.forms.Activo.objects.filter", return_value=Activo.objects.none())
        parche.start()
        self.addCleanup(parche.stop)

    def test_ruta_nuevo_resuelve_a_la_vista_web(self):
        from tickets.web_views import crear_ticket_web

        url = reverse("tickets_web:nuevo")
        coincidencia = resolve(url)

        self.assertEqual(url, "/tickets/nuevo/")
        self.assertEqual(coincidencia.view_name, "tickets_web:nuevo")
        self.assertIs(coincidencia.func, crear_ticket_web)

    def test_ruta_real_de_confirmacion_recibe_identificador(self):
        from tickets.web_views import confirmacion_ticket

        url = reverse("tickets_web:confirmacion", kwargs={"pk": 50})
        coincidencia = resolve(url)

        self.assertEqual(url, "/tickets/50/confirmacion/")
        self.assertEqual(coincidencia.view_name, "tickets_web:confirmacion")
        self.assertEqual(coincidencia.kwargs, {"pk": 50})
        self.assertIs(coincidencia.func, confirmacion_ticket)

    def test_portal_enlaza_al_formulario_real(self):
        usuario = Usuario(id_usuario=3, nombres="Ana", apellidos="Pérez", activo=True)
        url = reverse("tickets_web:nuevo")

        with (
            patch("usuarios.views.obtener_usuario_actual", return_value=usuario),
            patch("usuarios.views.usuario_tiene_rol", return_value=True),
            patch("usuarios.views.resumen_usuario", return_value={}),
            patch("tickets.web_views.obtener_usuario_actual", return_value=usuario),
            patch("tickets.web_views.usuario_tiene_rol", return_value=True),
            patch("tickets.web_views.crear_ticket") as crear,
        ):
            inicio = self.client.get(reverse("inicio"))
            self.assertEqual(inicio.status_code, 200)
            self.assertTemplateUsed(inicio, "usuarios/inicio.html")
            self.assertInHTML(
                f'<a href="{url}"><span>Soporte / Tickets</span></a>',
                inicio.content.decode(),
            )

            formulario = self.client.get(url)
            self.assertEqual(formulario.status_code, 200)
            self.assertTemplateUsed(formulario, "tickets/crear.html")
            self.assertContains(formulario, 'name="csrfmiddlewaretoken"')
            crear.assert_not_called()

    def test_post_real_redirige_a_confirmacion_del_propietario(self):
        usuario = Usuario(id_usuario=3, nombres="Ana", apellidos="Pérez", activo=True)
        ticket = SimpleNamespace(
            pk=50, codigo_ticket="TCK-0050", asunto="Problema de acceso",
            id_estado_ticket=SimpleNamespace(nombre="Abierto"),
            id_prioridad=SimpleNamespace(nombre="Medio"),
        )
        queryset = Ticket.objects.none()
        with (
            patch("tickets.web_views.obtener_usuario_actual", return_value=usuario),
            patch("tickets.web_views.usuario_tiene_rol", return_value=True),
            patch("tickets.web_views.crear_ticket", return_value=ticket) as crear,
            patch("tickets.web_views.Ticket.objects.select_related", return_value=queryset),
            patch.object(queryset, "get", return_value=ticket) as consultar,
        ):
            response = self.client.post(
                reverse("tickets_web:nuevo"),
                {"asunto": "Problema de acceso", "descripcion": "No puedo acceder."},
                follow=True,
            )

        self.assertEqual(response.redirect_chain, [
            (reverse("tickets_web:confirmacion", kwargs={"pk": 50}), 302),
        ])
        self.assertTemplateUsed(response, "tickets/confirmacion.html")
        self.assertContains(response, "TCK-0050")
        crear.assert_called_once()
        consultar.assert_called_once_with(pk=50, id_usuario_solicitante=usuario)

    def test_rutas_api_conservan_destinos_sin_conflictos_con_web(self):
        from tickets.views import (
            EstadoTicketListView,
            PrioridadListView,
            SLAListView,
            TicketDetailView,
            TicketListCreateView,
        )

        for url, vista in (
            ("/api/tickets/", TicketListCreateView),
            ("/api/tickets/50/", TicketDetailView),
            ("/api/tickets/estados/", EstadoTicketListView),
            ("/api/tickets/prioridades/", PrioridadListView),
            ("/api/tickets/sla/", SLAListView),
        ):
            with self.subTest(url=url):
                coincidencia = resolve(url)
                self.assertEqual(coincidencia.namespace, "")
                self.assertIs(coincidencia.func.view_class, vista)

        self.assertEqual(reverse("ticket-list-create"), "/api/tickets/")
        with (
            patch("usuarios.authentication.obtener_usuario_actual", return_value=None),
            patch("tickets.permissions.obtener_usuario_actual", return_value=None),
        ):
            # El endpoint sigue activo y exige autenticación, no responde 404.
            self.assertEqual(self.client.get("/api/tickets/").status_code, 403)
