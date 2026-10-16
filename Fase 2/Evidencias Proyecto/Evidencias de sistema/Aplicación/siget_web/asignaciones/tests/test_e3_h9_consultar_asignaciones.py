"""
Pruebas para E3-H9: Consultar asignaciones.
Cubre consulta general, búsqueda por usuario, búsqueda por equipo, resultados vacíos, alcance por rol y RBAC.
"""
from unittest.mock import patch

from rest_framework import status
from usuarios.services import ROL_ADMINISTRADOR, ROL_TECNICO, ROL_USUARIO_SOLICITANTE

from asignaciones.models import Asignacion
from asignaciones.views import AsignacionDetailView, AsignacionListCreateView
from .helpers import AsignacionesTestBase, crear_request_con_sesion, obtener_data_list


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
