"""
Pruebas para E3-H7: Solicitar asignación de equipo.
Cubre escenarios funcionales, criterios de aceptación, RBAC, sesión manipulada y auditoría.
"""
from unittest.mock import patch

from rest_framework import status
from usuarios.services import ROL_ADMINISTRADOR, ROL_TECNICO, ROL_USUARIO_SOLICITANTE

from asignaciones.models import SolicitudAsignacion
from asignaciones.views import SolicitudAsignacionListCreateView
from .helpers import AsignacionesTestBase, crear_request_con_sesion, obtener_data_dict


class SolicitarAsignacionE3H7Tests(AsignacionesTestBase):
    """
    Suite de pruebas correspondiente a E3-H7 — Solicitar asignación de equipo.
    """

    def test_01_solicitud_asignacion_exitosa_por_solicitante(self):
        """
        Escenario 1: Usuario solicitante registra solicitud con disponibilidad.
        Retorna 201 Created y estado 'Pendiente'.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/solicitudes-asignacion/",
            usuario_id=3,
            roles=[ROL_USUARIO_SOLICITANTE],
            data={"id_categoria": 1, "motivo": "Requiero notebook para labores de desarrollo"},
        )
        view = SolicitudAsignacionListCreateView.as_view()

        with (
            patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.solicitante_user),
            patch("asignaciones.services.CategoriaActivo.objects.get", return_value=self.categoria),
            patch("asignaciones.services.Activo.objects.filter") as mock_activos,
            patch("asignaciones.services.SolicitudAsignacion.objects.filter") as mock_solicitudes,
            patch("asignaciones.services.EstadoSolicitudAsignacion.objects.filter") as mock_estado,
            patch("asignaciones.services.SolicitudAsignacion.objects.create") as mock_create,
            patch("asignaciones.services.registrar_auditoria") as mock_audit,
        ):
            mock_activos.return_value.count.return_value = 5  # Hay disponibilidad
            mock_solicitudes.return_value.first.return_value = None  # No hay duplicado
            mock_estado.return_value.first.return_value = self.estado_solicitud_pendiente
            mock_create.return_value = self.solicitud_pendiente

            response = view(request)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = obtener_data_dict(response)
        self.assertEqual(data["id_solicitud"], 100)
        self.assertEqual(data["estado"]["nombre"], "Pendiente")
        mock_create.assert_called_once()
        mock_audit.assert_called_once()

    def test_02_categoria_sin_disponibilidad_rechaza_solicitud(self):
        """
        Escenario 2: La categoría seleccionada no tiene equipos disponibles.
        Retorna 400 Bad Request y no crea la solicitud.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/solicitudes-asignacion/",
            usuario_id=3,
            roles=[ROL_USUARIO_SOLICITANTE],
            data={"id_categoria": 1, "motivo": "Solicitud sin stock"},
        )
        view = SolicitudAsignacionListCreateView.as_view()

        with (
            patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.solicitante_user),
            patch("asignaciones.services.CategoriaActivo.objects.get", return_value=self.categoria),
            patch("asignaciones.services.Activo.objects.filter") as mock_activos,
            patch("asignaciones.services.SolicitudAsignacion.objects.create") as mock_create,
        ):
            mock_activos.return_value.count.return_value = 0  # 0 disponibles

            response = view(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = obtener_data_dict(response)
        self.assertIn("detail", data)
        self.assertIn("no existe disponibilidad", data["detail"].lower())
        mock_create.assert_not_called()

    def test_03_datos_incompletos_motivo_vacio_falla_validacion(self):
        """
        Escenario 3: Motivo vacío o ausente debe ser rechazado con 400.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/solicitudes-asignacion/",
            usuario_id=3,
            roles=[ROL_USUARIO_SOLICITANTE],
            data={"id_categoria": 1, "motivo": "   "},
        )
        view = SolicitudAsignacionListCreateView.as_view()

        with patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.solicitante_user):
            response = view(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = obtener_data_dict(response)
        self.assertIn("motivo", data)

    def test_04_solicitud_duplicada_activa_es_rechazada(self):
        """
        Escenario 4: Si el usuario ya posee una solicitud activa (Pendiente/Aprobada) para esa categoría,
        se bloquea la duplicación con 400.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/solicitudes-asignacion/",
            usuario_id=3,
            roles=[ROL_USUARIO_SOLICITANTE],
            data={"id_categoria": 1, "motivo": "Otra solicitud duplicada"},
        )
        view = SolicitudAsignacionListCreateView.as_view()

        with (
            patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.solicitante_user),
            patch("asignaciones.services.CategoriaActivo.objects.get", return_value=self.categoria),
            patch("asignaciones.services.Activo.objects.filter") as mock_activos,
            patch("asignaciones.services.SolicitudAsignacion.objects.filter") as mock_solicitudes,
            patch("asignaciones.services.SolicitudAsignacion.objects.create") as mock_create,
        ):
            mock_activos.return_value.count.return_value = 3
            mock_solicitudes.return_value.first.return_value = self.solicitud_pendiente  # Ya existe activa

            response = view(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = obtener_data_dict(response)
        self.assertIn("detail", data)
        self.assertIn("ya existe una solicitud activa", data["detail"].lower())
        mock_create.assert_not_called()

    def test_05_usuario_no_autenticado_recibe_403(self):
        """
        Petición sin sesión debe ser rechazada de forma controlada.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/solicitudes-asignacion/",
            usuario_id=None,
            data={"id_categoria": 1, "motivo": "Sin autenticar"},
        )
        view = SolicitudAsignacionListCreateView.as_view()

        with patch("asignaciones.permissions.obtener_usuario_actual", return_value=None):
            response = view(request)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_06_sesion_manipulada_sin_rol_en_bd_es_rechazada(self):
        """
        Sesión manipulada en cliente fingiendo rol solicitante, pero usuario en PostgreSQL sin rol.
        Debe ser rechazada con 403.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/solicitudes-asignacion/",
            usuario_id=3,
            roles=[ROL_USUARIO_SOLICITANTE],  # manipulada en sesión
            data={"id_categoria": 1, "motivo": "Intento manipulado"},
        )
        view = SolicitudAsignacionListCreateView.as_view()

        with (
            patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.solicitante_user),
            patch("asignaciones.permissions.usuario_tiene_rol", return_value=False),
            patch("asignaciones.permissions.usuario_tiene_permiso", return_value=False),
            patch("asignaciones.permissions.es_administrador", return_value=False),
        ):
            response = view(request)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
