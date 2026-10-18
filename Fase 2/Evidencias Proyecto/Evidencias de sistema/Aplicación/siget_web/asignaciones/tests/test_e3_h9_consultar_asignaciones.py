"""
Pruebas para E3-H9: Consultar asignaciones.
Cubre consulta general, búsqueda por usuario, búsqueda por equipo, resultados vacíos, alcance por rol y RBAC.
"""
from unittest.mock import patch

from rest_framework import status
from usuarios.services import ROL_ADMINISTRADOR, ROL_TECNICO, ROL_USUARIO_SOLICITANTE

from asignaciones.models import Asignacion, EstadoAsignacion
from asignaciones.views import AsignacionDetailView, AsignacionListCreateView, EstadoAsignacionListView
from .helpers import AsignacionesTestBase, crear_request_con_sesion, obtener_data_dict, obtener_data_list


class ConsultarAsignacionesE3H9Tests(AsignacionesTestBase):
    """
    Suite de pruebas correspondiente a E3-H9 — Consultar asignaciones.
    """

    def test_01_consulta_general_exitosa_por_administrador(self):
        """
        Escenario 1: Administrador consulta el listado de asignaciones. Retorna 200 OK con datos.
        """
        request = crear_request_con_sesion(
            self.factory,
            "GET",
            "/api/asignaciones/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
        )
        view = AsignacionListCreateView.as_view()

        with (
            patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.admin_user),
            patch("asignaciones.permissions.es_administrador", return_value=True),
            patch.object(Asignacion.objects, "select_related") as mock_sr,
        ):
            queryset = mock_sr.return_value.order_by.return_value
            queryset.__iter__.return_value = [self.asignacion_activa]
            queryset.__len__.return_value = 1

            response = view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = obtener_data_list(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id_asignacion"], 200)
        self.assertEqual(data[0]["estado"]["nombre"], "Activa")

    def test_02_busqueda_por_usuario(self):
        """
        Escenario 2: Administrador filtra por datos de usuario (nombre/correo/rut).
        """
        request = crear_request_con_sesion(
            self.factory,
            "GET",
            "/api/asignaciones/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
            data={"usuario": "solicitante@siget.cl"},
        )
        view = AsignacionListCreateView.as_view()

        with (
            patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.admin_user),
            patch("asignaciones.permissions.es_administrador", return_value=True),
            patch.object(Asignacion.objects, "select_related") as mock_sr,
        ):
            queryset = mock_sr.return_value.order_by.return_value
            queryset.filter.return_value = queryset
            queryset.__iter__.return_value = [self.asignacion_activa]
            queryset.__len__.return_value = 1

            response = view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        queryset.filter.assert_called()

    def test_03_busqueda_por_equipo(self):
        """
        Escenario 3: Administrador filtra por identificador del equipo (código de inventario o serie).
        """
        request = crear_request_con_sesion(
            self.factory,
            "GET",
            "/api/asignaciones/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
            data={"equipo": "ACT-0010"},
        )
        view = AsignacionListCreateView.as_view()

        with (
            patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.admin_user),
            patch("asignaciones.permissions.es_administrador", return_value=True),
            patch.object(Asignacion.objects, "select_related") as mock_sr,
        ):
            queryset = mock_sr.return_value.order_by.return_value
            queryset.filter.return_value = queryset
            queryset.__iter__.return_value = [self.asignacion_activa]
            queryset.__len__.return_value = 1

            response = view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        queryset.filter.assert_called()

    def test_04_asignaciones_no_encontradas_retorna_lista_vacia(self):
        """
        Escenario 4: Criterios de búsqueda sin coincidencia retornan lista vacía 200 OK.
        """
        request = crear_request_con_sesion(
            self.factory,
            "GET",
            "/api/asignaciones/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
            data={"equipo": "INEXISTENTE-999"},
        )
        view = AsignacionListCreateView.as_view()

        with (
            patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.admin_user),
            patch("asignaciones.permissions.es_administrador", return_value=True),
            patch.object(Asignacion.objects, "select_related") as mock_sr,
        ):
            queryset = mock_sr.return_value.order_by.return_value
            queryset.filter.return_value = queryset
            queryset.__iter__.return_value = []
            queryset.__len__.return_value = 0

            response = view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = obtener_data_list(response)
        self.assertEqual(len(data), 0)

    def test_05_usuario_solicitante_solo_ve_sus_propias_asignaciones(self):
        """
        Usuario solicitante consulta asignaciones: el sistema filtra automáticamente
        por su id_usuario.
        """
        request = crear_request_con_sesion(
            self.factory,
            "GET",
            "/api/asignaciones/",
            usuario_id=3,
            roles=[ROL_USUARIO_SOLICITANTE],
        )
        view = AsignacionListCreateView.as_view()

        with (
            patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.solicitante_user),
            patch("asignaciones.permissions.es_administrador", return_value=False),
            patch("asignaciones.permissions.usuario_tiene_rol", return_value=True),
            patch.object(Asignacion.objects, "select_related") as mock_sr,
        ):
            queryset = mock_sr.return_value.order_by.return_value
            queryset.filter.return_value = queryset
            queryset.__iter__.return_value = [self.asignacion_activa]
            queryset.__len__.return_value = 1

            response = view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        queryset.filter.assert_called_with(id_solicitud__id_usuario=self.solicitante_user)

    def test_06_usuario_no_autenticado_recibe_403(self):
        """
        Petición anónima a /api/asignaciones/ recibe 403.
        """
        request = crear_request_con_sesion(
            self.factory,
            "GET",
            "/api/asignaciones/",
            usuario_id=None,
        )
        view = AsignacionListCreateView.as_view()

        with patch("asignaciones.permissions.obtener_usuario_actual", return_value=None):
            response = view(request)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_detalle_autorizado_para_administrador_tecnico_y_propietario(self):
        for usuario_id in (1, 2, 3):
            with self.subTest(usuario_id=usuario_id):
                request = crear_request_con_sesion(
                    self.factory, "GET", "/api/asignaciones/200/", usuario_id=usuario_id,
                )
                with patch.object(Asignacion.objects, "select_related") as consulta:
                    consulta.return_value.get.return_value = self.asignacion_activa
                    response = AsignacionDetailView.as_view()(request, pk=200)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(obtener_data_dict(response)["id_asignacion"], 200)
                consulta.return_value.get.assert_called_once_with(pk=200)

    def test_detalle_inexistente_devuelve_404(self):
        request = crear_request_con_sesion(
            self.factory, "GET", "/api/asignaciones/99999/", usuario_id=1,
        )
        with patch.object(Asignacion.objects, "select_related") as consulta:
            consulta.return_value.get.side_effect = Asignacion.DoesNotExist
            response = AsignacionDetailView.as_view()(request, pk=99999)
        self.assertEqual(response.status_code, 404)
        self.assertIn("detail", obtener_data_dict(response))

    def test_detalle_ajeno_devuelve_403(self):
        request = crear_request_con_sesion(
            self.factory, "GET", "/api/asignaciones/200/", usuario_id=4,
        )
        with patch.object(Asignacion.objects, "select_related") as consulta:
            consulta.return_value.get.return_value = self.asignacion_activa
            response = AsignacionDetailView.as_view()(request, pk=200)
        self.assertEqual(response.status_code, 403)

    def test_detalle_y_estados_rechazan_anonimos(self):
        for vista, kwargs in ((AsignacionDetailView, {"pk": 200}), (EstadoAsignacionListView, {})):
            with self.subTest(vista=vista.__name__):
                request = crear_request_con_sesion(self.factory, "GET", "/api/asignaciones/")
                response = vista.as_view()(request, **kwargs)
                self.assertEqual(response.status_code, 403)

    def test_sin_roles_ni_permiso_no_consulta_ningun_endpoint(self):
        for vista, kwargs in (
            (AsignacionListCreateView, {}), (AsignacionDetailView, {"pk": 200}),
            (EstadoAsignacionListView, {}),
        ):
            with self.subTest(vista=vista.__name__):
                request = crear_request_con_sesion(
                    self.factory, "GET", "/api/asignaciones/", usuario_id=3,
                    roles=[ROL_ADMINISTRADOR],
                )
                with (
                    patch("asignaciones.permissions.es_administrador", return_value=False),
                    patch("asignaciones.permissions.usuario_tiene_rol", return_value=False),
                    patch("asignaciones.permissions.usuario_tiene_permiso", return_value=False),
                    patch.object(Asignacion.objects, "select_related") as consultar,
                    patch.object(EstadoAsignacion.objects, "all") as estados,
                ):
                    response = vista.as_view()(request, **kwargs)
                self.assertEqual(response.status_code, 403)
                consultar.assert_not_called()
                estados.assert_not_called()

    def test_catalogo_de_estados_para_administrador(self):
        request = crear_request_con_sesion(
            self.factory, "GET", "/api/asignaciones/estados/", usuario_id=1,
        )
        with patch.object(EstadoAsignacion.objects, "all") as consulta:
            consulta.return_value.order_by.return_value = [
                EstadoAsignacion(id_estado_asignacion=1, nombre="Activa", descripcion=None),
                EstadoAsignacion(id_estado_asignacion=2, nombre="Finalizada", descripcion=None),
            ]
            response = EstadoAsignacionListView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["nombre"] for item in obtener_data_list(response)], ["Activa", "Finalizada"])
        self.assertEqual(set(obtener_data_list(response)[0]), {"id_estado_asignacion", "nombre", "descripcion"})
        consulta.return_value.order_by.assert_called_once_with("id_estado_asignacion")

    def test_filtros_numericos_se_combinan_en_el_listado_administrativo(self):
        request = crear_request_con_sesion(
            self.factory, "GET", "/api/asignaciones/", usuario_id=1,
            data={"usuario": "3", "equipo": "10", "estado": "1"},
        )
        with patch.object(Asignacion.objects, "select_related") as consulta:
            queryset = consulta.return_value.order_by.return_value
            queryset.filter.return_value = queryset
            queryset.__iter__.return_value = []
            response = AsignacionListCreateView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        filtros = [llamada.kwargs for llamada in queryset.filter.call_args_list]
        self.assertEqual(filtros, [
            {"id_solicitud__id_usuario__id_usuario": 3},
            {"id_activo__id_activo": 10},
            {"id_estado_asignacion__id_estado_asignacion": 1},
        ])
