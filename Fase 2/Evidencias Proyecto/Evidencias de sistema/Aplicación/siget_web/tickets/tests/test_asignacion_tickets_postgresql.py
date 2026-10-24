"""Asignación/reasignación  sobre una base PostgreSQL aislada test_."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

from django.db import DatabaseError, connection, connections
from django.test import override_settings
from django.urls import reverse
from rest_framework.exceptions import PermissionDenied

from notificaciones.models import Notificacion
from notificaciones.resend_client import ErrorCorreo
from notificaciones.services import despachar_notificacion
from tickets.models import EstadoTicket, Ticket
from tickets.services import asignar_ticket, crear_ticket
from usuarios.models import BitacoraAuditoria, Permiso, Rol, RolPermiso, UsuarioRol
from usuarios.tests.test_integracion_postgresql import PostgreSQLTestBase


@override_settings(SIGET_PUBLIC_URL="https://siget.example.invalid", RESEND_FROM_EMAIL="SIGET <avisos@example.invalid>", RESEND_MAX_ATTEMPTS=3, RESEND_RETRY_SECONDS=1)
class AsignarTicketPostgreSQLTests(PostgreSQLTestBase):
    def setUp(self):
        super().setUp()
        self.assertEqual(connection.settings_dict["NAME"], "test_siget_db")
        self.segundo = self.usuario(5, "Técnico de soporte")
        self.ticket = crear_ticket(self.solicitante, "Incidente", "Descripción de la falla")
        self.url = reverse("ticket-asignar", kwargs={"pk": self.ticket.pk})
        self.http_patch = patch("notificaciones.resend_client.requests.post")
        self.http = self.http_patch.start()
        self.addCleanup(self.http_patch.stop)

    def asignar(self, tecnico=None, usuario=None, motivo="Especialidad requerida", **extras):
        return self.cliente(usuario or self.admin).post(self.url, {
            "id_tecnico_asignado": (tecnico or self.tecnico).pk, "motivo": motivo, **extras,
        }, format="json")

    def eventos(self):
        return BitacoraAuditoria.objects.filter(accion__in=["TICKET_ASIGNADO", "TICKET_REASIGNADO"])

    def sin_efectos(self):
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.id_tecnico_asignado)
        self.assertEqual(self.ticket.id_estado_ticket.nombre, "Abierto")
        self.assertIsNone(self.ticket.fecha_resolucion)
        self.assertFalse(self.eventos().exists())
        self.assertFalse(Notificacion.objects.exists())
        self.http.assert_not_called()

    def test_asignacion_exitosa_con_respuesta_ticket_y_sin_cambio_de_estado(self):
        antes = Ticket.objects.get(pk=self.ticket.pk)
        response = self.asignar()
        self.assertEqual(response.status_code, 200, response.data)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.id_tecnico_asignado, self.tecnico)
        self.assertEqual(response.data["id_tecnico_asignado"], self.tecnico.pk)
        self.assertEqual(response.data["tecnico_asignado"]["correo"], self.tecnico.correo)
        self.assertEqual(self.ticket.id_estado_ticket, antes.id_estado_ticket)
        self.assertEqual(self.ticket.fecha_creacion, antes.fecha_creacion)
        self.assertEqual(self.ticket.fecha_resolucion, antes.fecha_resolucion)
        detalle = self.cliente(self.admin).get(f"/api/tickets/{self.ticket.pk}/")
        self.assertEqual(response.data, detalle.data)
        self.http.assert_not_called()

    def test_auditoria_contiene_actor_tecnicos_y_motivo_limpio(self):
        self.assertEqual(self.asignar(motivo="  Especialidad requerida  ").status_code, 200)
        evento = self.eventos().get()
        self.assertEqual(evento.accion, "TICKET_ASIGNADO")
        self.assertEqual(evento.id_usuario, self.admin)
        self.assertEqual(evento.id_registro_afectado, self.ticket.pk)
        self.assertEqual(evento.entidad_afectada, "ticket")
        self.assertEqual(evento.direccion_ip, "127.0.0.1")
        for dato in (f"Administrador #{self.admin.pk}", "técnico anterior: None", f"técnico nuevo: {self.tecnico.pk}", "motivo: Especialidad requerida"):
            self.assertIn(dato, evento.detalle_evento)

    def test_reasignacion_registra_anterior_y_nuevo(self):
        self.assertEqual(self.asignar().status_code, 200)
        response = self.asignar(self.segundo, motivo="Cambio de turno")
        self.assertEqual(response.status_code, 200, response.data)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.id_tecnico_asignado, self.segundo)
        evento = self.eventos().get(accion="TICKET_REASIGNADO")
        self.assertIn(f"técnico anterior: {self.tecnico.pk}", evento.detalle_evento)
        self.assertIn(f"técnico nuevo: {self.segundo.pk}", evento.detalle_evento)
        self.assertIn("Cambio de turno", evento.detalle_evento)
        self.assertEqual(Notificacion.objects.count(), 2)

    def test_notificacion_describe_asignacion_sin_afirmar_transicion(self):
        self.assertEqual(self.asignar().status_code, 200)
        aviso = Notificacion.objects.get()
        self.assertEqual(aviso.id_usuario, self.solicitante)
        self.assertEqual(aviso.estado_envio, "PENDIENTE")
        self.assertIn("Asignación de técnico responsable", aviso.mensaje)
        self.assertIn("El estado del ticket no ha cambiado.", aviso.mensaje)
        self.assertIn("Abierto", aviso.titulo)
        self.assertIn(reverse("tickets_web:detalle", kwargs={"pk": self.ticket.pk}), aviso.datos_envio["html"])
        self.http.assert_not_called()

    def test_administrador_sin_permiso_rechazado(self):
        rol = Rol.objects.get(nombre="Administrador del sistema")
        RolPermiso.objects.filter(rol=rol, permiso__codigo="TICKET_ASIGNAR").delete()
        self.assertEqual(self.asignar().status_code, 403)
        self.sin_efectos()

    def test_permiso_sin_rol_admin_y_roles_falsificados_no_autorizan(self):
        rol = Rol.objects.get(nombre="Usuario solicitante")
        RolPermiso.objects.get_or_create(rol=rol, permiso=Permiso.objects.get(codigo="TICKET_ASIGNAR"))
        for usuario in (self.solicitante, self.tecnico):
            with self.subTest(usuario=usuario.pk):
                self.assertEqual(self.asignar(usuario=usuario).status_code, 403)
        self.sin_efectos()

    def test_anonimo_y_admin_inactivo_rechazados(self):
        self.assertEqual(self.cliente().post(self.url, {"id_tecnico_asignado": self.tecnico.pk, "motivo": "Asignar"}, format="json").status_code, 403)
        self.admin.activo = False
        self.admin.save(update_fields=["activo"])
        self.assertEqual(self.asignar().status_code, 403)
        self.sin_efectos()

    def test_tecnico_inexistente_inactivo_o_sin_rol(self):
        self.segundo.activo = False
        self.segundo.save(update_fields=["activo"])
        for identificador in (999999, self.segundo.pk, self.solicitante.pk):
            with self.subTest(identificador=identificador):
                response = self.asignar(id_tecnico_asignado=identificador)
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn("id_tecnico_asignado", response.data)
                self.sin_efectos()

    def test_tecnico_sin_permiso_atender_rechazado(self):
        rol = Rol.objects.get(nombre="Técnico de soporte")
        RolPermiso.objects.filter(rol=rol, permiso__codigo="TICKET_ATENDER").delete()
        self.assertEqual(self.asignar().status_code, 400)
        self.sin_efectos()

    def test_permiso_atender_sin_rol_tecnico_no_es_destinatario_valido(self):
        rol = Rol.objects.get(nombre="Usuario solicitante")
        RolPermiso.objects.get_or_create(rol=rol, permiso=Permiso.objects.get(codigo="TICKET_ATENDER"))
        self.assertEqual(self.asignar(self.solicitante).status_code, 400)
        self.sin_efectos()

    def test_ticket_inexistente(self):
        self.url = reverse("ticket-asignar", kwargs={"pk": 999999})
        response = self.asignar()
        self.assertEqual(response.status_code, 404)
        self.sin_efectos()

    def test_resuelto_o_cerrado_no_admite_asignacion_ni_reasignacion(self):
        for estado in ("Resuelto", "Cerrado"):
            for anterior in (None, self.tecnico):
                with self.subTest(estado=estado, anterior=anterior):
                    self.ticket.id_estado_ticket = EstadoTicket.objects.get(nombre=estado)
                    self.ticket.id_tecnico_asignado = anterior
                    self.ticket.save(update_fields=["id_estado_ticket", "id_tecnico_asignado"])
                    response = self.asignar(self.segundo)
                    self.assertEqual(response.status_code, 400)
                    self.ticket.refresh_from_db()
                    self.assertEqual(self.ticket.id_tecnico_asignado, anterior)
        self.assertFalse(self.eventos().exists())
        self.assertFalse(Notificacion.objects.exists())

    def test_mismo_tecnico_no_crea_nueva_auditoria_ni_aviso(self):
        self.assertEqual(self.asignar().status_code, 200)
        self.assertEqual(self.asignar().status_code, 400)
        self.assertEqual(self.eventos().count(), 1)
        self.assertEqual(Notificacion.objects.count(), 1)

    def test_asignacion_no_modifica_estados_abierto_en_proceso_en_espera(self):
        for estado in ("Abierto", "En Proceso", "En Espera"):
            with self.subTest(estado=estado):
                self.ticket.id_estado_ticket = EstadoTicket.objects.get(nombre=estado)
                self.ticket.id_tecnico_asignado = None
                self.ticket.save(update_fields=["id_estado_ticket", "id_tecnico_asignado"])
                response = self.asignar()
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["estado"]["nombre"], estado)

    def test_motivo_vacio_y_campos_ausentes_no_escriben(self):
        cliente = self.cliente(self.admin)
        for datos in ({}, {"motivo": "Asignar"}, {"id_tecnico_asignado": self.tecnico.pk}, {"id_tecnico_asignado": self.tecnico.pk, "motivo": " \n\t"}):
            with self.subTest(datos=datos):
                self.assertEqual(cliente.post(self.url, datos, format="json").status_code, 400)
        self.sin_efectos()

    def test_identidad_y_estado_en_payload_no_se_utilizan(self):
        response = self.asignar(id_usuario=self.solicitante.pk, id_estado_ticket=999999, codigo_ticket="MANUAL", id_activo=999999)
        self.assertEqual(response.status_code, 200)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.id_usuario_solicitante, self.solicitante)
        self.assertEqual(self.ticket.id_estado_ticket.nombre, "Abierto")
        self.assertNotEqual(self.ticket.codigo_ticket, "MANUAL")
        self.assertIsNone(self.ticket.id_activo)
        self.assertEqual(self.eventos().get().id_usuario, self.admin)

    def test_servicio_directo_tambien_exige_administrador_y_permiso(self):
        with self.assertRaises(PermissionDenied):
            asignar_ticket(id_ticket=self.ticket.pk, administrador=self.tecnico, id_tecnico_asignado=self.segundo.pk, motivo="Intento directo")
        self.sin_efectos()

    def test_rollback_si_falla_auditoria_o_registro_de_notificacion(self):
        for destino in ("tickets.services.registrar_auditoria", "tickets.services.notificar_actualizacion_ticket"):
            with self.subTest(destino=destino), patch(destino, side_effect=DatabaseError("Fallo simulado")):
                with self.assertRaises(DatabaseError):
                    self.asignar()
                self.sin_efectos()

    def test_rollback_exterior_revierte_asignacion_auditoria_y_aviso(self):
        from django.db import transaction
        with self.assertRaises(ValueError), transaction.atomic():
            asignar_ticket(id_ticket=self.ticket.pk, administrador=self.admin, id_tecnico_asignado=self.tecnico.pk, motivo="Asignar")
            raise ValueError("Rollback exterior deliberado")
        self.sin_efectos()

    def test_fallo_de_envio_no_revierte_asignacion_confirmada(self):
        self.assertEqual(self.asignar().status_code, 200)
        aviso = Notificacion.objects.get()
        with patch("notificaciones.services.enviar_correo", side_effect=ErrorCorreo("Proveedor temporalmente no disponible", transitorio=True)):
            self.assertTrue(despachar_notificacion(aviso.pk))
        self.ticket.refresh_from_db()
        aviso.refresh_from_db()
        self.assertEqual(self.ticket.id_tecnico_asignado, self.tecnico)
        self.assertEqual(self.eventos().count(), 1)
        self.assertEqual(aviso.estado_envio, "ERROR")
        self.assertTrue(aviso.reintento_permitido)

    def test_bearer_admin_usa_autenticacion_existente(self):
        cliente = self.cliente()
        with (
            patch("usuarios.authentication.validar_access_token", return_value={"sub": "identidad-de-prueba"}),
            patch("usuarios.authentication.resolver_usuario_access_token", return_value=self.admin),
        ):
            response = cliente.post(self.url, {"id_tecnico_asignado": self.tecnico.pk, "motivo": "Asignación desde escritorio"}, format="json", HTTP_AUTHORIZATION="Bearer credencial-de-prueba")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.eventos().get().id_usuario, self.admin)

    def test_sesion_web_exige_csrf(self):
        cliente = self.cliente(self.admin, csrf=True)
        datos = {"id_tecnico_asignado": self.tecnico.pk, "motivo": "Asignar"}
        self.assertEqual(cliente.post(self.url, datos, format="json").status_code, 403)
        UsuarioRol.objects.create(usuario=self.admin, rol=Rol.objects.get(nombre="Usuario solicitante"))
        cliente.get("/")
        response = cliente.post(self.url, datos, format="json", HTTP_X_CSRFTOKEN=cliente.cookies["csrftoken"].value)
        self.assertEqual(response.status_code, 200, response.data)

    def test_concurrencia_serializa_reasignaciones_y_conserva_anterior_real(self):
        tomado, intentando, continuar = Event(), Event(), Event()
        real_auditoria = __import__("tickets.services", fromlist=["registrar_auditoria"]).registrar_auditoria
        def auditar(**datos):
            if datos["accion"] == "TICKET_ASIGNADO":
                tomado.set()
                if not continuar.wait(10):
                    raise TimeoutError("No se liberó la primera asignación")
            return real_auditoria(**datos)
        def ejecutar(tecnico, segundo=False):
            try:
                if segundo:
                    intentando.set()
                return self.asignar(tecnico).status_code
            finally:
                connections.close_all()
        with patch("tickets.services.registrar_auditoria", side_effect=auditar), ThreadPoolExecutor(max_workers=2) as pool:
            primero = pool.submit(ejecutar, self.tecnico)
            try:
                self.assertTrue(tomado.wait(10))
                segundo = pool.submit(ejecutar, self.segundo, True)
                self.assertTrue(intentando.wait(10))
                self.assertFalse(segundo.done())
            finally:
                continuar.set()
            self.assertEqual(primero.result(timeout=15), 200)
            self.assertEqual(segundo.result(timeout=15), 200)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.id_tecnico_asignado, self.segundo)
        evento = self.eventos().get(accion="TICKET_REASIGNADO")
        self.assertIn(f"técnico anterior: {self.tecnico.pk}", evento.detalle_evento)
        self.assertEqual(self.eventos().count(), 2)
        self.assertEqual(Notificacion.objects.count(), 2)

    def test_ruta_solo_admite_post_y_consultas_siguen_disponibles(self):
        self.assertEqual(self.cliente(self.admin).get(self.url).status_code, 405)
        for ruta in ("/api/tickets/", f"/api/tickets/{self.ticket.pk}/", "/api/tickets/estados/"):
            self.assertEqual(self.cliente(self.admin).get(ruta).status_code, 200)
        self.sin_efectos()

    def test_reasignar_ticket_no_reasigna_orden_ni_altera_diagnostico(self):
        from activos.models import EstadoActivo
        from ordenes_trabajo.models import Diagnostico
        from ordenes_trabajo.services import crear_orden_trabajo

        activo = self.activo()
        activo.id_estado_activo = EstadoActivo.objects.get(nombre="En revisión")
        activo.save(update_fields=["id_estado_activo"])
        self.ticket.id_activo = activo
        self.ticket.save(update_fields=["id_activo"])
        self.assertEqual(self.asignar().status_code, 200)
        orden = crear_orden_trabajo(
            self.ticket.pk, self.tecnico, "Falla de prueba", "Inspección inicial",
        )
        antes = dict(orden.__dict__)
        diagnostico = Diagnostico.objects.get(id_orden=orden)
        self.assertEqual(self.asignar(self.segundo).status_code, 200)
        orden.refresh_from_db()
        for campo in ("id_tecnico_responsable_id", "id_estado_ot_id", "falla_reportada", "fecha_inicio"):
            self.assertEqual(getattr(orden, campo), antes[campo])
        diagnostico.refresh_from_db()
        self.assertEqual(diagnostico.id_tecnico, self.tecnico)
        self.assertEqual(diagnostico.procedimiento_inicial, "Inspección inicial")
        self.assertEqual(Diagnostico.objects.filter(id_orden=orden).count(), 1)
        activo.refresh_from_db()
        self.assertEqual(activo.id_estado_activo.nombre, "En revisión")
