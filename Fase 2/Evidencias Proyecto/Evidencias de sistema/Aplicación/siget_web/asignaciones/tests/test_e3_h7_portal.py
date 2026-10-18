"""Pruebas del formulario y flujo web E3-H7, sin acceso a base de datos."""

from types import SimpleNamespace
from unittest.mock import patch

from django.http import HttpResponse
from django.test import Client, SimpleTestCase, override_settings
from django.urls import include, path, resolve, reverse
from rest_framework.exceptions import ValidationError

from activos.models import CategoriaActivo
from asignaciones.forms import SolicitudAsignacionForm
from asignaciones.models import SolicitudAsignacion
from asignaciones.services import ESTADO_ACTIVO_DISPONIBLE
from usuarios.models import Usuario
from usuarios.services import ROL_USUARIO_SOLICITANTE


# Enrutamiento aislado para las pruebas de las vistas de la Etapa 2.
urlpatterns = [
    path("solicitudes/", include("asignaciones.web_urls")),
    path("", include("usuarios.urls")),
    path("", lambda request: HttpResponse("Inicio"), name="inicio"),
]


class SolicitudAsignacionFormTests(SimpleTestCase):
    def setUp(self):
        self.categoria = CategoriaActivo(id_categoria=1, nombre="Notebook")

    def test_construir_formulario_no_consulta_la_base_de_datos(self):
        form = SolicitudAsignacionForm()

        self.assertFalse(form.is_bound)
        self.assertEqual(set(form.fields), {"id_categoria", "motivo"})
        self.assertTrue(form.campo_categoria.required)
        self.assertTrue(form.fields["motivo"].required)

    def test_selector_filtra_disponibilidad_y_ordena_categorias_sin_duplicarlas(self):
        # Se inspecciona el SQL generado, sin ejecutarlo. IN evita repetir una
        # categoría aunque existan varios activos disponibles de esa categoría.
        queryset = SolicitudAsignacionForm().campo_categoria.queryset
        assert queryset is not None
        sql, params = queryset.query.sql_with_params()

        self.assertIn(ESTADO_ACTIVO_DISPONIBLE, params)
        self.assertIn('"activo"', sql)
        self.assertIn('"modelo_activo"', sql)
        self.assertIn('"estado_activo"', sql)
        self.assertIn(" IN (SELECT ", sql)
        self.assertEqual(queryset.query.order_by, ("nombre",))

    def test_categoria_disponible_y_motivo_validos(self):
        form = SolicitudAsignacionForm(
            data={"id_categoria": "1", "motivo": "  Trabajo de desarrollo  "},
        )
        with patch.object(
            form.campo_categoria.queryset, "get", return_value=self.categoria,
        ) as obtener:
            self.assertTrue(form.is_valid(), form.errors)

        obtener.assert_called_once_with(pk="1")
        self.assertEqual(form.cleaned_data["id_categoria"], self.categoria)
        self.assertEqual(form.cleaned_data["motivo"], "Trabajo de desarrollo")

    def test_campos_obligatorios(self):
        form = SolicitudAsignacionForm(data={})

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors.as_data()["id_categoria"][0].code, "required")
        self.assertEqual(form.errors.as_data()["motivo"][0].code, "required")

    def test_motivo_vacio_o_solo_espacios(self):
        for motivo in ("", "   \n\t"):
            with self.subTest(motivo=motivo):
                form = SolicitudAsignacionForm(
                    data={"id_categoria": "1", "motivo": motivo},
                )
                with patch.object(
                    form.campo_categoria.queryset, "get", return_value=self.categoria,
                ):
                    self.assertFalse(form.is_valid())
                self.assertEqual(form.errors.as_data()["motivo"][0].code, "required")

    def test_categoria_inexistente_o_sin_disponibilidad(self):
        # Ambos casos quedan fuera del queryset permitido por el selector.
        for categoria in ("99999", "2"):
            with self.subTest(categoria=categoria):
                form = SolicitudAsignacionForm(
                    data={"id_categoria": categoria, "motivo": "Necesito equipo"},
                )
                with patch.object(
                    form.campo_categoria.queryset,
                    "get",
                    side_effect=CategoriaActivo.DoesNotExist,
                ):
                    self.assertFalse(form.is_valid())
                self.assertEqual(
                    form.errors.as_data()["id_categoria"][0].code, "invalid_choice",
                )
                self.assertEqual(form.data["motivo"], "Necesito equipo")

    def test_identificador_de_categoria_malformado(self):
        form = SolicitudAsignacionForm(
            data={"id_categoria": "no-es-un-id", "motivo": "Necesito equipo"},
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors.as_data()["id_categoria"][0].code, "invalid_choice")

    def test_sin_categorias_disponibles_rechaza_seleccion(self):
        form = SolicitudAsignacionForm(
            data={"id_categoria": "1", "motivo": "Necesito equipo"},
        )
        form.campo_categoria.queryset = CategoriaActivo.objects.none()

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors.as_data()["id_categoria"][0].code, "invalid_choice")


@override_settings(ROOT_URLCONF=__name__)
class SolicitudAsignacionWebTests(SimpleTestCase):
    def setUp(self):
        self.usuario = Usuario(
            id_usuario=3, nombres="Ana", apellidos="Pérez", activo=True,
        )
        self.categoria = CategoriaActivo(id_categoria=1, nombre="Notebook")
        self.solicitud = SimpleNamespace(
            pk=100,
            id_solicitud=100,
            id_categoria=self.categoria,
            id_estado_solicitud=SimpleNamespace(nombre="Pendiente"),
        )
        self.hay_disponibilidad = True
        self.categoria_valida = True
        self.url = reverse("asignaciones_web:solicitar")
        self.confirmacion = reverse("asignaciones_web:confirmacion", kwargs={"pk": 100})

        self.obtener_usuario = self.parchear(
            "asignaciones.web_views.obtener_usuario_actual", return_value=self.usuario,
        )
        self.tiene_rol = self.parchear(
            "asignaciones.web_views.usuario_tiene_rol", return_value=True,
        )
        self.crear = self.parchear(
            "asignaciones.web_views.crear_solicitud_asignacion", return_value=self.solicitud,
        )
        self.parchear(
            "asignaciones.web_views.SolicitudAsignacionForm", side_effect=self.formulario,
        )
        # El queryset real permite que get_object_or_404 conserve su semántica;
        # solo su consulta get se simula.
        self.solicitudes = SolicitudAsignacion.objects.none()
        self.seleccionar = self.parchear(
            "asignaciones.web_views.SolicitudAsignacion.objects.select_related",
            return_value=self.solicitudes,
        )
        consulta = patch.object(self.solicitudes, "get", return_value=self.solicitud)
        self.consultar = consulta.start()
        self.addCleanup(consulta.stop)

    def parchear(self, target, **kwargs):
        parche = patch(target, **kwargs)
        resultado = parche.start()
        self.addCleanup(parche.stop)
        return resultado

    def formulario(self, data=None):
        # Se valida con el formulario real. Se simulan las lecturas del catálogo
        # para mantener SimpleTestCase sin PostgreSQL.
        form = SolicitudAsignacionForm(data=data)
        campo = form.campo_categoria
        campo.queryset = CategoriaActivo.objects.none()
        opciones = [("", "Seleccione una categoría")]
        if self.hay_disponibilidad:
            opciones.append(("1", "Notebook"))
        campo.choices = opciones
        existe = patch.object(
            campo.queryset, "exists", side_effect=lambda: self.hay_disponibilidad,
        )
        existe.start()
        self.addCleanup(existe.stop)
        consulta = patch.object(campo.queryset, "get")
        obtener = consulta.start()
        self.addCleanup(consulta.stop)
        if self.categoria_valida:
            obtener.return_value = self.categoria
        else:
            obtener.side_effect = CategoriaActivo.DoesNotExist
        return form

    def test_get_muestra_formulario_categoria_y_csrf(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "asignaciones/solicitar.html")
        self.assertContains(response, "Notebook")
        self.assertContains(response, 'name="motivo"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, "css/siget.css")
        self.tiene_rol.assert_called_once_with(self.usuario, ROL_USUARIO_SOLICITANTE)
        self.crear.assert_not_called()

    def test_get_sin_disponibilidad_informa_y_deshabilita_envio(self):
        self.hay_disponibilidad = False

        response = self.client.get(self.url)

        self.assertContains(response, "Actualmente no hay categorías con equipos disponibles.")
        self.assertContains(response, " disabled")
        self.assertNotContains(response, "Notebook")
        self.crear.assert_not_called()

    def test_anonimo_o_usuario_inactivo_no_accede_a_ninguna_vista(self):
        for usuario in (None, Usuario(id_usuario=3, activo=False)):
            self.obtener_usuario.return_value = usuario
            for url in (self.url, self.confirmacion):
                with self.subTest(usuario=usuario, url=url):
                    self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(self.url, {}).status_code, 403)
        self.crear.assert_not_called()
        self.consultar.assert_not_called()

    def test_sin_rol_solicitante_no_accede_ni_crea(self):
        self.tiene_rol.return_value = False

        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.get(self.confirmacion).status_code, 403)
        self.assertEqual(self.client.post(self.url, {}).status_code, 403)
        self.crear.assert_not_called()
        self.consultar.assert_not_called()

    def test_post_valido_reutiliza_servicio_y_redirige(self):
        response = self.client.post(
            self.url,
            {"id_categoria": "1", "motivo": "  Trabajo remoto  ",
             "id_usuario": "999", "id_estado_solicitud": "999"},
            REMOTE_ADDR="127.0.0.1",
        )

        self.assertRedirects(response, self.confirmacion, fetch_redirect_response=False)
        self.crear.assert_called_once_with(
            usuario=self.usuario, id_categoria=1, motivo="Trabajo remoto", ip_origen="127.0.0.1",
        )

    def test_post_invalido_muestra_errores_sin_crear(self):
        response = self.client.post(self.url, {"motivo": "  "})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Seleccione una categoría de equipo.")
        self.assertContains(response, "El motivo de la solicitud es obligatorio.")
        self.crear.assert_not_called()

    def test_categoria_fuera_del_catalogo_conserva_motivo(self):
        self.categoria_valida = False

        response = self.client.post(self.url, {"id_categoria": "999", "motivo": "Trabajo remoto"})

        self.assertContains(response, "Seleccione una categoría con equipos disponibles.")
        self.assertContains(response, "Trabajo remoto")
        self.crear.assert_not_called()

    def test_errores_del_servicio_se_muestran_y_conservan_datos(self):
        for detalle in (
            {"detail": "Actualmente no existe disponibilidad."},
            {"detail": "Ya existe una solicitud activa."},
            {"motivo": ["El motivo no es válido."]},
            ["No se pudo validar la solicitud."],
        ):
            with self.subTest(detalle=detalle):
                self.crear.side_effect = ValidationError(detalle)
                response = self.client.post(
                    self.url, {"id_categoria": "1", "motivo": "Trabajo remoto"},
                )
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "asignaciones/solicitar.html")
                self.assertTrue(response.context["form"].errors)
                mensajes = list(detalle.values())[0] if isinstance(detalle, dict) else detalle
                mensaje = mensajes[0] if isinstance(mensajes, list) else mensajes
                self.assertContains(response, mensaje)
                self.assertContains(response, "Trabajo remoto")
                self.assertContains(response, 'value="1" selected')

    def test_perdida_de_stock_entre_formulario_y_servicio(self):
        def sin_stock(**kwargs):
            self.hay_disponibilidad = False
            raise ValidationError({"detail": "Actualmente no existe disponibilidad."})

        self.crear.side_effect = sin_stock
        response = self.client.post(self.url, {"id_categoria": "1", "motivo": "Trabajo remoto"})

        self.assertContains(response, "Actualmente no existe disponibilidad.")
        self.assertContains(response, "Trabajo remoto")
        self.assertContains(response, "Actualmente no hay categorías con equipos disponibles.")
        self.assertContains(response, " disabled")

    def test_csrf_ausente_o_invalido_no_invoca_servicio(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.get(self.url)
        datos = {"id_categoria": "1", "motivo": "Trabajo remoto"}

        self.assertEqual(cliente.post(self.url, datos).status_code, 403)
        self.assertEqual(
            cliente.post(self.url, datos, HTTP_X_CSRFTOKEN="invalido").status_code, 403,
        )
        self.crear.assert_not_called()

    def test_csrf_valido_permite_envio(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.get(self.url)

        response = cliente.post(
            self.url,
            {"id_categoria": "1", "motivo": "Trabajo remoto"},
            HTTP_X_CSRFTOKEN=cliente.cookies["csrftoken"].value,
        )

        self.assertRedirects(response, self.confirmacion, fetch_redirect_response=False)
        self.crear.assert_called_once()

    def test_confirmacion_propia_muestra_identificador_categoria_y_estado(self):
        response = self.client.get(self.confirmacion)

        self.assertTemplateUsed(response, "asignaciones/confirmacion.html")
        self.assertContains(response, "100")
        self.assertContains(response, "Notebook")
        self.assertContains(response, "Pendiente")
        self.consultar.assert_called_once_with(pk=100, id_usuario=self.usuario)
        self.crear.assert_not_called()

    def test_confirmacion_ajena_o_inexistente_responde_404(self):
        self.consultar.side_effect = SolicitudAsignacion.DoesNotExist

        self.assertEqual(self.client.get(self.confirmacion).status_code, 404)
        self.consultar.assert_called_once_with(pk=100, id_usuario=self.usuario)
        self.crear.assert_not_called()

    def test_actualizar_confirmacion_no_crea_otra_solicitud(self):
        for _ in range(2):
            self.assertEqual(self.client.get(self.confirmacion).status_code, 200)
        self.crear.assert_not_called()

    def test_metodos_no_admitidos(self):
        self.assertEqual(self.client.put(self.url).status_code, 405)
        self.assertEqual(self.client.post(self.confirmacion).status_code, 405)
        self.crear.assert_not_called()


@override_settings(ROOT_URLCONF="siget.urls")
class SolicitudAsignacionIntegracionPortalTests(SimpleTestCase):
    """Enrutamiento y navegación reales, con lecturas de negocio simuladas."""

    def test_ruta_real_del_formulario_conserva_namespace(self):
        from asignaciones.web_views import solicitar_equipo

        url = reverse("asignaciones_web:solicitar")
        coincidencia = resolve(url)

        self.assertEqual(url, "/solicitudes/nueva/")
        self.assertEqual(coincidencia.namespace, "asignaciones_web")
        self.assertIs(coincidencia.func, solicitar_equipo)

    def test_ruta_real_de_confirmacion_recibe_identificador(self):
        from asignaciones.web_views import confirmacion_solicitud

        url = reverse("asignaciones_web:confirmacion", kwargs={"pk": 100})
        coincidencia = resolve(url)

        self.assertEqual(url, "/solicitudes/100/confirmacion/")
        self.assertEqual(coincidencia.namespace, "asignaciones_web")
        self.assertEqual(coincidencia.kwargs, {"pk": 100})
        self.assertIs(coincidencia.func, confirmacion_solicitud)

    def test_portal_enlaza_al_formulario_accesible(self):
        usuario = Usuario(id_usuario=3, nombres="Ana", apellidos="Pérez", activo=True)
        url = reverse("asignaciones_web:solicitar")
        form = SolicitudAsignacionForm()
        form.campo_categoria.queryset = CategoriaActivo.objects.none()

        with (
            patch("usuarios.views.obtener_usuario_actual", return_value=usuario),
            patch("usuarios.views.usuario_tiene_rol", return_value=True),
            patch("asignaciones.web_views.obtener_usuario_actual", return_value=usuario),
            patch("asignaciones.web_views.usuario_tiene_rol", return_value=True),
            patch("asignaciones.web_views.SolicitudAsignacionForm", return_value=form),
            patch("asignaciones.web_views.crear_solicitud_asignacion") as crear,
        ):
            inicio = self.client.get(reverse("inicio"))
            self.assertEqual(inicio.status_code, 200)
            self.assertTemplateUsed(inicio, "usuarios/inicio.html")
            self.assertInHTML(
                f'<a href="{url}"><span>Solicitudes</span></a>',
                inicio.content.decode(),
            )

            formulario = self.client.get(url)
            self.assertEqual(formulario.status_code, 200)
            self.assertTemplateUsed(formulario, "asignaciones/solicitar.html")
            self.assertContains(formulario, 'name="csrfmiddlewaretoken"')
            crear.assert_not_called()

    def test_rutas_api_de_solicitudes_conservan_destinos(self):
        from asignaciones.views import (
            SolicitudAsignacionAprobarView,
            SolicitudAsignacionEntregarView,
            SolicitudAsignacionListCreateView,
        )

        for url, vista in (
            ("/api/solicitudes-asignacion/", SolicitudAsignacionListCreateView),
            ("/api/solicitudes-asignacion/100/aprobar/", SolicitudAsignacionAprobarView),
            ("/api/solicitudes-asignacion/100/entregar/", SolicitudAsignacionEntregarView),
        ):
            with self.subTest(url=url):
                self.assertIs(resolve(url).func.view_class, vista)
