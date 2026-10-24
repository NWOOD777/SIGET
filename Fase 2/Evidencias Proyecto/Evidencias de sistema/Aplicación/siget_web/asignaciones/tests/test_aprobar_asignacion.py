"""
Pruebas de aprobación y rechazo de solicitud de asignación.
Cubre aprobación, rechazo, validación de estado previo, solicitud inexistente, doble gestión y RBAC.
"""
from unittest.mock import patch

from rest_framework import status

from asignaciones.models import SolicitudAsignacion
from asignaciones.views import (
    SolicitudAsignacionAprobarView,
    SolicitudAsignacionRechazarView,
)
from usuarios.services import ROL_ADMINISTRADOR, ROL_TECNICO

from .helpers import AsignacionesTestBase, crear_request_con_sesion, obtener_data_dict


class AprobarRechazarSolicitudTests(AsignacionesTestBase):
    """
    Pruebas de Aprobar o rechazar solicitud de asignación.
    """

    def test_01_aprobacion_exitosa_por_administrador(self):
        """
        Escenario 1: Administrador aprueba una solicitud pendiente válida.
        Retorna 200 OK, cambia a 'Aprobada' y registra resolución.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/solicitudes-asignacion/100/aprobar/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
        )
        view = SolicitudAsignacionAprobarView.as_view()

        with (
            patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.admin_user),
            patch("asignaciones.permissions.es_administrador", return_value=True),
            patch.object(SolicitudAsignacion.objects, "select_related") as mock_sr,
            patch("asignaciones.services.Activo.objects.filter") as mock_activos,
            patch("asignaciones.services.EstadoSolicitudAsignacion.objects.filter") as mock_estado,
            patch("asignaciones.services.registrar_auditoria") as mock_audit,
        ):
            mock_sr.return_value.get.return_value = self.solicitud_pendiente
            mock_activos.return_value.exists.return_value = True
            mock_estado.return_value.first.return_value = self.estado_solicitud_aprobada
            self.solicitud_pendiente.save = lambda **kw: None

            response = view(request, pk=100)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.solicitud_pendiente.id_estado_solicitud, self.estado_solicitud_aprobada)
        self.assertEqual(self.solicitud_pendiente.id_administrador_resolutor, self.admin_user)
        mock_audit.assert_called_once()

    def test_02_rechazo_exitoso_con_motivo_por_administrador(self):
        """
        Escenario 2: Administrador rechaza solicitud pendiente indicando motivo.
        Retorna 200 OK y estado 'Rechazada'.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/solicitudes-asignacion/100/rechazar/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
            data={"motivo_rechazo": "Presupuesto no disponible para esta categoría"},
        )
        view = SolicitudAsignacionRechazarView.as_view()

        with (
            patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.admin_user),
            patch("asignaciones.permissions.es_administrador", return_value=True),
            patch.object(SolicitudAsignacion.objects, "select_related") as mock_sr,
            patch("asignaciones.services.EstadoSolicitudAsignacion.objects.filter") as mock_estado,
            patch("asignaciones.services.registrar_auditoria") as mock_audit,
        ):
            mock_sr.return_value.get.return_value = self.solicitud_pendiente
            mock_estado.return_value.first.return_value = self.estado_solicitud_rechazada
            self.solicitud_pendiente.save = lambda **kw: None

            response = view(request, pk=100)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.solicitud_pendiente.id_estado_solicitud, self.estado_solicitud_rechazada)
        self.assertEqual(self.solicitud_pendiente.motivo_rechazo, "Presupuesto no disponible para esta categoría")
        mock_audit.assert_called_once()

    def test_03_solicitud_inexistente_retorna_404(self):
        """
        Escenario 3: Búsqueda o gestión de una solicitud inexistente retorna 404.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/solicitudes-asignacion/9999/aprobar/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
        )
        view = SolicitudAsignacionAprobarView.as_view()

        with (
            patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.admin_user),
            patch("asignaciones.permissions.es_administrador", return_value=True),
            patch.object(SolicitudAsignacion.objects, "select_related") as mock_sr,
        ):
            mock_sr.return_value.get.side_effect = SolicitudAsignacion.DoesNotExist

            response = view(request, pk=9999)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_04_solicitud_ya_gestionada_es_bloqueada(self):
        """
        Escenario 4: Si la solicitud ya fue aprobada o rechazada, no se permite volver a gestionarla.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/solicitudes-asignacion/101/aprobar/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
        )
        view = SolicitudAsignacionAprobarView.as_view()

        with (
            patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.admin_user),
            patch("asignaciones.permissions.es_administrador", return_value=True),
            patch.object(SolicitudAsignacion.objects, "select_related") as mock_sr,
        ):
            mock_sr.return_value.get.return_value = self.solicitud_aprobada  # ya aprobada

            response = view(request, pk=101)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = obtener_data_dict(response)
        self.assertIn("detail", data)
        self.assertIn("ya fue gestionada", data["detail"].lower())

    def test_05_rechazo_sin_motivo_retorna_400(self):
        """
        Rechazar sin especificar motivo_rechazo debe retornar 400.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/solicitudes-asignacion/100/rechazar/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
            data={"motivo_rechazo": "   "},
        )
        view = SolicitudAsignacionRechazarView.as_view()

        with (
            patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.admin_user),
            patch("asignaciones.permissions.es_administrador", return_value=True),
            patch.object(SolicitudAsignacion.objects, "select_related") as mock_sr,
        ):
            mock_sr.return_value.get.return_value = self.solicitud_pendiente
            response = view(request, pk=100)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = obtener_data_dict(response)
        self.assertIn("motivo_rechazo", data)

    def test_06_usuario_no_autorizado_o_solicitante_recibe_403(self):
        """
        Un Técnico o Usuario solicitante intentando aprobar recibe 403.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/solicitudes-asignacion/100/aprobar/",
            usuario_id=2,
            roles=[ROL_TECNICO],
        )
        view = SolicitudAsignacionAprobarView.as_view()

        with (
            patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.tecnico_user),
            patch("asignaciones.permissions.es_administrador", return_value=False),
            patch("asignaciones.permissions.usuario_tiene_permiso", return_value=False),
        ):
            response = view(request, pk=100)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
