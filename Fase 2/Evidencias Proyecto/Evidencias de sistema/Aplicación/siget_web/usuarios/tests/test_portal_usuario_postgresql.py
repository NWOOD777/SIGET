"""Portal real: propiedad de registros, indicadores y datos institucionales."""
from typing import Any
from unittest.mock import patch

from django.urls import reverse
from rest_framework.test import APIClient

from asignaciones.models import Asignacion
from asignaciones.services import registrar_devolucion_asignacion
from tickets.models import Ticket
from tickets.services import crear_ticket
from usuarios.tests.test_integracion_postgresql import PostgreSQLTestBase


class PortalUsuarioPostgreSQLTests(PostgreSQLTestBase):
    def test_invitado_admin_tecnico_e_inactivo_no_acceden_a_paginas_personales(self):
        for route in ("usuarios:mis_equipos", "usuarios:perfil"):
            for usuario in (None, self.admin, self.tecnico):
                self.assertEqual(self.cliente(usuario).get(reverse(route)).status_code, 403)
        self.solicitante.activo = False
        self.solicitante.save(update_fields=["activo"])
        self.assertEqual(self.cliente(self.solicitante).get(reverse("usuarios:perfil")).status_code, 403)

    def test_perfil_actual_escapa_texto_y_no_expone_identidad_externa(self):
        self.solicitante.nombres = "<script>alert(1)</script>"
        self.solicitante.save(update_fields=["nombres"])
        response = self.cliente(self.solicitante).get(reverse("usuarios:perfil"))
        self.assertContains(response, self.solicitante.correo)
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>alert")
        self.assertNotContains(response, self.solicitante.identificador_externo)
        self.assertEqual(self.cliente(self.solicitante).post(reverse("usuarios:perfil"), {"correo": "otro@example.invalid"}).status_code, 405)

    def test_inicio_vacio_muestra_ceros_y_mensajes(self):
        response = self.cliente(self.solicitante).get(reverse("inicio"))
        self.assertEqual(response.status_code, 200)
        for key in ("cantidad_equipos", "cantidad_solicitudes", "cantidad_tickets"):
            self.assertEqual(response.context[key], 0)
        self.assertContains(response, "No tienes equipos asignados.")
        self.assertNotContains(response, "Sin información disponible por ahora")

    def test_equipo_detalle_historial_e_indicadores_solo_del_dueno(self):
        activo, aid = self.entregar()
        crear_ticket(self.solicitante, "Problema propio", "Detalle", id_activo=activo.pk)
        crear_ticket(self.otro, "Incidente ajeno", "Privado")
        cliente = self.cliente(self.solicitante)
        response = cliente.get(reverse("inicio"))
        self.assertEqual(response.context["cantidad_equipos"], 1)
        self.assertEqual(response.context["cantidad_tickets"], 1)
        self.assertEqual(response.context["cantidad_solicitudes"], 0)
        self.assertNotContains(response, "Incidente ajeno")
        self.assertContains(cliente.get(reverse("usuarios:mis_equipos")), activo.codigo_inventario)
        url = reverse("usuarios:detalle_equipo", args=[aid])
        self.assertContains(cliente.get(url), activo.numero_serie)
        self.assertEqual(self.cliente(self.otro).get(url).status_code, 404)
        registrar_devolucion_asignacion(Asignacion.objects.get(pk=aid), self.tecnico, "Buen estado")
        self.assertNotContains(cliente.get(reverse("usuarios:mis_equipos")), activo.codigo_inventario)
        self.assertContains(cliente.get(reverse("usuarios:mis_equipos") + "?historial=1"), activo.codigo_inventario)
        self.assertEqual(cliente.get(reverse("inicio")).context["cantidad_equipos"], 0)

    def test_bearer_no_crea_ticket_incluso_con_rol_solicitante(self):
        cliente: Any = APIClient()
        cliente.credentials(HTTP_AUTHORIZATION="Bearer token-de-prueba")
        with patch("usuarios.authentication.validar_access_token", return_value={"sub": self.solicitante.identificador_externo}):
            response = cliente.post("/api/tickets/", {"asunto": "No permitido", "descripcion": "Escritorio"}, format="json")
        self.assertEqual(response.status_code, 403, response.data)
        self.assertFalse(Ticket.objects.exists())

    def test_roles_internos_consultan_pero_no_crean_y_solicitante_no_ve_ajenos(self):
        ticket = crear_ticket(self.solicitante, "Falla", "Descripción")
        for usuario in (self.admin, self.tecnico):
            cliente = self.cliente(usuario)
            self.assertEqual(cliente.get(f"/api/tickets/{ticket.pk}/").status_code, 200)
            self.assertEqual(cliente.post("/api/tickets/", {"asunto": "Manual", "descripcion": "No permitido"}, format="json").status_code, 403)
        self.assertEqual(self.cliente(self.otro).get(f"/api/tickets/{ticket.pk}/").status_code, 403)

    def test_contadores_actualizan_estados_de_solicitud_y_ticket(self):
        from asignaciones.services import aprobar_solicitud_asignacion, crear_solicitud_asignacion
        from tickets.models import EstadoTicket
        self.activo()
        solicitud = crear_solicitud_asignacion(self.solicitante, self.categoria.pk, "Trabajo")
        cliente = self.cliente(self.solicitante)
        self.assertEqual(cliente.get(reverse("inicio")).context["cantidad_solicitudes"], 1)
        aprobar_solicitud_asignacion(solicitud, self.admin)
        self.assertEqual(cliente.get(reverse("inicio")).context["cantidad_solicitudes"], 1)
        ticket = crear_ticket(self.solicitante, "Prueba de estado", "Descripción")
        self.assertEqual(cliente.get(reverse("inicio")).context["cantidad_tickets"], 1)
        ticket.id_estado_ticket = EstadoTicket.objects.get(nombre="Resuelto")
        ticket.save(update_fields=["id_estado_ticket"])
        self.assertEqual(cliente.get(reverse("inicio")).context["cantidad_tickets"], 0)
