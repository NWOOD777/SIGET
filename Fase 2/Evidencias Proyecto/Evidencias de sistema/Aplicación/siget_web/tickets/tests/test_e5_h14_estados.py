"""Contrato y persistencia de transiciones E5-H14."""
import hashlib
from unittest.mock import patch

from django.db import DatabaseError, connection
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from notificaciones.models import Notificacion
from tickets.models import ComentarioTicket, EstadoTicket
from tickets.serializers import TicketEstadoSerializer, TicketReadSerializer
from tickets.services import asignar_ticket, cambiar_estado_ticket, crear_ticket
from usuarios.models import BitacoraAuditoria, Permiso, Rol, RolPermiso, UsuarioRol
from usuarios.tests.test_integracion_postgresql import PostgreSQLTestBase


class EstadoSerializerTests(SimpleTestCase):
    def test_campos_obligatorios_y_valores_invalidos(self):
        for datos in ({}, {"id_estado_ticket": 1}, {"mensaje": "Motivo"},
                      {"id_estado_ticket": 1, "mensaje": " \n\t"},
                      {"id_estado_ticket": 1, "mensaje": None},
                      {"id_estado_ticket": 0, "mensaje": "Motivo"},
                      {"id_estado_ticket": 2147483648, "mensaje": "Motivo"}):
            with self.subTest(datos=datos):
                self.assertFalse(TicketEstadoSerializer(data=datos).is_valid())


@override_settings(SIGET_PUBLIC_URL="https://siget.example.invalid", RESEND_FROM_EMAIL="SIGET <avisos@example.invalid>")
class EstadoFixture(PostgreSQLTestBase):
    def setUp(self):
        super().setUp()
        self.assertEqual(connection.settings_dict["NAME"], "test_siget_db")
        with connection.cursor() as cursor:
            cursor.execute("SHOW transaction_isolation")
            self.assertEqual(cursor.fetchone()[0], "read committed")
        self.estados = {e.nombre: e for e in EstadoTicket.objects.all()}
        self.segundo = self.usuario(5, "Técnico de soporte")
        self.ticket = crear_ticket(self.solicitante, "Falla", "Sin conectividad")
        asignar_ticket(id_ticket=self.ticket.pk, administrador=self.admin,
                       id_tecnico_asignado=self.tecnico.pk, motivo="Especialidad")
        self.url = reverse("ticket-estado", kwargs={"pk": self.ticket.pk})
        self.base_auditoria = BitacoraAuditoria.objects.count()
        self.base_avisos = Notificacion.objects.count()
        self.http_patch = patch("notificaciones.resend_client.requests.post")
        self.http = self.http_patch.start()
        self.addCleanup(self.http_patch.stop)

    def origen(self, nombre):
        self.ticket.id_estado_ticket = self.estados[nombre]
        self.ticket.save(update_fields=["id_estado_ticket"])

    def cambiar(self, destino="En Proceso", usuario=None, **extra):
        return self.cliente(usuario or self.tecnico).patch(self.url, {
            "id_estado_ticket": self.estados[destino].pk, "mensaje": "  Revisión documentada  ", **extra,
        }, format="json")

    def sin_efectos(self):
        self.assertFalse(ComentarioTicket.objects.exists())
        self.assertEqual(BitacoraAuditoria.objects.count(), self.base_auditoria)
        self.assertEqual(Notificacion.objects.count(), self.base_avisos)
        self.http.assert_not_called()


class EstadoTicketTests(EstadoFixture):
    def test_cerrado_mensaje_explicito_y_sin_efectos_en_los_tres_endpoints(self):
        self.origen("Cerrado")
        antes = type(self.ticket).objects.values().get(pk=self.ticket.pk)
        operaciones = (
            lambda: self.cambiar("En Proceso"),
            lambda: self.cliente(self.tecnico).post(f"/api/tickets/{self.ticket.pk}/atenciones/",
                                                   {"mensaje": "Intento"}, format="json"),
            lambda: self.cliente(self.admin).post(f"/api/tickets/{self.ticket.pk}/asignar/",
                {"id_tecnico_asignado": self.segundo.pk, "motivo": "Intento"}, format="json"),
        )
        for numero, operacion in enumerate(operaciones):
            with self.subTest(endpoint=numero):
                response = operacion()
                self.assertEqual(response.status_code, 400)
                self.assertEqual(str(response.data["detail"]), "El ticket está Cerrado y no puede ser modificado.")
                self.assertEqual(type(self.ticket).objects.values().get(pk=self.ticket.pk), antes)
                self.sin_efectos()

    def test_ciclo_de_vida_completo_persistido_con_trazabilidad(self):
        # El fixture tiene otro ticket asignado; este recorre el ciclo desde cero.
        ticket = crear_ticket(self.solicitante, "Ciclo completo", "Incidente de prueba sin activo")
        self.assertEqual(ticket.id_estado_ticket.nombre, "Abierto")
        self.assertIsNone(ticket.id_tecnico_asignado)
        auditorias_antes = BitacoraAuditoria.objects.count()
        avisos_antes = Notificacion.objects.count()
        url = f"/api/tickets/{ticket.pk}/"
        r = self.cliente(self.admin).post(url + "asignar/", {
            "id_tecnico_asignado": self.tecnico.pk, "motivo": "Asignación inicial del ciclo"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        ticket.refresh_from_db()
        self.assertEqual(ticket.id_tecnico_asignado, self.tecnico)
        self.assertEqual(ticket.id_estado_ticket.nombre, "Abierto")
        r = self.cliente(self.tecnico).post(url + "atenciones/", {"mensaje": "Primera revisión"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        mensajes = ["Primera revisión"]
        fecha_resolucion = None
        for paso, estado in enumerate(("En Proceso", "En Espera", "En Proceso", "Resuelto", "Cerrado"), 1):
            mensaje = f"Paso {paso}: {estado}"
            antes = timezone.now()
            r = self.cliente(self.tecnico).patch(url + "estado/", {
                "id_estado_ticket": self.estados[estado].pk, "mensaje": mensaje}, format="json")
            self.assertEqual(r.status_code, 200, r.data)
            ticket.refresh_from_db()
            self.assertEqual(ticket.id_estado_ticket.nombre, estado)
            mensajes.append(mensaje)
            if estado == "Resuelto":
                fecha_resolucion = ticket.fecha_resolucion
                self.assertGreaterEqual(fecha_resolucion, antes)
                self.assertLessEqual(fecha_resolucion, timezone.now())
            elif estado == "Cerrado":
                self.assertEqual(ticket.fecha_resolucion, fecha_resolucion)
            else:
                self.assertIsNone(ticket.fecha_resolucion)
        comentarios = ComentarioTicket.objects.filter(id_ticket=ticket).order_by("id_comentario")
        self.assertEqual(list(comentarios.values_list("mensaje", flat=True)), mensajes)
        self.assertEqual(set(comentarios.values_list("id_usuario_id", flat=True)), {self.tecnico.pk})
        # No se presupone que los IDs de auditoría sean consecutivos.
        eventos = BitacoraAuditoria.objects.exclude(accion="TICKET_CREADO").filter(
            id_auditoria__gt=BitacoraAuditoria.objects.get(accion="TICKET_CREADO", id_registro_afectado=ticket.pk).pk
        ).order_by("id_auditoria")
        self.assertEqual(list(eventos.values_list("accion", flat=True)),
                         ["TICKET_ASIGNADO", "TICKET_ATENDIDO"] + ["TICKET_ESTADO_CAMBIADO"] * 5)
        for evento in eventos:
            self.assertEqual(evento.id_usuario, self.admin if evento.accion == "TICKET_ASIGNADO" else self.tecnico)
            clave = hashlib.sha256(f"ticket:{ticket.pk}:actualizacion:{evento.pk}".encode()).hexdigest()
            aviso = Notificacion.objects.get(clave_evento=clave)
            self.assertEqual(aviso.id_usuario, self.solicitante)
            self.assertEqual(aviso.estado_envio, "PENDIENTE")
        self.assertEqual(BitacoraAuditoria.objects.count(), auditorias_antes + 7)
        self.assertEqual(Notificacion.objects.count(), avisos_antes + 7)
        antes_ticket = type(ticket).objects.values().get(pk=ticket.pk)
        r = self.cliente(self.tecnico).patch(url + "estado/", {
            "id_estado_ticket": self.estados["En Proceso"].pk, "mensaje": "Intento de reapertura"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(str(r.data["detail"]), "El ticket está Cerrado y no puede ser modificado.")
        self.assertEqual(type(ticket).objects.values().get(pk=ticket.pk), antes_ticket)
        self.assertEqual(comentarios.count(), 6)
        self.assertEqual(BitacoraAuditoria.objects.count(), auditorias_antes + 7)
        self.assertEqual(Notificacion.objects.count(), avisos_antes + 7)
        self.http.assert_not_called()

    def test_matriz_completa_25_combinaciones(self):
        permitidas = {("Abierto", "En Proceso"), ("En Proceso", "En Espera"),
                      ("En Espera", "En Proceso"), ("En Proceso", "Resuelto"), ("Resuelto", "Cerrado")}
        for origen in self.estados:
            for destino in self.estados:
                with self.subTest(origen=origen, destino=destino):
                    self.origen(origen)
                    antes = (ComentarioTicket.objects.count(), BitacoraAuditoria.objects.count(), Notificacion.objects.count())
                    response = self.cambiar(destino)
                    valido = (origen, destino) in permitidas
                    self.assertEqual(response.status_code, 200 if valido else 400, response.data)
                    self.ticket.refresh_from_db()
                    self.assertEqual(self.ticket.id_estado_ticket.nombre, destino if valido else origen)
                    despues = (ComentarioTicket.objects.count(), BitacoraAuditoria.objects.count(), Notificacion.objects.count())
                    self.assertEqual(despues, tuple(n + int(valido) for n in antes))
        self.http.assert_not_called()

    def test_respuesta_comentario_auditoria_y_notificacion_unica(self):
        response = self.cambiar(id_usuario=self.admin.pk, fecha_registro="2000-01-01", fecha_resolucion="2000-01-01")
        self.assertEqual(response.status_code, 200, response.data)
        self.ticket.refresh_from_db()
        self.assertEqual(response.data, TicketReadSerializer(self.ticket).data)
        comentario = ComentarioTicket.objects.get()
        self.assertEqual(comentario.id_usuario, self.tecnico)
        self.assertEqual(comentario.id_ticket, self.ticket)
        self.assertEqual(comentario.mensaje, "Revisión documentada")
        evento = BitacoraAuditoria.objects.get(accion="TICKET_ESTADO_CAMBIADO")
        self.assertEqual(evento.id_usuario, self.tecnico)
        self.assertEqual(evento.id_registro_afectado, self.ticket.pk)
        self.assertEqual(evento.direccion_ip, "127.0.0.1")
        for texto in ("Abierto", "En Proceso", f"técnico #{self.tecnico.pk}", "Revisión documentada"):
            self.assertIn(texto, evento.detalle_evento)
        clave = hashlib.sha256(f"ticket:{self.ticket.pk}:actualizacion:{evento.pk}".encode()).hexdigest()
        aviso = Notificacion.objects.get(clave_evento=clave)
        self.assertEqual(aviso.id_usuario, self.solicitante)
        self.assertIn("En Proceso", aviso.titulo)
        self.assertIn(comentario.mensaje, aviso.mensaje)
        self.assertEqual(aviso.estado_envio, "PENDIENTE")
        self.assertEqual(Notificacion.objects.count(), self.base_avisos + 1)
        self.assertIsNone(self.ticket.fecha_resolucion)
        self.http.assert_not_called()

    def test_fecha_servidor_al_resolver_y_conservada_al_cerrar(self):
        self.origen("En Proceso")
        antes = timezone.now()
        self.assertEqual(self.cambiar("Resuelto").status_code, 200)
        self.ticket.refresh_from_db()
        fecha = self.ticket.fecha_resolucion
        self.assertGreaterEqual(fecha, antes)
        self.assertLessEqual(fecha, timezone.now())
        self.assertEqual(self.cambiar("Cerrado", fecha_resolucion="2000-01-01").status_code, 200)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.fecha_resolucion, fecha)

    def test_inexistencias(self):
        self.assertEqual(self.cambiar(id_estado_ticket=999999).status_code, 400)
        self.url = reverse("ticket-estado", kwargs={"pk": 999999})
        self.assertEqual(self.cambiar().status_code, 404)
        self.sin_efectos()

    def test_tecnico_ajeno_admin_solicitante_y_roles_falsos(self):
        for usuario in (self.segundo, self.admin, self.solicitante):
            with self.subTest(usuario=usuario.pk):
                self.assertEqual(self.cambiar(usuario=usuario).status_code, 403)
        self.sin_efectos()

    def test_tecnico_inactivo(self):
        self.tecnico.activo = False
        self.tecnico.save(update_fields=["activo"])
        self.assertEqual(self.cambiar().status_code, 403)
        self.sin_efectos()

    def test_tecnico_sin_permiso(self):
        RolPermiso.objects.filter(rol__nombre="Técnico de soporte", permiso__codigo="TICKET_ATENDER").delete()
        self.assertEqual(self.cambiar().status_code, 403)
        self.sin_efectos()

    def test_permiso_sin_rol_no_autoriza(self):
        UsuarioRol.objects.filter(usuario=self.tecnico).delete()
        rol = Rol.objects.get(nombre="Usuario solicitante")
        UsuarioRol.objects.create(usuario=self.tecnico, rol=rol)
        RolPermiso.objects.get_or_create(rol=rol, permiso=Permiso.objects.get(codigo="TICKET_ATENDER"))
        self.assertEqual(self.cambiar().status_code, 403)
        self.sin_efectos()

    def test_mensaje_vacio_o_ausente(self):
        for datos in ({"id_estado_ticket": self.estados["En Proceso"].pk},
                      {"id_estado_ticket": self.estados["En Proceso"].pk, "mensaje": " \t\n"}):
            self.assertEqual(self.cliente(self.tecnico).patch(self.url, datos, format="json").status_code, 400)
        self.sin_efectos()

    def test_rollback_completo_ante_auditoria_o_notificacion(self):
        self.origen("En Proceso")
        for destino in ("tickets.services.registrar_auditoria", "tickets.services.notificar_actualizacion_ticket"):
            with self.subTest(destino=destino), patch(destino, side_effect=DatabaseError("Fallo simulado")):
                with self.assertRaises(DatabaseError):
                    self.cambiar("Resuelto")
                self.ticket.refresh_from_db()
                self.assertEqual(self.ticket.id_estado_ticket.nombre, "En Proceso")
                self.assertIsNone(self.ticket.fecha_resolucion)
                self.sin_efectos()

    def test_servicio_directo_tambien_valida(self):
        with self.assertRaises(PermissionDenied):
            cambiar_estado_ticket(id_ticket=self.ticket.pk, tecnico=self.admin,
                                  id_estado_ticket=self.estados["En Proceso"].pk, mensaje="Intento")
        with self.assertRaises(ValidationError):
            cambiar_estado_ticket(id_ticket=self.ticket.pk, tecnico=self.tecnico,
                                  id_estado_ticket=self.estados["En Proceso"].pk, mensaje=" ")
        self.sin_efectos()

    def test_bearer_y_token_invalido(self):
        from rest_framework.exceptions import AuthenticationFailed
        cliente = self.cliente()
        datos = {"id_estado_ticket": self.estados["En Proceso"].pk, "mensaje": "Desde escritorio"}
        with (patch("usuarios.authentication.validar_access_token", return_value={"sub": "prueba"}),
              patch("usuarios.authentication.resolver_usuario_access_token", return_value=self.tecnico)):
            self.assertEqual(cliente.patch(self.url, datos, format="json", HTTP_AUTHORIZATION="Bearer prueba").status_code, 200)
        with patch("usuarios.authentication.validar_access_token", side_effect=AuthenticationFailed("Token inválido")):
            self.assertEqual(cliente.patch(self.url, datos, format="json", HTTP_AUTHORIZATION="Bearer invalido").status_code, 401)
        self.assertEqual(ComentarioTicket.objects.count(), 1)

    def test_anonimo_y_csrf(self):
        datos = {"id_estado_ticket": self.estados["En Proceso"].pk, "mensaje": "Desde web"}
        self.assertEqual(self.cliente().patch(self.url, datos, format="json").status_code, 403)
        cliente = self.cliente(self.tecnico, csrf=True)
        self.assertEqual(cliente.patch(self.url, datos, format="json").status_code, 403)
        self.sin_efectos()
        UsuarioRol.objects.create(usuario=self.tecnico, rol=Rol.objects.get(nombre="Usuario solicitante"))
        cliente.get("/")
        response = cliente.patch(self.url, datos, format="json", HTTP_X_CSRFTOKEN=cliente.cookies["csrftoken"].value)
        self.assertEqual(response.status_code, 200, response.data)

    def test_resuelto_y_cerrado_no_admiten_atenciones_ni_reasignaciones(self):
        for estado in ("Resuelto", "Cerrado"):
            self.origen(estado)
            r = self.cliente(self.tecnico).post(f"/api/tickets/{self.ticket.pk}/atenciones/", {"mensaje": "Intento"}, format="json")
            self.assertEqual(r.status_code, 400)
            r = self.cliente(self.admin).post(f"/api/tickets/{self.ticket.pk}/asignar/", {
                "id_tecnico_asignado": self.segundo.pk, "motivo": "Intento"}, format="json")
            self.assertEqual(r.status_code, 400)
        self.sin_efectos()
