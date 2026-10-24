"""
Pruebas de creación de ticket Service Desk.
Cubre registro exitoso, campos obligatorios, activo relacionado, duplicados activos,
alcance por rol en consultas y RBAC.
"""
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase
from rest_framework import status

from activos.models import Activo
from asignaciones.tests.helpers import (
    crear_request_con_sesion,
    obtener_data_dict,
)
from tickets.models import EstadoTicket, PrioridadTicket, Ticket
from tickets.views import TicketListCreateView
from usuarios.services import ROL_ADMINISTRADOR, ROL_TECNICO, ROL_USUARIO_SOLICITANTE
from usuarios.tests.helpers import SafeMock, crear_mock_usuario


class LevantarTicketTests(SimpleTestCase):
    """
    Pruebas de Levantar ticket Service Desk.
    """

    def setUp(self):
        super().setUp()
        auth_patch = patch("usuarios.authentication.obtener_usuario_actual", return_value=None)
        auth_patch.start()
        self.addCleanup(auth_patch.stop)
        lock_patch = patch("siget.db.connection")
        lock_patch.start()
        self.addCleanup(lock_patch.stop)
        code_patch = patch("tickets.services.generar_codigo_ticket", return_value="TCK-0001")
        code_patch.start()
        self.addCleanup(code_patch.stop)
        # Estos casos ejercitan creación/duplicados con un activo ya autorizado;
        # la política de autorización tiene escenarios independientes.
        selector_patch = patch("tickets.views.activos_reportables_por_usuario")
        self.activos_reportables = selector_patch.start()
        self.activos_reportables.return_value.filter.return_value.exists.return_value = True
        self.addCleanup(selector_patch.stop)
        self.factory = RequestFactory()

        # Usuarios
        self.admin_user = crear_mock_usuario(
            id_usuario=1,
            correo="admin@siget.cl",
            nombres="Admin",
            apellidos="Sistema",
        )
        self.tecnico_user = crear_mock_usuario(
            id_usuario=2,
            correo="tecnico@siget.cl",
            nombres="Tecnico",
            apellidos="Soporte",
        )
        self.solicitante_user = crear_mock_usuario(
            id_usuario=3,
            correo="solicitante@siget.cl",
            nombres="Usuario",
            apellidos="Solicitante",
        )
        self.otro_solicitante = crear_mock_usuario(
            id_usuario=4,
            correo="otro@siget.cl",
            nombres="Otro",
            apellidos="Usuario",
        )

        # Prioridad
        self.prioridad_medio = SafeMock(spec=PrioridadTicket)
        self.prioridad_medio.id_prioridad = 3
        self.prioridad_medio.pk = 3
        self.prioridad_medio.nombre = "Medio"
        self.prioridad_medio.nivel_urgencia = 3

        # Estado Ticket
        self.estado_abierto = SafeMock(spec=EstadoTicket)
        self.estado_abierto.id_estado_ticket = 1
        self.estado_abierto.pk = 1
        self.estado_abierto.nombre = "Abierto"

        # Activo
        self.activo = SafeMock(spec=Activo)
        self.activo.id_activo = 10
        self.activo.pk = 10
        self.activo.codigo_inventario = "ACT-0010"
        self.activo.numero_serie = "SN-12345"

        # Ticket fixture
        self.ticket_mock = SafeMock(spec=Ticket)
        self.ticket_mock.id_ticket = 50
        self.ticket_mock.pk = 50
        self.ticket_mock.codigo_ticket = "TCK-0050"
        self.ticket_mock.id_usuario_solicitante = self.solicitante_user
        self.ticket_mock.id_tecnico_asignado = None
        self.ticket_mock.id_activo = self.activo
        self.ticket_mock.id_estado_ticket = self.estado_abierto
        self.ticket_mock.id_prioridad = self.prioridad_medio
        self.ticket_mock.asunto = "Problema con el teclado"
        self.ticket_mock.descripcion = "La tecla espaciadora no funciona correctamente."
        self.ticket_mock.fecha_creacion = "2026-10-15T10:00:00Z"
        self.ticket_mock.fecha_resolucion = None

        # Mock de transacción atómica
        patcher_atomic_tck = patch("tickets.services.transaction.atomic")
        self.mock_atomic_tck = patcher_atomic_tck.start()
        self.mock_atomic_tck.return_value.__enter__.return_value = None
        self.mock_atomic_tck.return_value.__exit__.return_value = None
        self.addCleanup(patcher_atomic_tck.stop)

        # Configuración por defecto de RBAC y usuarios
        def _mock_obtener_usuario_actual(request):
            session = getattr(request, "session", {})
            user_id = session.get("siget_usuario_id")
            if user_id == 1:
                return self.admin_user
            elif user_id == 2:
                return self.tecnico_user
            elif user_id == 3:
                return self.solicitante_user
            elif user_id == 4:
                return self.otro_solicitante
            return None

        def _mock_usuario_tiene_rol(usuario, nombre_rol):
            if not usuario:
                return False
            user_roles = getattr(usuario, "_mock_roles", None)
            if user_roles is not None:
                return nombre_rol in user_roles
            user_id = getattr(usuario, "id_usuario", None)
            if user_id == 1 or usuario == self.admin_user:
                return nombre_rol == ROL_ADMINISTRADOR
            if user_id == 2 or usuario == self.tecnico_user:
                return nombre_rol == ROL_TECNICO
            if user_id in (3, 4) or usuario in (self.solicitante_user, self.otro_solicitante):
                return nombre_rol == ROL_USUARIO_SOLICITANTE
            return False

        def _mock_es_administrador(usuario):
            return _mock_usuario_tiene_rol(usuario, ROL_ADMINISTRADOR)

        for target in [
            "tickets.permissions.usuario_tiene_rol",
            "tickets.permissions.es_administrador",
            "tickets.views.usuario_tiene_rol",
            "tickets.views.es_administrador",
        ]:
            patcher = patch(target, side_effect=_mock_es_administrador if "es_administrador" in target else _mock_usuario_tiene_rol)
            patcher.start()
            self.addCleanup(patcher.stop)

        patcher_user = patch("tickets.permissions.obtener_usuario_actual", side_effect=_mock_obtener_usuario_actual)
        patcher_user.start()
        self.addCleanup(patcher_user.stop)


    def test_01_registro_exitoso_de_ticket_por_solicitante(self):
        """
        Escenario 1: Usuario solicitante registra un ticket con datos válidos.
        Retorna 201 Created, genera código único y asigna estado 'Abierto'.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/tickets/",
            usuario_id=3,
            roles=[ROL_USUARIO_SOLICITANTE],
            data={
                "asunto": "Problema con el teclado",
                "descripcion": "La tecla espaciadora no funciona correctamente.",
                "id_activo": 10,
                "id_prioridad": 3,
            },
        )
        view = TicketListCreateView.as_view()

        with (
            patch("tickets.permissions.obtener_usuario_actual", return_value=self.solicitante_user),
            patch("tickets.permissions.usuario_tiene_rol", return_value=True),
            patch("tickets.services.PrioridadTicket.objects.get", return_value=self.prioridad_medio),
            patch("tickets.services.Activo.objects.get", return_value=self.activo),
            patch("tickets.services.Ticket.objects.filter") as mock_ticket_filter,
            patch("tickets.services.EstadoTicket.objects.filter") as mock_estado_filter,
            patch("tickets.services.Ticket.objects.order_by") as mock_order,
            patch("tickets.services.Ticket.objects.create") as mock_create,
            patch("tickets.services.registrar_auditoria") as mock_audit,
        ):
            mock_ticket_filter.return_value.filter.return_value = mock_ticket_filter.return_value
            mock_ticket_filter.return_value.first.return_value = None  # No hay duplicado activo
            mock_ticket_filter.return_value.exists.return_value = False  # Código no colisiona
            mock_estado_filter.return_value.first.return_value = self.estado_abierto
            mock_order.return_value.first.return_value = None  # Primer ticket -> TCK-0001
            mock_create.return_value = self.ticket_mock


            response = view(request)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = obtener_data_dict(response)
        self.assertEqual(data["codigo_ticket"], "TCK-0050")
        self.assertEqual(data["estado"]["nombre"], "Abierto")
        mock_create.assert_called_once()
        mock_audit.assert_called_once()

    def test_02_datos_incompletos_sin_asunto_o_descripcion_falla_con_400(self):
        """
        Escenario 2: Asunto o descripción ausentes retornan 400 Bad Request.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/tickets/",
            usuario_id=3,
            roles=[ROL_USUARIO_SOLICITANTE],
            data={"asunto": "", "descripcion": "Solo descripcion"},
        )
        view = TicketListCreateView.as_view()

        with (
            patch("tickets.permissions.obtener_usuario_actual", return_value=self.solicitante_user),
            patch("tickets.permissions.usuario_tiene_rol", return_value=True),
        ):
            response = view(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = obtener_data_dict(response)
        self.assertIn("asunto", data)

    def test_03_datos_invalidos_prioridad_o_activo_inexistente_falla_con_400(self):
        """
        Escenario 3: Prioridad o activo inexistente retorna 400 Bad Request.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/tickets/",
            usuario_id=2,
            roles=[ROL_TECNICO],
            data={
                "asunto": "Falla en monitor",
                "descripcion": "No da video",
                "id_activo": 9999,
            },
        )
        view = TicketListCreateView.as_view()

        with (
            patch("tickets.permissions.obtener_usuario_actual", return_value=self.tecnico_user),
            patch("tickets.permissions.usuario_tiene_rol", return_value=True),
            patch("tickets.services.PrioridadTicket.objects.filter") as mock_pri_filter,
            patch("tickets.services.Activo.objects.get", side_effect=Activo.DoesNotExist),
        ):
            mock_pri_filter.return_value.first.return_value = self.prioridad_medio

            response = view(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = obtener_data_dict(response)
        self.assertIn("id_activo", data)

    def test_04_mismo_incidente_y_activo_activo_es_bloqueado(self):
        """
        Escenario 4: Si el usuario ya tiene un ticket activo para el mismo incidente y activo,
        se impide generar ticket duplicado con 400.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/tickets/",
            usuario_id=3,
            roles=[ROL_USUARIO_SOLICITANTE],
            data={
                "asunto": "Problema con el teclado",
                "descripcion": "Reiteración de falla",
                "id_activo": 10,
            },
        )
        view = TicketListCreateView.as_view()

        ticket_existente = self.ticket_mock

        with (
            patch("tickets.permissions.obtener_usuario_actual", return_value=self.solicitante_user),
            patch("tickets.permissions.usuario_tiene_rol", return_value=True),
            patch("tickets.services.PrioridadTicket.objects.filter") as mock_pri_filter,
            patch("tickets.services.Activo.objects.get", return_value=self.activo),
            patch("tickets.services.Ticket.objects.filter") as mock_ticket_filter,
            patch("tickets.services.Ticket.objects.create") as mock_create,
        ):
            mock_pri_filter.return_value.first.return_value = self.prioridad_medio
            # Simulamos que existe ticket activo para ese activo
            mock_ticket_filter.return_value.filter.return_value.first.return_value = ticket_existente

            response = view(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = obtener_data_dict(response)
        self.assertIn("detail", data)
        self.assertIn("ya existe una solicitud activa", data["detail"].lower())
        mock_create.assert_not_called()

    def test_05_solicitante_solo_ve_sus_propios_tickets_en_get(self):
        """
        Consulta de tickets (GET): Un solicitante solo puede consultar los tickets creados por él.
        """
        request = crear_request_con_sesion(
            self.factory,
            "GET",
            "/api/tickets/",
            usuario_id=3,
            roles=[ROL_USUARIO_SOLICITANTE],
        )
        view = TicketListCreateView.as_view()

        with (
            patch("tickets.permissions.obtener_usuario_actual", return_value=self.solicitante_user),
            patch("tickets.permissions.usuario_tiene_rol", side_effect=lambda usuario, rol: rol == ROL_USUARIO_SOLICITANTE),
            patch("tickets.permissions.es_administrador", return_value=False),
            patch.object(Ticket.objects, "select_related") as mock_sr,
        ):
            queryset = mock_sr.return_value.order_by.return_value
            queryset.filter.return_value = queryset
            queryset.__iter__.return_value = [self.ticket_mock]
            queryset.__len__.return_value = 1

            response = view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        queryset.filter.assert_called_with(id_usuario_solicitante=self.solicitante_user)

    def test_06_usuario_no_autenticado_recibe_403(self):
        """
        Petición anónima a /api/tickets/ es rechazada con 403.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/tickets/",
            usuario_id=None,
            data={"asunto": "Sin auth", "descripcion": "Sin auth"},
        )
        view = TicketListCreateView.as_view()

        with patch("tickets.permissions.obtener_usuario_actual", return_value=None):
            response = view(request)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
