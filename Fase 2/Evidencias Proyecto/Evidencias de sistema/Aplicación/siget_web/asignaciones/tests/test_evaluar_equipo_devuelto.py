"""
Pruebas de evaluación de estado de equipo devuelto.
Cubre evaluación en 'Buen estado' (pasa a Disponible), 'Con falla técnica' y 'Con daño físico'
(pasan a 'En revisión' y generan ticket de soporte), validación de condición y auditoría.
"""
from unittest.mock import Mock, patch

from rest_framework import status

from asignaciones.models import Asignacion
from asignaciones.views import AsignacionDevolucionView
from tickets.models import Ticket
from usuarios.services import ROL_TECNICO

from .helpers import (
    AsignacionesTestBase,
    crear_mock_devolucion,
    crear_request_con_sesion,
    obtener_data_dict,
)


class EvaluarEquipoDevueltoTests(AsignacionesTestBase):
    """
    Pruebas de Evaluar estado de equipo devuelto.
    """

    def test_01_equipo_recibido_en_buen_estado_pasa_a_disponible(self):
        """
        Escenario 1: Equipo devuelto sin fallas ni daños.
        Pasa a 'Disponible' y no genera ticket de soporte.
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

        devolucion_mock = crear_mock_devolucion(
            id_devolucion=301,
            asignacion=self.asignacion_activa,
            tecnico=self.tecnico_user,
            estado_activo=self.estado_activo_disponible,
            condicion_fisica="Buen estado",
        )

        with (
            patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.tecnico_user),
            patch("asignaciones.permissions.usuario_tiene_rol", return_value=True),
            patch.object(Asignacion.objects, "select_related") as mock_asig_sr,
            patch("asignaciones.services.DevolucionActivo.objects.filter") as mock_dev_filter,
            patch("asignaciones.services.EstadoActivo.objects.filter") as mock_est_act,
            patch("asignaciones.services.EstadoAsignacion.objects.filter") as mock_est_asig,
            patch("asignaciones.services.DevolucionActivo.objects.create") as mock_dev_create,
            patch("asignaciones.services.crear_ticket") as mock_ticket,
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
        self.assertEqual(self.activo.id_estado_activo, self.estado_activo_disponible)
        mock_ticket.assert_not_called()
        mock_audit.assert_called_once()

    def test_02_equipo_con_falla_tecnica_pasa_a_en_revision_y_genera_ticket(self):
        """
        Escenario 2: Equipo con falla técnica.
        El activo pasa a 'En revisión' y se genera o asocia un ticket de soporte Service Desk.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/asignaciones/200/devolucion/",
            usuario_id=2,
            roles=[ROL_TECNICO],
            data={
                "condicion_fisica": "Con falla técnica",
                "motivo_devolucion": "Falla en placa base",
                "observaciones": "El equipo no enciende",
            },
        )
        view = AsignacionDevolucionView.as_view()

        devolucion_mock = crear_mock_devolucion(
            id_devolucion=302,
            asignacion=self.asignacion_activa,
            tecnico=self.tecnico_user,
            estado_activo=self.estado_activo_en_revision,
            condicion_fisica="Con falla técnica",
            motivo_devolucion="Falla en placa base",
            observaciones="El equipo no enciende",
        )

        ticket_mock = Mock(spec=Ticket)
        ticket_mock.codigo_ticket = "TCK-0010"

        with (
            patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.tecnico_user),
            patch("asignaciones.permissions.usuario_tiene_rol", return_value=True),
            patch.object(Asignacion.objects, "select_related") as mock_asig_sr,
            patch("asignaciones.services.DevolucionActivo.objects.filter") as mock_dev_filter,
            patch("asignaciones.services.EstadoActivo.objects.filter") as mock_est_act,
            patch("asignaciones.services.EstadoAsignacion.objects.filter") as mock_est_asig,
            patch("asignaciones.services.crear_ticket", return_value=ticket_mock) as mock_ticket,
            patch("asignaciones.services.DevolucionActivo.objects.create") as mock_dev_create,
            patch("asignaciones.services.registrar_auditoria") as mock_audit,
        ):
            mock_asig_sr.return_value.get.return_value = self.asignacion_activa
            mock_dev_filter.return_value.exists.return_value = False
            mock_est_act.return_value.first.return_value = self.estado_activo_en_revision
            mock_est_asig.return_value.first.return_value = self.estado_asignacion_finalizada
            mock_dev_create.return_value = devolucion_mock

            self.asignacion_activa.save = lambda **kw: None
            self.activo.save = lambda **kw: None

            response = view(request, pk=200)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.activo.id_estado_activo, self.estado_activo_en_revision)
        mock_ticket.assert_called_once()
        mock_audit.assert_called_once()

    def test_03_equipo_con_dano_fisico_pasa_a_en_revision_con_observacion_y_ticket(self):
        """
        Escenario 3: Equipo con daño físico. Guarda observación, pasa activo a 'En revisión'
        y genera ticket de soporte.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/asignaciones/200/devolucion/",
            usuario_id=2,
            roles=[ROL_TECNICO],
            data={
                "condicion_fisica": "Con daño físico",
                "observaciones": "Pantalla quebrada en esquina superior izquierda",
            },
        )
        view = AsignacionDevolucionView.as_view()

        devolucion_mock = crear_mock_devolucion(
            id_devolucion=303,
            asignacion=self.asignacion_activa,
            tecnico=self.tecnico_user,
            estado_activo=self.estado_activo_en_revision,
            condicion_fisica="Con daño físico",
            observaciones="Pantalla quebrada en esquina superior izquierda",
        )

        ticket_mock = Mock(spec=Ticket)
        ticket_mock.codigo_ticket = "TCK-0011"

        with (
            patch("asignaciones.permissions.obtener_usuario_actual", return_value=self.tecnico_user),
            patch("asignaciones.permissions.usuario_tiene_rol", return_value=True),
            patch.object(Asignacion.objects, "select_related") as mock_asig_sr,
            patch("asignaciones.services.DevolucionActivo.objects.filter") as mock_dev_filter,
            patch("asignaciones.services.EstadoActivo.objects.filter") as mock_est_act,
            patch("asignaciones.services.EstadoAsignacion.objects.filter") as mock_est_asig,
            patch("asignaciones.services.crear_ticket", return_value=ticket_mock) as mock_ticket,
            patch("asignaciones.services.DevolucionActivo.objects.create") as mock_dev_create,
            patch("asignaciones.services.registrar_auditoria") as mock_audit,
        ):
            mock_asig_sr.return_value.get.return_value = self.asignacion_activa
            mock_dev_filter.return_value.exists.return_value = False
            mock_est_act.return_value.first.return_value = self.estado_activo_en_revision
            mock_est_asig.return_value.first.return_value = self.estado_asignacion_finalizada
            mock_dev_create.return_value = devolucion_mock

            self.asignacion_activa.save = lambda **kw: None
            self.activo.save = lambda **kw: None

            response = view(request, pk=200)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.activo.id_estado_activo, self.estado_activo_en_revision)
        mock_ticket.assert_called_once()
        mock_audit.assert_called_once()

    def test_04_condicion_no_permitida_es_rechazada(self):
        """
        Escenario 4: Condición no seleccionada o fuera de catálogo oficial es rechazada con 400.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/asignaciones/200/devolucion/",
            usuario_id=2,
            roles=[ROL_TECNICO],
            data={"condicion_fisica": "Destruido"},
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
