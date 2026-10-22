"""Consulta de solicitudes y tickets con permisos y datos persistidos."""

from django.urls import reverse
from django.utils import timezone

from asignaciones.models import SolicitudAsignacion
from asignaciones.services import crear_solicitud_asignacion, rechazar_solicitud_asignacion
from notificaciones.models import Notificacion
from tickets.models import EstadoTicket, Ticket
from tickets.services import crear_ticket
from usuarios.tests.test_integracion_postgresql import PostgreSQLTestBase


class DetallesPortalPostgreSQLTests(PostgreSQLTestBase):
    def casos(self):
        self.activo()
        solicitud = crear_solicitud_asignacion(self.solicitante, self.categoria.pk, "Trabajo remoto")
        ticket = crear_ticket(self.solicitante, "Falla de acceso", "No puedo ingresar")
        return solicitud, ticket

    def rutas(self, solicitud, ticket):
        return (
            reverse("asignaciones_web:detalle", args=[solicitud.pk]),
            reverse("tickets_web:detalle", args=[ticket.pk]),
        )

    def test_solicitud_muestra_resolucion_actual_y_escapa_motivos(self):
        solicitud, _ = self.casos()
        motivo = '<script>alert("x")</script>\nSin justificación'
        rechazar_solicitud_asignacion(solicitud, self.admin, motivo)
        cliente = self.cliente(self.solicitante)
        response = cliente.get(reverse("asignaciones_web:detalle", args=[solicitud.pk]))
        self.assertTemplateUsed(response, "asignaciones/detalle.html")
        for texto in ("Rechazada", "Trabajo remoto", "Notebook", "Fecha de resolución", "Sin justificación", "&lt;script&gt;"):
            self.assertContains(response, texto)
        self.assertNotContains(response, '<script>alert("x")</script>')
        self.assertNotContains(response, "Tu solicitud fue registrada correctamente.")
        self.assertNotContains(response, "Coordina con el área de soporte")
        self.assertIn("no-store", response["Cache-Control"])

    def test_ticket_muestra_datos_actualizados_sin_datos_inventados(self):
        _, ticket = self.casos()
        url = reverse("tickets_web:detalle", args=[ticket.pk])
        cliente = self.cliente(self.solicitante)
        abierto = cliente.get(url)
        self.assertTemplateUsed(abierto, "tickets/detalle.html")
        for texto in (ticket.codigo_ticket, ticket.asunto, ticket.descripcion, "Abierto", "Sin equipo específico", "Sin técnico asignado"):
            self.assertContains(abierto, texto)
        self.assertNotContains(abierto, "Fecha de resolución")
        ticket.id_estado_ticket = EstadoTicket.objects.get(nombre="Resuelto")
        ticket.id_tecnico_asignado = self.tecnico
        ticket.fecha_resolucion = timezone.now()
        ticket.descripcion = "<script>alert(1)</script>\nServicio recuperado"
        ticket.save(update_fields=["id_estado_ticket", "id_tecnico_asignado", "fecha_resolucion", "descripcion"])
        resuelto = cliente.get(url)
        for texto in ("Resuelto", "Fecha de resolución", "Prueba 2", "Servicio recuperado", "&lt;script&gt;"):
            self.assertContains(resuelto, texto)
        self.assertNotContains(resuelto, "<script>alert(1)</script>")
        self.assertNotContains(resuelto, "Tu ticket fue registrado correctamente.")

    def test_ticket_asociado_muestra_equipo_del_registro(self):
        activo, _ = self.entregar()
        ticket = crear_ticket(self.solicitante, "Pantalla", "No enciende", id_activo=activo.pk)
        response = self.cliente(self.solicitante).get(reverse("tickets_web:detalle", args=[ticket.pk]))
        self.assertContains(response, activo.codigo_inventario)
        self.assertNotContains(response, "Sin equipo específico")

    def test_anonimo_roles_internos_e_inactivo_no_acceden_a_detalles(self):
        solicitud, ticket = self.casos()
        for usuario in (None, self.admin, self.tecnico):
            for url in self.rutas(solicitud, ticket):
                with self.subTest(usuario=usuario, url=url):
                    self.assertEqual(self.cliente(usuario).get(url).status_code, 403)
        self.solicitante.activo = False
        self.solicitante.save(update_fields=["activo"])
        for url in self.rutas(solicitud, ticket):
            self.assertEqual(self.cliente(self.solicitante).get(url).status_code, 403)

    def test_detalles_ajenos_o_inexistentes_devuelven_404(self):
        solicitud, ticket = self.casos()
        for url in self.rutas(solicitud, ticket):
            self.assertEqual(self.cliente(self.otro).get(url).status_code, 404)
        for nombre in ("asignaciones_web:detalle", "tickets_web:detalle"):
            self.assertEqual(self.cliente(self.solicitante).get(reverse(nombre, args=[999999])).status_code, 404)

    def test_consultar_detalles_no_modifica_casos_ni_genera_avisos(self):
        solicitud, ticket = self.casos()
        previo = (SolicitudAsignacion.objects.count(), Ticket.objects.count(), Notificacion.objects.count())
        cliente = self.cliente(self.solicitante)
        for url in self.rutas(solicitud, ticket):
            for _ in range(2):
                self.assertEqual(cliente.get(url).status_code, 200)
            self.assertEqual(cliente.post(url, {}).status_code, 405)
        self.assertEqual(previo, (SolicitudAsignacion.objects.count(), Ticket.objects.count(), Notificacion.objects.count()))
        solicitud.refresh_from_db()
        ticket.refresh_from_db()
        self.assertEqual(solicitud.id_estado_solicitud.nombre, "Pendiente")
        self.assertEqual(ticket.id_estado_ticket.nombre, "Abierto")

    def test_registro_web_confirma_una_vez_y_despues_abre_detalle(self):
        self.activo()
        cliente = self.cliente(self.solicitante)
        for formulario, datos, modelo, namespace, mensaje in (
            ("asignaciones_web:solicitar", {"id_categoria": self.categoria.pk, "motivo": "Trabajo"}, SolicitudAsignacion, "asignaciones_web", "Tu solicitud fue registrada correctamente."),
            ("tickets_web:nuevo", {"asunto": "Falla", "descripcion": "No enciende"}, Ticket, "tickets_web", "Tu ticket fue registrado correctamente."),
        ):
            with self.subTest(namespace=namespace):
                response = cliente.post(reverse(formulario), datos)
                self.assertEqual(response.status_code, 302)
                caso = modelo.objects.get()
                confirmacion = reverse(namespace + ":confirmacion", args=[caso.pk])
                detalle = reverse(namespace + ":detalle", args=[caso.pk])
                self.assertEqual(response["Location"], confirmacion)
                primera = cliente.get(confirmacion)
                self.assertContains(primera, mensaje)
                self.assertContains(primera, f'href="{detalle}"')
                repetida = cliente.get(confirmacion, follow=True)
                self.assertRedirects(repetida, detalle)
                self.assertNotContains(repetida, mensaje)
                self.assertEqual(modelo.objects.count(), 1)

    def test_enlaces_anteriores_abren_detalle_y_respetan_propiedad(self):
        solicitud, ticket = self.casos()
        for namespace, caso in (("asignaciones_web", solicitud), ("tickets_web", ticket)):
            url = reverse(namespace + ":confirmacion", args=[caso.pk])
            destino = reverse(namespace + ":detalle", args=[caso.pk])
            self.assertRedirects(self.cliente(self.solicitante).get(url), destino)
            self.assertEqual(self.cliente(self.otro).get(url).status_code, 404)

    def test_inicio_enlaza_detalles_de_solicitud_y_ticket(self):
        solicitud, ticket = self.casos()
        response = self.cliente(self.solicitante).get(reverse("inicio"))
        for url in self.rutas(solicitud, ticket):
            self.assertContains(response, f'href="{url}"')
        for namespace, caso in (("asignaciones_web", solicitud), ("tickets_web", ticket)):
            self.assertNotContains(response, reverse(namespace + ":confirmacion", args=[caso.pk]))
