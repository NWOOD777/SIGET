"""
Pruebas para E4-H10: Registrar devolución de equipo.
Cubre devolución exitosa, asignación inactiva o inexistente, campos requeridos,
duplicidad, RBAC y cierre de asignación.
"""
from unittest.mock import patch

from rest_framework import status
from usuarios.services import ROL_ADMINISTRADOR, ROL_TECNICO, ROL_USUARIO_SOLICITANTE

from asignaciones.models import Asignacion, DevolucionActivo
from asignaciones.views import AsignacionDevolucionView
from .helpers import (
    AsignacionesTestBase,
    crear_mock_devolucion,
    crear_request_con_sesion,
    obtener_data_dict,
)


class RegistrarDevolucionE4H10Tests(AsignacionesTestBase):
    """
    Suite de pruebas correspondiente a E4-H10 — Registrar devolución de equipo.
    """

    def test_01_devolucion_exitosa_por_tecnico(self):
        """
        Escenario 1: Técnico de soporte registra devolución de asignación activa.
        Retorna 201 Created, cierra asignación ('Finalizada') y registra devolución.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/asignaciones/200/devolucion/",
            usuario_id=2,
            roles=[ROL_TECNICO],
            data={
                "condicion_fisica": "Buen estado",
                "motivo_devolucion": "Término de proyecto",
                "observaciones": "Equipo en óptimas condiciones",
            },
        )
        view = AsignacionDevolucionView.as_view()

        devolucion_mock = crear_mock_devolucion(
            id_devolucion=300,
            asignacion=self.asignacion_activa,
            tecnico=self.tecnico_user,
            estado_activo=self.estado_activo_disponible,
            condicion_fisica="Buen estado",
            motivo_devolucion="Término de proyecto",
            observaciones="Equipo en óptimas condiciones",
        )


        with (
            patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.tecnico_user),
            patch("asignaciones.permissions.usuario_tiene_rol", return_value=True),
            patch.object(Asignacion.objects, "select_related") as mock_asig_sr,
            patch("asignaciones.services.DevolucionActivo.objects.filter") as mock_dev_filter,
            patch("asignaciones.services.EstadoActivo.objects.filter") as mock_est_act,
            patch("asignaciones.services.EstadoAsignacion.objects.filter") as mock_est_asig,
            patch("asignaciones.services.DevolucionActivo.objects.create") as mock_dev_create,
            patch("asignaciones.services.registrar_auditoria") as mock_audit,
        ):
            mock_asig_sr.return_value.get.return_value = self.asignacion_activa
            mock_dev_filter.return_value.exists.return_value = False
            mock_est_act.return_value.first.return_value = self.estado_activo_disponible
            mock_est_asig.return_value.first.return_value = self.estado_asignacion_finalizada
            mock_dev_create.return_value = devolucion_mock

            self.asignacion_activa.save = lambda **kw: None
            self.activo.save = lambda **kw: None

            response = view(request, pk=200)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.asignacion_activa.id_estado_asignacion, self.estado_asignacion_finalizada)
        data = obtener_data_dict(response)
        self.assertEqual(data["condicion_fisica"], "Buen estado")
        mock_dev_create.assert_called_once()
        mock_audit.assert_called_once()

    def test_02_asignacion_inexistente_retorna_404(self):
        """
        Escenario 2: Asignación inexistente retorna 404.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/asignaciones/9999/devolucion/",
            usuario_id=2,
            roles=[ROL_TECNICO],
            data={"condicion_fisica": "Buen estado"},
        )
        view = AsignacionDevolucionView.as_view()

        with (
            patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.tecnico_user),
            patch("asignaciones.permissions.usuario_tiene_rol", return_value=True),
            patch.object(Asignacion.objects, "select_related") as mock_asig_sr,
        ):
            mock_asig_sr.return_value.get.side_effect = Asignacion.DoesNotExist

            response = view(request, pk=9999)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_03_asignacion_ya_finalizada_impide_devolucion(self):
        """
        Escenario 2 bis: Si la asignación ya no está activa, impide la devolución con 400.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/asignaciones/200/devolucion/",
            usuario_id=2,
            roles=[ROL_TECNICO],
            data={"condicion_fisica": "Buen estado"},
        )
        view = AsignacionDevolucionView.as_view()

        asignacion_cerrada = self.asignacion_activa
        asignacion_cerrada.id_estado_asignacion = self.estado_asignacion_finalizada

        with (
            patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.tecnico_user),
            patch("asignaciones.permissions.usuario_tiene_rol", return_value=True),
            patch.object(Asignacion.objects, "select_related") as mock_asig_sr,
        ):
            mock_asig_sr.return_value.get.return_value = asignacion_cerrada

            response = view(request, pk=200)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = obtener_data_dict(response)
        self.assertIn("detail", data)
        self.assertIn("no existe una asignación activa", data["detail"].lower())

    def test_04_datos_incompletos_condicion_ausente_falla_con_400(self):
        """
        Escenario 3: Falta de condición física retorna 400 indicando campos obligatorios.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/asignaciones/200/devolucion/",
            usuario_id=2,
            roles=[ROL_TECNICO],
            data={"motivo_devolucion": "Sin condicion"},
        )
        view = AsignacionDevolucionView.as_view()

        with (
            patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.tecnico_user),
            patch("asignaciones.permissions.usuario_tiene_rol", return_value=True),
            patch.object(Asignacion.objects, "select_related") as mock_asig_sr,
        ):
            mock_asig_sr.return_value.get.return_value = self.asignacion_activa

            response = view(request, pk=200)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = obtener_data_dict(response)
        self.assertIn("condicion_fisica", data)

    def test_05_devolucion_duplicada_es_rechazada(self):
        """
        Escenario 4: Si la devolución ya fue registrada previamente, se impide duplicar con 400.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/asignaciones/200/devolucion/",
            usuario_id=2,
            roles=[ROL_TECNICO],
            data={"condicion_fisica": "Buen estado"},
        )
        view = AsignacionDevolucionView.as_view()

        with (
            patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.tecnico_user),
            patch("asignaciones.permissions.usuario_tiene_rol", return_value=True),
            patch.object(Asignacion.objects, "select_related") as mock_asig_sr,
            patch("asignaciones.services.DevolucionActivo.objects.filter") as mock_dev_filter,
        ):
            mock_asig_sr.return_value.get.return_value = self.asignacion_activa
            mock_dev_filter.return_value.exists.return_value = True  # Ya registrada

            response = view(request, pk=200)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = obtener_data_dict(response)
        self.assertIn("detail", data)
        self.assertIn("ya fue devuelto", data["detail"].lower())

    def test_06_usuario_solicitante_recibe_403(self):
        """
        Un Usuario solicitante no puede registrar devoluciones (403).
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/asignaciones/200/devolucion/",
            usuario_id=3,
            roles=[ROL_USUARIO_SOLICITANTE],
            data={"condicion_fisica": "Buen estado"},
        )
        view = AsignacionDevolucionView.as_view()

        with (
            patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.solicitante_user),
            patch("asignaciones.permissions.usuario_tiene_rol", return_value=False),
            patch("asignaciones.permissions.usuario_tiene_permiso", return_value=False),
            patch("asignaciones.permissions.es_administrador", return_value=False),
        ):
            response = view(request, pk=200)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
