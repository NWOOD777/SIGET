"""
Pruebas para E3-H20: Registrar entrega y asignación de equipo.
Cubre entrega exitosa, compatibilidad de equipo, estado de solicitud, entregas duplicadas,
disponibilidad de activo, RBAC y transaccionalidad.
"""
from unittest.mock import patch

from rest_framework import status

from asignaciones.models import SolicitudAsignacion
from asignaciones.views import SolicitudAsignacionEntregarView
from usuarios.services import ROL_TECNICO, ROL_USUARIO_SOLICITANTE

from .helpers import AsignacionesTestBase, crear_request_con_sesion, obtener_data_dict


class RegistrarEntregaE3H20Tests(AsignacionesTestBase):
    """
    Suite de pruebas correspondiente a E3-H20 — Registrar entrega y asignación de equipo.
    """

    def test_01_entrega_exitosa_por_tecnico_de_soporte(self):
        """
        Escenario 1: Técnico entrega un activo disponible compatible con solicitud aprobada.
        Retorna 201 Created, activa asignación, activo pasa a 'Asignado' y solicitud a 'Atendida'.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/solicitudes-asignacion/101/entregar/",
            usuario_id=2,
            roles=[ROL_TECNICO],
            data={"id_activo": 10},
        )
        view = SolicitudAsignacionEntregarView.as_view()

        with (
            patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.tecnico_user),
            patch("asignaciones.permissions.usuario_tiene_rol", return_value=True),
            patch.object(SolicitudAsignacion.objects, "select_related") as mock_sol_sr,
            patch("asignaciones.services.Asignacion.objects.filter") as mock_asig_filter,
            patch("asignaciones.services.Activo.objects.select_related") as mock_act_sr,
            patch("asignaciones.services.EstadoAsignacion.objects.filter") as mock_est_asig,
            patch("asignaciones.services.EstadoActivo.objects.filter") as mock_est_act,
            patch("asignaciones.services.EstadoSolicitudAsignacion.objects.filter") as mock_est_sol,
            patch("asignaciones.services.Asignacion.objects.create") as mock_asig_create,
            patch("asignaciones.services.registrar_auditoria") as mock_audit,
        ):
            mock_sol_sr.return_value.get.return_value = self.solicitud_aprobada
            mock_asig_filter.return_value.exists.return_value = False  # No existe asignación previa
            mock_act_sr.return_value.get.return_value = self.activo  # Disponible y de categoría 1
            mock_est_asig.return_value.first.return_value = self.estado_asignacion_activa
            mock_est_act.return_value.first.return_value = self.estado_activo_asignado
            mock_est_sol.return_value.first.return_value = self.estado_solicitud_atendida
            mock_asig_create.return_value = self.asignacion_activa

            self.activo.save = lambda **kw: None
            self.solicitud_aprobada.save = lambda **kw: None

            response = view(request, pk=101)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.activo.id_estado_activo, self.estado_activo_asignado)
        self.assertEqual(self.solicitud_aprobada.id_estado_solicitud, self.estado_solicitud_atendida)
        mock_asig_create.assert_called_once()
        mock_audit.assert_called_once()

    def test_02_equipo_incompatible_con_categoria_bloquea_entrega(self):
        """
        Escenario 2: El activo seleccionado pertenece a una categoría diferente de la solicitada.
        Retorna 400 Bad Request y bloquea la entrega.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/solicitudes-asignacion/101/entregar/",
            usuario_id=2,
            roles=[ROL_TECNICO],
            data={"id_activo": 20},
        )
        view = SolicitudAsignacionEntregarView.as_view()

        activo_incompatible = self.activo
        # Activo con otra categoría (id=2)
        activo_incompatible.id_modelo.id_categoria = self.otra_categoria

        with (
            patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.tecnico_user),
            patch("asignaciones.permissions.usuario_tiene_rol", return_value=True),
            patch.object(SolicitudAsignacion.objects, "select_related") as mock_sol_sr,
            patch("asignaciones.services.Asignacion.objects.filter") as mock_asig_filter,
            patch("asignaciones.services.Activo.objects.select_related") as mock_act_sr,
        ):
            mock_sol_sr.return_value.get.return_value = self.solicitud_aprobada  # categoría 1
            mock_asig_filter.return_value.exists.return_value = False
            mock_act_sr.return_value.get.return_value = activo_incompatible

            response = view(request, pk=101)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = obtener_data_dict(response)
        self.assertIn("detail", data)
        self.assertIn("no es compatible", data["detail"].lower())

    def test_03_solicitud_no_aprobada_bloquea_entrega(self):
        """
        Escenario 3: Intentar entregar sobre una solicitud que sigue en 'Pendiente' debe ser rechazado con 400.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/solicitudes-asignacion/100/entregar/",
            usuario_id=2,
            roles=[ROL_TECNICO],
            data={"id_activo": 10},
        )
        view = SolicitudAsignacionEntregarView.as_view()

        with (
            patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.tecnico_user),
            patch("asignaciones.permissions.usuario_tiene_rol", return_value=True),
            patch.object(SolicitudAsignacion.objects, "select_related") as mock_sol_sr,
        ):
            mock_sol_sr.return_value.get.return_value = self.solicitud_pendiente  # Pendiente

            response = view(request, pk=100)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = obtener_data_dict(response)
        self.assertIn("detail", data)
        self.assertIn("no existe una solicitud aprobada", data["detail"].lower())

    def test_04_entrega_previamente_registrada_es_bloqueada(self):
        """
        Escenario 4: Si la solicitud ya fue atendida y tiene asignación activa, se impide registro duplicado.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/solicitudes-asignacion/101/entregar/",
            usuario_id=2,
            roles=[ROL_TECNICO],
            data={"id_activo": 10},
        )
        view = SolicitudAsignacionEntregarView.as_view()

        with (
            patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.tecnico_user),
            patch("asignaciones.permissions.usuario_tiene_rol", return_value=True),
            patch.object(SolicitudAsignacion.objects, "select_related") as mock_sol_sr,
            patch("asignaciones.services.Asignacion.objects.filter") as mock_asig_filter,
        ):
            mock_sol_sr.return_value.get.return_value = self.solicitud_aprobada
            mock_asig_filter.return_value.exists.return_value = True  # Ya tiene asignación

            response = view(request, pk=101)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = obtener_data_dict(response)
        self.assertIn("detail", data)
        self.assertIn("ya fue atendida", data["detail"].lower())

    def test_05_activo_no_disponible_bloquea_entrega(self):
        """
        Si el activo seleccionado está 'Asignado' o 'En revisión', se rechaza con 400.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/solicitudes-asignacion/101/entregar/",
            usuario_id=2,
            roles=[ROL_TECNICO],
            data={"id_activo": 10},
        )
        view = SolicitudAsignacionEntregarView.as_view()

        activo_ocupado = self.activo
        activo_ocupado.id_estado_activo = self.estado_activo_asignado

        with (
            patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.tecnico_user),
            patch("asignaciones.permissions.usuario_tiene_rol", return_value=True),
            patch.object(SolicitudAsignacion.objects, "select_related") as mock_sol_sr,
            patch("asignaciones.services.Asignacion.objects.filter") as mock_asig_filter,
            patch("asignaciones.services.Activo.objects.select_related") as mock_act_sr,
        ):
            mock_sol_sr.return_value.get.return_value = self.solicitud_aprobada
            mock_asig_filter.return_value.exists.return_value = False
            mock_act_sr.return_value.get.return_value = activo_ocupado

            response = view(request, pk=101)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = obtener_data_dict(response)
        self.assertIn("detail", data)
        self.assertIn("no está disponible", data["detail"].lower())

    def test_06_usuario_solicitante_recibe_403(self):
        """
        Un Usuario solicitante no puede registrar entregas (403).
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/solicitudes-asignacion/101/entregar/",
            usuario_id=3,
            roles=[ROL_USUARIO_SOLICITANTE],
            data={"id_activo": 10},
        )
        view = SolicitudAsignacionEntregarView.as_view()

        with (
            patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.solicitante_user),
            patch("asignaciones.permissions.usuario_tiene_rol", return_value=False),
            patch("asignaciones.permissions.usuario_tiene_permiso", return_value=False),
            patch("asignaciones.permissions.es_administrador", return_value=False),
        ):
            response = view(request, pk=101)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
