"""Atenciones técnicas: contrato REST y persistencia atómica en PostgreSQL."""
import hashlib
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

from django.db import DatabaseError, connection, connections
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from notificaciones.models import Notificacion
from tickets.models import ComentarioTicket, EstadoTicket
from tickets.serializers import TicketAtencionCreateSerializer
from tickets.services import asignar_ticket, crear_ticket, registrar_atencion_ticket
from usuarios.models import BitacoraAuditoria, Rol, RolPermiso, UsuarioRol
from usuarios.tests.test_integracion_postgresql import PostgreSQLTestBase


class AtencionSerializerTests(SimpleTestCase):
    def test_mensaje_obligatorio_y_sin_blancos(self):
        for datos in ({}, {"mensaje": None}, {"mensaje": ""}, {"mensaje": " \n\t"}):
            with self.subTest(datos=datos):
                serializer = TicketAtencionCreateSerializer(data=datos)
                self.assertFalse(serializer.is_valid())
                self.assertIn("mensaje", serializer.errors)

    def test_mensaje_limpio_y_campos_servidor_ignorados(self):
        serializer = TicketAtencionCreateSerializer(data={
            "mensaje": "  Revisión realizada  ", "id_usuario": 999, "fecha_registro": "2000-01-01",
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data, {"mensaje": "Revisión realizada"})


@override_settings(SIGET_PUBLIC_URL="https://siget.example.invalid", RESEND_FROM_EMAIL="SIGET <avisos@example.invalid>")
class AtencionesPostgreSQLTests(PostgreSQLTestBase):
    def setUp(self):
        super().setUp()
        self.assertEqual(connection.settings_dict["NAME"], "test_siget_db")
        self.segundo = self.usuario(5, "Técnico de soporte")
        self.ticket = crear_ticket(self.solicitante, "Falla", "Sin conectividad")
        asignar_ticket(id_ticket=self.ticket.pk, administrador=self.admin,
                       id_tecnico_asignado=self.tecnico.pk, motivo="Especialidad")
        self.url = reverse("ticket-atenciones", kwargs={"pk": self.ticket.pk})
        self.avisos_previos = Notificacion.objects.count()
        self.auditorias_previas = BitacoraAuditoria.objects.count()
        self.http_patch = patch("notificaciones.resend_client.requests.post")
        self.http = self.http_patch.start()
        self.addCleanup(self.http_patch.stop)

    def atender(self, usuario=None, **datos):
        return self.cliente(usuario or self.tecnico).post(
            self.url, {"mensaje": "Revisión realizada", **datos}, format="json",
        )

    def sin_efectos(self):
        self.assertFalse(ComentarioTicket.objects.exists())
        self.assertEqual(Notificacion.objects.count(), self.avisos_previos)
        self.assertEqual(BitacoraAuditoria.objects.count(), self.auditorias_previas)
        self.http.assert_not_called()

    def test_creacion_persistencia_contrato_autor_y_fecha_del_servidor(self):
        antes = timezone.now()
        response = self.atender(mensaje="  Conectividad verificada  ", id_usuario=self.admin.pk,
                                fecha_registro="2000-01-01T00:00:00Z", id_ticket=999999)
        self.assertEqual(response.status_code, 201, response.data)
        comentario = ComentarioTicket.objects.get()
        self.assertEqual(set(response.data), {"id_comentario", "id_ticket", "id_usuario", "mensaje", "fecha_registro"})
        self.assertEqual(response.data["id_comentario"], comentario.pk)
        self.assertEqual(response.data["id_ticket"], self.ticket.pk)
        self.assertEqual(response.data["id_usuario"], self.tecnico.pk)
        self.assertEqual(response.data["mensaje"], "Conectividad verificada")
        self.assertTrue(response.data["fecha_registro"])
        self.assertEqual(comentario.id_usuario, self.tecnico)
        self.assertEqual(comentario.id_ticket, self.ticket)
        self.assertGreaterEqual(comentario.fecha_registro, antes)
        self.assertLessEqual(comentario.fecha_registro, timezone.now())
        self.http.assert_not_called()

    def test_auditoria_y_aviso_con_id_real_de_auditoria_sin_duplicaciones(self):
        self.assertEqual(self.atender().status_code, 201)
        comentario = ComentarioTicket.objects.get()
        evento = BitacoraAuditoria.objects.get(accion="TICKET_ATENDIDO")
        self.assertEqual(evento.id_usuario, self.tecnico)
        self.assertEqual(evento.entidad_afectada, "comentario_ticket")
        self.assertEqual(evento.id_registro_afectado, comentario.pk)
        self.assertEqual(evento.direccion_ip, "127.0.0.1")
        self.assertIn(f"ticket #{self.ticket.pk}", evento.detalle_evento)
        self.assertIn(comentario.mensaje, evento.detalle_evento)
        clave = hashlib.sha256(f"ticket:{self.ticket.pk}:actualizacion:{evento.pk}".encode()).hexdigest()
        aviso = Notificacion.objects.get(clave_evento=clave)
        self.assertEqual(aviso.id_usuario, self.solicitante)
        self.assertEqual(aviso.estado_envio, "PENDIENTE")
        self.assertIn(comentario.mensaje, aviso.mensaje)
        self.assertEqual(Notificacion.objects.count(), self.avisos_previos + 1)
        self.assertEqual(BitacoraAuditoria.objects.count(), self.auditorias_previas + 1)
        self.http.assert_not_called()

    def test_tecnico_no_asignado_admin_y_solicitante_rechazados(self):
        for usuario in (self.segundo, self.admin, self.solicitante):
            with self.subTest(usuario=usuario.pk):
                self.assertEqual(self.atender(usuario).status_code, 403)
        self.sin_efectos()

    def test_ticket_sin_tecnico_rechazado(self):
        self.ticket.id_tecnico_asignado = None
        self.ticket.save(update_fields=["id_tecnico_asignado"])
        self.assertEqual(self.atender().status_code, 403)
        self.sin_efectos()

    def test_tecnico_inactivo(self):
        self.tecnico.activo = False
        self.tecnico.save(update_fields=["activo"])
        self.assertEqual(self.atender().status_code, 403)
        self.sin_efectos()

    def test_tecnico_sin_permiso(self):
        RolPermiso.objects.filter(rol__nombre="Técnico de soporte", permiso__codigo="TICKET_ATENDER").delete()
        self.assertEqual(self.atender().status_code, 403)
        self.sin_efectos()

    def test_permiso_sin_rol_tecnico_no_autoriza(self):
        UsuarioRol.objects.filter(usuario=self.tecnico).delete()
        rol_admin = Rol.objects.get(nombre="Administrador del sistema")
        UsuarioRol.objects.create(usuario=self.tecnico, rol=rol_admin)
        from usuarios.models import Permiso
        RolPermiso.objects.get_or_create(rol=rol_admin, permiso=Permiso.objects.get(codigo="TICKET_ATENDER"))
        self.assertEqual(self.atender().status_code, 403)
        self.sin_efectos()

    def test_ticket_inexistente(self):
        self.url = reverse("ticket-atenciones", kwargs={"pk": 999999})
        self.assertEqual(self.atender().status_code, 404)
        self.sin_efectos()

    def test_resuelto_y_cerrado_rechazados(self):
        for estado in ("Resuelto", "Cerrado"):
            with self.subTest(estado=estado):
                self.ticket.id_estado_ticket = EstadoTicket.objects.get(nombre=estado)
                self.ticket.save(update_fields=["id_estado_ticket"])
                self.assertEqual(self.atender().status_code, 400)
        self.sin_efectos()

    def test_estados_activos_aceptados_sin_alterar_ticket(self):
        for estado in ("Abierto", "En Proceso", "En Espera"):
            with self.subTest(estado=estado):
                self.ticket.id_estado_ticket = EstadoTicket.objects.get(nombre=estado)
                self.ticket.save(update_fields=["id_estado_ticket"])
                antes = (self.ticket.id_estado_ticket_id, self.ticket.fecha_creacion, self.ticket.fecha_resolucion)
                self.assertEqual(self.atender().status_code, 201)
                self.ticket.refresh_from_db()
                self.assertEqual((self.ticket.id_estado_ticket_id, self.ticket.fecha_creacion, self.ticket.fecha_resolucion), antes)
                self.assertEqual(self.ticket.id_tecnico_asignado, self.tecnico)
        self.assertEqual(ComentarioTicket.objects.count(), 3)

    def test_mensaje_invalido_no_escribe(self):
        for datos in ({}, {"mensaje": ""}, {"mensaje": " \n\t"}, {"mensaje": None}):
            with self.subTest(datos=datos):
                response = self.cliente(self.tecnico).post(self.url, datos, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn("mensaje", response.data)
        self.sin_efectos()

    def test_servicio_directo_valida_rol_y_mensaje(self):
        from rest_framework.exceptions import ValidationError
        with self.assertRaises(PermissionDenied):
            registrar_atencion_ticket(id_ticket=self.ticket.pk, tecnico=self.admin, mensaje="Intento")
        with self.assertRaises(ValidationError):
            registrar_atencion_ticket(id_ticket=self.ticket.pk, tecnico=self.tecnico, mensaje="   ")
        self.sin_efectos()

    def test_rollback_auditoria_y_notificacion(self):
        for destino in ("tickets.services.registrar_auditoria", "tickets.services.notificar_actualizacion_ticket"):
            with self.subTest(destino=destino), patch(destino, side_effect=DatabaseError("Fallo simulado")):
                with self.assertRaises(DatabaseError):
                    self.atender()
                self.sin_efectos()

    def test_bearer_valido_y_bearer_invalido(self):
        cliente = self.cliente()
        with (patch("usuarios.authentication.validar_access_token", return_value={"sub": "tecnico-prueba"}),
              patch("usuarios.authentication.resolver_usuario_access_token", return_value=self.tecnico)):
            response = cliente.post(self.url, {"mensaje": "Atención desde escritorio"}, format="json",
                                   HTTP_AUTHORIZATION="Bearer credencial-de-prueba")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(ComentarioTicket.objects.get().id_usuario, self.tecnico)
        from rest_framework.exceptions import AuthenticationFailed
        with patch("usuarios.authentication.validar_access_token", side_effect=AuthenticationFailed("Token inválido")):
            response = cliente.post(self.url, {"mensaje": "No autorizado"}, format="json",
                                   HTTP_AUTHORIZATION="Bearer invalido")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(ComentarioTicket.objects.count(), 1)

    def test_anonimo_y_csrf(self):
        self.assertEqual(self.cliente().post(self.url, {"mensaje": "Intento"}, format="json").status_code, 403)
        cliente = self.cliente(self.tecnico, csrf=True)
        self.assertEqual(cliente.post(self.url, {"mensaje": "Intento"}, format="json").status_code, 403)
        self.sin_efectos()
        UsuarioRol.objects.create(usuario=self.tecnico, rol=Rol.objects.get(nombre="Usuario solicitante"))
        cliente.get("/")
        response = cliente.post(self.url, {"mensaje": "Atención web"}, format="json",
                               HTTP_X_CSRFTOKEN=cliente.cookies["csrftoken"].value)
        self.assertEqual(response.status_code, 201, response.data)

    def test_ruta_solo_post(self):
        self.assertEqual(self.url, f"/api/tickets/{self.ticket.pk}/atenciones/")
        self.assertEqual(self.cliente(self.tecnico).get(self.url).status_code, 405)
        self.sin_efectos()

    def ejecutar_conexion(self, operacion):
        try:
            return operacion()
        finally:
            connections.close_all()

    def test_reasignacion_concurrente_revoca_al_tecnico_anterior_antes_de_atender(self):
        tomado, intentando, continuar = Event(), Event(), Event()
        from tickets.services import registrar_auditoria as auditar_real

        def auditar(**datos):
            if datos["accion"] == "TICKET_REASIGNADO":
                tomado.set()
                if not continuar.wait(10):
                    raise TimeoutError("Reasignación no liberada")
            return auditar_real(**datos)

        def reasignar():
            return self.cliente(self.admin).post(reverse("ticket-asignar", kwargs={"pk": self.ticket.pk}),
                {"id_tecnico_asignado": self.segundo.pk, "motivo": "Cambio de turno"}, format="json").status_code

        def atender():
            intentando.set()
            return self.atender().status_code

        with patch("tickets.services.registrar_auditoria", side_effect=auditar), ThreadPoolExecutor(max_workers=2) as pool:
            primero = pool.submit(self.ejecutar_conexion, reasignar)
            try:
                self.assertTrue(tomado.wait(10))
                segundo = pool.submit(self.ejecutar_conexion, atender)
                self.assertTrue(intentando.wait(10))
                self.assertFalse(segundo.done())
            finally:
                continuar.set()
            self.assertEqual(primero.result(timeout=15), 200)
            self.assertEqual(segundo.result(timeout=15), 403)
        self.assertFalse(ComentarioTicket.objects.exists())
        self.assertFalse(BitacoraAuditoria.objects.filter(accion="TICKET_ATENDIDO").exists())
        self.assertEqual(Notificacion.objects.count(), self.avisos_previos + 1)
        self.assertEqual(self.atender(self.segundo).status_code, 201)

    def test_atencion_concurrente_se_confirma_antes_de_reasignar(self):
        tomado, intentando, continuar = Event(), Event(), Event()
        from tickets.services import registrar_auditoria as auditar_real

        def auditar(**datos):
            if datos["accion"] == "TICKET_ATENDIDO":
                tomado.set()
                if not continuar.wait(10):
                    raise TimeoutError("Atención no liberada")
            return auditar_real(**datos)

        def reasignar():
            intentando.set()
            return self.cliente(self.admin).post(reverse("ticket-asignar", kwargs={"pk": self.ticket.pk}),
                {"id_tecnico_asignado": self.segundo.pk, "motivo": "Cambio de turno"}, format="json").status_code

        with patch("tickets.services.registrar_auditoria", side_effect=auditar), ThreadPoolExecutor(max_workers=2) as pool:
            primero = pool.submit(self.ejecutar_conexion, lambda: self.atender().status_code)
            try:
                self.assertTrue(tomado.wait(10))
                segundo = pool.submit(self.ejecutar_conexion, reasignar)
                self.assertTrue(intentando.wait(10))
                self.assertFalse(segundo.done())
            finally:
                continuar.set()
            self.assertEqual(primero.result(timeout=15), 201)
            self.assertEqual(segundo.result(timeout=15), 200)
        self.assertEqual(ComentarioTicket.objects.get().id_usuario, self.tecnico)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.id_tecnico_asignado, self.segundo)
        self.assertEqual(Notificacion.objects.count(), self.avisos_previos + 2)
