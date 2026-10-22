"""Filtro de disponibles: integración PostgreSQL sin alterar el alcance RBAC."""
from django.db import connection

from notificaciones.models import Notificacion
from tickets.models import EstadoTicket
from tickets.services import crear_ticket
from usuarios.models import BitacoraAuditoria
from usuarios.tests.test_integracion_postgresql import PostgreSQLTestBase
from django.test import override_settings


@override_settings(SIGET_PUBLIC_URL="", RESEND_FROM_EMAIL="SIGET <avisos@example.invalid>")
class FiltroSinAsignarTests(PostgreSQLTestBase):
    def setUp(self):
        super().setUp()
        self.assertEqual(connection.settings_dict["NAME"], "test_siget_db")
        self.libre = crear_ticket(self.solicitante, "Libre", "Incidente")
        self.asignado = crear_ticket(self.solicitante, "Asignado", "Incidente")
        self.asignado.id_tecnico_asignado = self.tecnico
        self.asignado.save(update_fields=["id_tecnico_asignado"])
        self.ajeno = crear_ticket(self.otro, "Ajeno", "Incidente")
        self.en_proceso = crear_ticket(self.solicitante, "En proceso", "Incidente")
        self.en_proceso.id_estado_ticket = EstadoTicket.objects.get(nombre="En Proceso")
        self.en_proceso.save(update_fields=["id_estado_ticket"])
        self.resuelto = crear_ticket(self.solicitante, "Resuelto", "Incidente")
        self.resuelto.id_estado_ticket = EstadoTicket.objects.get(nombre="Resuelto")
        self.resuelto.save(update_fields=["id_estado_ticket"])

    def consultar(self, usuario, parametros=None):
        response = self.cliente(usuario).get("/api/tickets/", parametros or {})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsInstance(response.data, list)
        return response.data

    def ids(self, usuario, parametros=None):
        return [ticket["id_ticket"] for ticket in self.consultar(usuario, parametros)]

    def test_true_solo_abiertos_sin_tecnico(self):
        datos = self.consultar(self.tecnico, {"sin_asignar": "true"})
        self.assertEqual({t["id_ticket"] for t in datos}, {self.libre.pk, self.ajeno.pk})
        for ticket in datos:
            self.assertIsNone(ticket["id_tecnico_asignado"])
            self.assertEqual(ticket["estado"]["nombre"], "Abierto")

    def test_combinacion_con_estado_nombre_o_id(self):
        for estado in ("Abierto", str(self.libre.id_estado_ticket_id)):
            with self.subTest(estado=estado):
                self.assertEqual(set(self.ids(self.admin, {"estado": estado, "sin_asignar": "true"})),
                                 {self.libre.pk, self.ajeno.pk})

    def test_visibilidad_solicitante_no_se_amplia_ni_con_usuario_ajeno(self):
        for usuario in (self.solicitante, self.otro):
            esperado = self.libre if usuario == self.solicitante else self.ajeno
            self.assertEqual(self.ids(usuario, {"sin_asignar": "true", "usuario": str(self.otro.pk)}), [esperado.pk])

    def test_sin_parametro_y_false_conservan_listado_y_orden(self):
        for usuario in (self.admin, self.tecnico, self.solicitante):
            with self.subTest(usuario=usuario.pk):
                normal = self.consultar(usuario)
                self.assertEqual(normal, self.consultar(usuario, {"sin_asignar": "false"}))
                esperado = 4 if usuario == self.solicitante else 5
                self.assertEqual(len(normal), esperado)
                fechas = [t["fecha_creacion"] for t in normal]
                self.assertEqual(fechas, sorted(fechas, reverse=True))
                self.assertIn(self.asignado.pk, [t["id_ticket"] for t in normal])
        abiertos = self.consultar(self.tecnico, {"estado": "Abierto"})
        self.assertEqual(abiertos, self.consultar(self.tecnico, {"estado": "Abierto", "sin_asignar": "false"}))
        self.assertEqual(len(abiertos), 3)

    def test_parametros_invalidos_sin_efectos(self):
        auditorias = BitacoraAuditoria.objects.count()
        for valor in ("", "1", "0", "yes", "TRUE", "False", "null", " true "):
            with self.subTest(valor=valor):
                response = self.cliente(self.tecnico).get("/api/tickets/", {"sin_asignar": valor})
                self.assertEqual(response.status_code, 400)
                self.assertEqual([str(e) for e in response.data["sin_asignar"]], ["Utilice true o false."])
        self.assertEqual(BitacoraAuditoria.objects.count(), auditorias)
        self.assertFalse(Notificacion.objects.exists())

    def test_interseccion_con_estado_incompatible_y_busqueda(self):
        self.assertEqual(self.ids(self.tecnico, {"estado": "Resuelto", "sin_asignar": "true"}), [])
        self.assertEqual(self.ids(self.tecnico, {"search": "Libre", "sin_asignar": "true"}), [self.libre.pk])
        self.assertEqual(self.ids(self.tecnico, {"search": "Asignado", "sin_asignar": "true"}), [])

    def test_sin_asignar_no_omite_autenticacion(self):
        response = self.cliente().get("/api/tickets/", {"sin_asignar": "true"})
        self.assertEqual(response.status_code, 403)

    def test_tomar_elimina_ticket_del_filtro_sin_cambiar_consulta_general(self):
        self.assertIn(self.libre.pk, self.ids(self.tecnico, {"sin_asignar": "true"}))
        response = self.cliente(self.tecnico).post(f"/api/tickets/{self.libre.pk}/tomar/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertNotIn(self.libre.pk, self.ids(self.tecnico, {"sin_asignar": "true"}))
        self.assertIn(self.libre.pk, self.ids(self.tecnico))
        self.assertEqual(self.ids(self.tecnico, {"sin_asignar": "true"}), [self.ajeno.pk])
