from datetime import timedelta

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from ordenes_trabajo.models import EstadoOrdenTrabajo, OrdenTrabajo
from reportes.services import obtener_metricas_reportes
from tickets.models import EstadoTicket, PrioridadTicket, Ticket
from usuarios.models import BitacoraAuditoria
from usuarios.tests.test_integracion_postgresql import PostgreSQLTestBase


class MetricasPostgreSQLTests(PostgreSQLTestBase):
    def test_carga_miles_de_tickets_y_pausas_sin_consultas_por_fila(self):
        fin = timezone.localtime()
        prioridad = PrioridadTicket.objects.get(nombre="Medio")
        estado = EstadoTicket.objects.get(nombre="Resuelto")
        Ticket.objects.bulk_create([
            Ticket(codigo_ticket=f"METRICA-{n}", id_usuario_solicitante=self.solicitante,
                   id_prioridad=prioridad, id_estado_ticket=estado, asunto="Prueba de métricas",
                   descripcion="Datos de prueba", fecha_creacion=fin-timedelta(hours=2), fecha_resolucion=fin)
            for n in range(5000)
        ])
        ticket = Ticket.objects.get(codigo_ticket="METRICA-0")
        orden = OrdenTrabajo.objects.create(codigo_ot="OT-METRICA", id_ticket=ticket,
                    id_tecnico_responsable=self.tecnico, id_estado_ot=EstadoOrdenTrabajo.objects.get(nombre="Completada"),
                    falla_reportada="Falla", fecha_inicio=fin-timedelta(hours=2), fecha_termino=fin)
        for accion, fecha in (("OT_PAUSADA", fin-timedelta(hours=1)), ("OT_REANUDADA", fin-timedelta(minutes=30))):
            BitacoraAuditoria.objects.create(id_usuario=self.tecnico, modulo="ORDENES_TRABAJO",
                entidad_afectada="orden_trabajo", id_registro_afectado=orden.pk, accion=accion,
                detalle_evento="Movimiento de prueba", fecha_evento=fecha)
        with CaptureQueriesContext(connection) as consultas:
            resultado = obtener_metricas_reportes(fin.date(), fin.date())
        self.assertLessEqual(len(consultas), 3)
        self.assertEqual(resultado["total_tickets_resueltos"], 5000)
        self.assertEqual(resultado["tickets_evaluados_sla"], 5000)
        self.assertEqual(resultado["tiempo_promedio_resolucion_horas"], 2.0)
        Ticket.objects.exclude(pk=ticket.pk).delete()
        resultado = obtener_metricas_reportes(fin.date(), fin.date())
        self.assertEqual(resultado["tiempo_promedio_resolucion_horas"], 1.5)
