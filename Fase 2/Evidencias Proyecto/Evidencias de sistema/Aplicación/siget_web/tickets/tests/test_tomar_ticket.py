"""Autoasignación técnica, RBAC real y exclusión mutua en PostgreSQL."""
import hashlib
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

from django.db import DatabaseError, connection, connections
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from notificaciones.models import Notificacion
from tickets.models import ComentarioTicket, EstadoTicket, Ticket
from tickets.serializers import TicketReadSerializer
from tickets.services import crear_ticket, tomar_ticket
from usuarios.models import BitacoraAuditoria, Permiso, Rol, RolPermiso, UsuarioRol
from usuarios.tests.test_integracion_postgresql import PostgreSQLTestBase


@override_settings(SIGET_PUBLIC_URL="https://siget.example.invalid", RESEND_FROM_EMAIL="SIGET <avisos@example.invalid>")
class TomarTicketTests(PostgreSQLTestBase):
    def setUp(self):
        super().setUp()
        self.assertEqual(connection.settings_dict["NAME"], "test_siget_db")
        self.segundo = self.usuario(5, "Técnico de soporte")
        self.ticket = crear_ticket(self.solicitante, "Falla", "Sin conectividad")
        self.url = reverse("ticket-tomar", kwargs={"pk": self.ticket.pk})
        self.antes = Ticket.objects.values().get(pk=self.ticket.pk)
        self.auditorias_previas = BitacoraAuditoria.objects.count()
        self.http_patch = patch("notificaciones.resend_client.requests.post")
        self.http = self.http_patch.start()
        self.addCleanup(self.http_patch.stop)

    def tomar(self, usuario=None):
        return self.cliente(usuario or self.tecnico).post(self.url)

    def sin_efectos(self, esperado=None):
        self.assertEqual(Ticket.objects.values().get(pk=self.ticket.pk), esperado or self.antes)
        self.assertEqual(BitacoraAuditoria.objects.count(), self.auditorias_previas)
        self.assertFalse(Notificacion.objects.exists())
        self.assertFalse(ComentarioTicket.objects.exists())
        self.http.assert_not_called()

    def test_tecnico_toma_sin_cuerpo_y_solo_cambia_responsable(self):
        response = self.tomar()
        self.assertEqual(response.status_code, 200, response.data)
        self.ticket.refresh_from_db()
        esperado = {**self.antes, "id_tecnico_asignado_id": self.tecnico.pk}
        self.assertEqual(Ticket.objects.values().get(pk=self.ticket.pk), esperado)
        self.assertEqual(response.data, TicketReadSerializer(self.ticket).data)
        self.assertFalse(ComentarioTicket.objects.exists())
        self.http.assert_not_called()

    def test_auditoria_y_notificacion_unica_con_evento_real(self):
        antes = timezone.now()
        self.assertEqual(self.tomar().status_code, 200)
        evento = BitacoraAuditoria.objects.get(accion="TICKET_TOMADO")
        self.assertEqual(evento.id_usuario, self.tecnico)
        self.assertEqual(evento.entidad_afectada, "ticket")
        self.assertEqual(evento.id_registro_afectado, self.ticket.pk)
        self.assertEqual(evento.direccion_ip, "127.0.0.1")
        self.assertGreaterEqual(evento.fecha_evento, antes)
        self.assertIn(f"técnico #{self.tecnico.pk}", evento.detalle_evento)
        clave = hashlib.sha256(f"ticket:{self.ticket.pk}:actualizacion:{evento.pk}".encode()).hexdigest()
        aviso = Notificacion.objects.get(clave_evento=clave)
        self.assertEqual(aviso.id_usuario, self.solicitante)
        self.assertEqual(aviso.estado_envio, "PENDIENTE")
        self.assertEqual(Notificacion.objects.count(), 1)
        self.assertIn("tomó el ticket", aviso.mensaje)
        self.assertEqual(self.tomar().status_code, 400)
        self.assertEqual(Notificacion.objects.count(), 1)
        self.assertEqual(BitacoraAuditoria.objects.filter(accion="TICKET_TOMADO").count(), 1)

    def test_solicitante_y_administrador_sin_rol_tecnico_rechazados(self):
        for usuario in (self.solicitante, self.admin):
            with self.subTest(usuario=usuario.pk):
                self.assertEqual(self.tomar(usuario).status_code, 403)
        self.sin_efectos()

    def test_tecnico_inactivo(self):
        self.tecnico.activo = False
        self.tecnico.save(update_fields=["activo"])
        self.assertEqual(self.tomar().status_code, 403)
        self.sin_efectos()

    def test_tecnico_sin_permiso(self):
        RolPermiso.objects.filter(rol__nombre="Técnico de soporte", permiso__codigo="TICKET_ATENDER").delete()
        self.assertEqual(self.tomar().status_code, 403)
        self.sin_efectos()

    def test_permiso_sin_rol_y_rol_falsificado_no_autorizan(self):
        RolPermiso.objects.get_or_create(rol=Rol.objects.get(nombre="Usuario solicitante"),
                                        permiso=Permiso.objects.get(codigo="TICKET_ATENDER"))
        self.assertEqual(self.tomar(self.solicitante).status_code, 403)
        self.sin_efectos()

    def test_admin_que_tambien_es_tecnico_puede_tomar(self):
        UsuarioRol.objects.create(usuario=self.admin, rol=Rol.objects.get(nombre="Técnico de soporte"))
        self.assertEqual(self.tomar(self.admin).status_code, 200)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.id_tecnico_asignado, self.admin)

    def test_ticket_inexistente(self):
        self.url = reverse("ticket-tomar", kwargs={"pk": 999999})
        self.assertEqual(self.tomar().status_code, 404)
        self.sin_efectos()

    def test_ticket_asignado_a_otro_o_al_mismo_tecnico_no_disponible(self):
        for tecnico in (self.segundo, self.tecnico):
            with self.subTest(tecnico=tecnico.pk):
                self.ticket.id_tecnico_asignado = tecnico
                self.ticket.save(update_fields=["id_tecnico_asignado"])
                esperado = Ticket.objects.values().get(pk=self.ticket.pk)
                response = self.tomar()
                self.assertEqual(response.status_code, 400)
                self.assertIn("no está disponible", str(response.data["detail"]))
                self.sin_efectos(esperado)

    def test_solo_abierto_y_cerrado_con_mensaje_explicito(self):
        for estado in ("En Proceso", "En Espera", "Resuelto", "Cerrado"):
            with self.subTest(estado=estado):
                self.ticket.id_estado_ticket = EstadoTicket.objects.get(nombre=estado)
                self.ticket.save(update_fields=["id_estado_ticket"])
                esperado = Ticket.objects.values().get(pk=self.ticket.pk)
                response = self.tomar()
                self.assertEqual(response.status_code, 400)
                if estado == "Cerrado":
                    self.assertEqual(str(response.data["detail"]), "El ticket está Cerrado y no puede ser modificado.")
                self.sin_efectos(esperado)

    def test_cuerpo_con_identidad_u_otros_campos_rechazado(self):
        for datos in ({"id_tecnico_asignado": self.segundo.pk}, {"id_usuario": self.admin.pk}, {"motivo": "Intento"}):
            self.assertEqual(self.cliente(self.tecnico).post(self.url, datos, format="json").status_code, 400)
        self.sin_efectos()
        self.assertEqual(self.cliente(self.tecnico).post(self.url, {}, format="json").status_code, 200)

    def test_rollback_auditoria_y_notificacion(self):
        for destino in ("tickets.services.registrar_auditoria", "tickets.services.notificar_actualizacion_ticket"):
            with self.subTest(destino=destino), patch(destino, side_effect=DatabaseError("Fallo simulado")):
                with self.assertRaises(DatabaseError):
                    self.tomar()
                self.sin_efectos()

    def test_servicio_directo_exige_rbac(self):
        with self.assertRaises(PermissionDenied):
            tomar_ticket(id_ticket=self.ticket.pk, tecnico=self.admin)
        self.sin_efectos()

    def test_bearer(self):
        with (patch("usuarios.authentication.validar_access_token", return_value={"sub": "prueba"}),
              patch("usuarios.authentication.resolver_usuario_access_token", return_value=self.tecnico)):
            response = self.cliente().post(self.url, HTTP_AUTHORIZATION="Bearer credencial-de-prueba")
        self.assertEqual(response.status_code, 200, response.data)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.id_tecnico_asignado, self.tecnico)

    def test_anonimo_csrf_y_metodo(self):
        self.assertEqual(self.cliente().post(self.url).status_code, 403)
        cliente = self.cliente(self.tecnico, csrf=True)
        self.assertEqual(cliente.post(self.url).status_code, 403)
        self.assertEqual(self.cliente(self.tecnico).get(self.url).status_code, 405)
        self.sin_efectos()
        UsuarioRol.objects.create(usuario=self.tecnico, rol=Rol.objects.get(nombre="Usuario solicitante"))
        cliente.get("/")
        response = cliente.post(self.url, HTTP_X_CSRFTOKEN=cliente.cookies["csrftoken"].value)
        self.assertEqual(response.status_code, 200, response.data)

    def test_consulta_tecnica_incluye_ticket_disponible_sin_ampliar_acceso(self):
        r = self.cliente(self.tecnico).get("/api/tickets/?estado=Abierto")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn(self.ticket.pk, [t["id_ticket"] for t in r.data])
        detalle = self.cliente(self.tecnico).get(f"/api/tickets/{self.ticket.pk}/")
        self.assertEqual(detalle.status_code, 200)
        self.assertIsNone(detalle.data["id_tecnico_asignado"])
        self.assertEqual(self.cliente(self.otro).get(f"/api/tickets/{self.ticket.pk}/").status_code, 403)

    def test_administrador_conserva_reasignacion_despues_de_tomar(self):
        self.assertEqual(self.tomar().status_code, 200)
        r = self.cliente(self.admin).post(f"/api/tickets/{self.ticket.pk}/asignar/", {
            "id_tecnico_asignado": self.segundo.pk, "motivo": "Cambio de turno"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.id_tecnico_asignado, self.segundo)
        self.assertEqual(self.tomar().status_code, 400)

    def test_dos_tecnicos_concurrentes_solo_uno_toma(self):
        tomado, intentando, continuar = Event(), Event(), Event()
        from tickets.services import registrar_auditoria as auditar_real
        def auditar(**datos):
            if datos["accion"] == "TICKET_TOMADO":
                tomado.set()
                if not continuar.wait(10):
                    raise TimeoutError("Autoasignación no liberada")
            return auditar_real(**datos)
        def ejecutar(usuario):
            conexion = connections["default"]
            def observar_sql(execute, sql, params, many, context):
                if "FOR UPDATE" in sql and '"ticket"' in sql:
                    intentando.set()
                return execute(sql, params, many, context)
            try:
                with conexion.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '8s'")
                with conexion.execute_wrapper(observar_sql):
                    return self.tomar(usuario).status_code
            finally:
                connections.close_all()
        with patch("tickets.services.registrar_auditoria", side_effect=auditar), ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(ejecutar, self.tecnico)
            try:
                self.assertTrue(tomado.wait(10))
                intentando.clear()
                b = pool.submit(ejecutar, self.segundo)
                self.assertTrue(intentando.wait(10))
                self.assertFalse(b.done())
            finally:
                continuar.set()
            self.assertEqual((a.result(timeout=15), b.result(timeout=15)), (200, 400))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.id_tecnico_asignado, self.tecnico)
        self.assertEqual(BitacoraAuditoria.objects.filter(accion="TICKET_TOMADO").count(), 1)
        self.assertEqual(Notificacion.objects.count(), 1)
        self.http.assert_not_called()
