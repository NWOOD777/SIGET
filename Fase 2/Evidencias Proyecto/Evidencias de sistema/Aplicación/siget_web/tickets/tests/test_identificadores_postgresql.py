"""Entradas de IDs inválidos deben fallar antes de ejecutar bloqueos PostgreSQL."""

from tickets.models import Ticket
from usuarios.models import BitacoraAuditoria
from usuarios.tests.test_integracion_postgresql import PostgreSQLTestBase


class IdentificadoresTicketPostgreSQLTests(PostgreSQLTestBase):
    def test_ids_fuera_del_rango_del_esquema_responden_400_sin_escrituras(self):
        for usuario in (self.solicitante,):
            cliente = self.cliente(usuario)
            for campo in ("id_activo", "id_prioridad"):
                for identificador in (0, -1, 2147483648, 10**30):
                    with self.subTest(rol=usuario.pk, campo=campo, id=identificador):
                        respuesta = cliente.post(
                            "/api/tickets/",
                            {
                                "asunto": "Identificador inválido",
                                "descripcion": "La entrada debe rechazarse sin escribir datos.",
                                campo: identificador,
                            },
                            format="json",
                        )
                        self.assertEqual(respuesta.status_code, 400, respuesta.data)
                        self.assertIn(campo, respuesta.data)
        self.assertFalse(Ticket.objects.exists())
        self.assertFalse(BitacoraAuditoria.objects.exists())
