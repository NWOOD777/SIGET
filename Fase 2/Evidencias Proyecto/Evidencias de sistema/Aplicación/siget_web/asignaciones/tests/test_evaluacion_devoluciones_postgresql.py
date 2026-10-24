"""Evaluación inicial: disponibilidad, tickets, trazabilidad y concurrencia."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.db import DatabaseError, connection, connections
from django.utils import timezone

from asignaciones.models import Asignacion, DevolucionActivo, HistorialEstadoActivo, SolicitudAsignacion
from tickets.models import EstadoTicket, Ticket
from tickets.services import crear_ticket
from usuarios.models import BitacoraAuditoria, Permiso, Rol, RolPermiso
from usuarios.tests.test_integracion_postgresql import PostgreSQLTestBase


class EvaluacionInicialPostgreSQLTests(PostgreSQLTestBase):
    def evaluar(self, aid, datos=None, usuario=None):
        return self.cliente(usuario or self.tecnico).post(f'/api/asignaciones/{aid}/devolucion/',
            datos if datos is not None else {'condicion_fisica': 'Buen estado'}, format='json')

    def test_equipo_operativo_permite_una_nueva_entrega(self):
        activo, aid = self.entregar()
        self.assertEqual(self.evaluar(aid).status_code, 201)
        self.assertFalse(Ticket.objects.exists())
        r = self.cliente(self.otro).post('/api/solicitudes-asignacion/', {
            'id_categoria': self.categoria.pk, 'motivo': 'Reutilizar equipo operativo'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        sid = r.data['id_solicitud']
        self.assertEqual(self.cliente(self.admin).post(f'/api/solicitudes-asignacion/{sid}/aprobar/', {}, format='json').status_code, 200)
        r = self.cliente(self.tecnico).post(f'/api/solicitudes-asignacion/{sid}/entregar/', {'id_activo': activo.pk}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertNotEqual(r.data['id_asignacion'], aid)
        self.assertEqual(Asignacion.objects.filter(id_activo=activo).count(), 2)
        self.assertEqual(Asignacion.objects.filter(id_activo=activo, fecha_finalizacion__isnull=True).count(), 1)

    def test_falla_y_dano_impiden_nuevas_entregas_hasta_estar_disponible(self):
        for condicion in ('Con falla técnica', 'Con daño físico'):
            with self.subTest(condicion=condicion):
                activo, solicitud_inicial = self.preparar_entrega()
                r = self.cliente(self.otro).post('/api/solicitudes-asignacion/', {
                    'id_categoria': self.categoria.pk, 'motivo': 'Otra solicitud'}, format='json')
                self.assertEqual(r.status_code, 201)
                sid = r.data['id_solicitud']
                self.assertEqual(self.cliente(self.admin).post(f'/api/solicitudes-asignacion/{sid}/aprobar/', {}, format='json').status_code, 200)
                entrega = self.cliente(self.tecnico).post(
                    f'/api/solicitudes-asignacion/{solicitud_inicial}/entregar/',
                    {'id_activo': activo.pk}, format='json')
                self.assertEqual(entrega.status_code, 201, entrega.data)
                aid = entrega.data['id_asignacion']
                self.assertEqual(self.evaluar(aid, {'condicion_fisica': condicion, 'observaciones': 'No operativo'}).status_code, 201)
                activo.refresh_from_db()
                self.assertEqual(activo.id_estado_activo.nombre, 'En revisión')
                r = self.cliente(self.tecnico).post(f'/api/solicitudes-asignacion/{sid}/entregar/', {'id_activo': activo.pk}, format='json')
                self.assertEqual(r.status_code, 400)
                self.assertFalse(Asignacion.objects.filter(id_solicitud_id=sid).exists())
                SolicitudAsignacion.objects.filter(pk=sid).delete()

    def test_evaluacion_conserva_condicion_observacion_motivo_actor_y_fecha(self):
        activo, aid = self.entregar()
        antes = timezone.now()
        r = self.evaluar(aid, {'condicion_fisica': 'Con daño físico',
            'observaciones': '  Carcasa rota en la esquina inferior  ', 'motivo_devolucion': '  Daño detectado  '})
        despues = timezone.now()
        self.assertEqual(r.status_code, 201, r.data)
        d = DevolucionActivo.objects.get(id_asignacion_id=aid)
        self.assertEqual(d.condicion_fisica, 'Con daño físico')
        self.assertEqual(d.observaciones, 'Carcasa rota en la esquina inferior')
        self.assertEqual(d.motivo_devolucion, 'Daño detectado')
        self.assertEqual(d.id_tecnico_receptor, self.tecnico)
        self.assertTrue(antes <= d.fecha_devolucion <= despues)
        h = HistorialEstadoActivo.objects.get(id_activo=activo)
        self.assertEqual(h.id_estado_activo, d.id_estado_activo_resultante)
        self.assertEqual(h.id_usuario, self.tecnico)
        self.assertEqual(h.fecha_cambio, d.fecha_devolucion)
        self.assertIn('Carcasa rota', Ticket.objects.get().descripcion)
        a = BitacoraAuditoria.objects.get(accion='DEVOLUCION_REGISTRADA')
        self.assertEqual(a.id_usuario, self.tecnico)
        self.assertEqual(a.id_registro_afectado, d.pk)
        self.assertIn(Ticket.objects.get().codigo_ticket, a.detalle_evento)

    def test_estado_invalido_no_finaliza_asignacion_ni_crea_historial(self):
        activo, aid = self.entregar()
        for datos in ({}, {'condicion_fisica': None}, {'condicion_fisica': ''},
                      {'condicion_fisica': 'En reparación'}, [], {'condicion_fisica': 'Buen estado', 'motivo_devolucion': 'X' * 101}):
            with self.subTest(datos=datos):
                self.assertEqual(self.evaluar(aid, datos).status_code, 400)
        self.assertIsNone(Asignacion.objects.get(pk=aid).fecha_finalizacion)
        activo.refresh_from_db()
        self.assertEqual(activo.id_estado_activo.nombre, 'Asignado')
        self.assertFalse(DevolucionActivo.objects.exists())
        self.assertFalse(HistorialEstadoActivo.objects.exists())
        self.assertFalse(Ticket.objects.exists())

    def test_ticket_activo_indicado_se_asocia_sin_duplicarse(self):
        activo, aid = self.entregar()
        t = crear_ticket(self.solicitante, 'Falla ya reportada', 'Mismo equipo', id_activo=activo.pk)
        r = self.evaluar(aid, {'condicion_fisica': 'Con falla técnica', 'id_ticket_asociado': t.pk})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Ticket.objects.count(), 1)
        self.assertIn(t.codigo_ticket, BitacoraAuditoria.objects.get(accion='DEVOLUCION_REGISTRADA').detalle_evento)
        self.assertEqual(HistorialEstadoActivo.objects.count(), 1)

    def test_ticket_invalido_revierte_evaluacion_sin_cambiar_equipo(self):
        activo, aid = self.entregar()
        otro_activo = self.activo()
        ajeno = crear_ticket(self.otro, 'Otro usuario', 'Incidente ajeno', id_activo=activo.pk)
        otro = crear_ticket(self.solicitante, 'Otro equipo', 'Activo distinto', id_activo=otro_activo.pk)
        cerrado = crear_ticket(self.solicitante, 'Cerrado', 'Incidente terminado', id_activo=activo.pk)
        cerrado.id_estado_ticket = EstadoTicket.objects.get(nombre='Cerrado')
        cerrado.save()
        for ticket in (99999, ajeno.pk, otro.pk, cerrado.pk):
            with self.subTest(ticket=ticket):
                r = self.evaluar(aid, {'condicion_fisica': 'Con falla técnica', 'id_ticket_asociado': ticket})
                self.assertEqual(r.status_code, 400)
                self.assertIsNone(Asignacion.objects.get(pk=aid).fecha_finalizacion)
                self.assertFalse(DevolucionActivo.objects.exists())
                self.assertFalse(HistorialEstadoActivo.objects.exists())
                activo.refresh_from_db()
                self.assertEqual(activo.id_estado_activo.nombre, 'Asignado')
        self.assertEqual(Ticket.objects.count(), 3)

    def test_buen_estado_rechaza_ticket_y_no_libera_el_equipo(self):
        activo, aid = self.entregar()
        t = crear_ticket(self.solicitante, 'Reporte previo', 'Incidente', id_activo=activo.pk)
        r = self.evaluar(aid, {'condicion_fisica': 'Buen estado', 'id_ticket_asociado': t.pk})
        self.assertEqual(r.status_code, 400)
        activo.refresh_from_db()
        self.assertEqual(activo.id_estado_activo.nombre, 'Asignado')
        self.assertIsNone(Asignacion.objects.get(pk=aid).fecha_finalizacion)
        self.assertFalse(DevolucionActivo.objects.exists())
        self.assertFalse(HistorialEstadoActivo.objects.exists())

    def test_permiso_granular_no_reemplaza_el_rol_tecnico(self):
        _, aid = self.entregar()
        permiso = Permiso.objects.get(codigo='DEVOLUCION_REGISTRAR')
        for nombre in ('Administrador del sistema', 'Usuario solicitante'):
            RolPermiso.objects.get_or_create(rol=Rol.objects.get(nombre=nombre), permiso=permiso)
        for usuario in (self.admin, self.solicitante):
            self.assertEqual(self.evaluar(aid, usuario=usuario).status_code, 403)
        self.assertIsNone(Asignacion.objects.get(pk=aid).fecha_finalizacion)
        self.assertFalse(DevolucionActivo.objects.exists())

    def test_dos_evaluaciones_simultaneas_generan_un_solo_ticket_y_devolucion(self):
        activo, aid = self.entregar()
        barrera = Barrier(2, timeout=10)
        def evaluar(n):
            try:
                c = self.cliente(self.tecnico)
                barrera.wait()
                return c.post(f'/api/asignaciones/{aid}/devolucion/',
                    {'condicion_fisica': 'Con falla técnica'}, format='json').status_code
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(evaluar, (1, 2))), [201, 400])
        self.assertEqual(DevolucionActivo.objects.filter(id_asignacion_id=aid).count(), 1)
        self.assertEqual(Ticket.objects.filter(id_activo=activo).count(), 1)
        self.assertEqual(HistorialEstadoActivo.objects.filter(id_activo=activo).count(), 1)
        self.assertEqual(BitacoraAuditoria.objects.filter(accion='DEVOLUCION_REGISTRADA').count(), 1)
        self.assertEqual(BitacoraAuditoria.objects.filter(accion='TICKET_CREADO').count(), 1)

    def test_error_sql_al_crear_ticket_revierte_cierre_y_estado(self):
        activo, aid = self.entregar()
        auditorias = BitacoraAuditoria.objects.count()
        def fallo(*args, **kwargs):
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1 / 0')
        with patch('tickets.services.Ticket.objects.create', side_effect=fallo):
            with self.assertRaises(DatabaseError):
                self.evaluar(aid, {'condicion_fisica': 'Con falla técnica'})
        activo.refresh_from_db()
        self.assertEqual(activo.id_estado_activo.nombre, 'Asignado')
        self.assertIsNone(Asignacion.objects.get(pk=aid).fecha_finalizacion)
        self.assertFalse(DevolucionActivo.objects.exists())
        self.assertFalse(HistorialEstadoActivo.objects.exists())
        self.assertFalse(Ticket.objects.exists())
        self.assertEqual(BitacoraAuditoria.objects.count(), auditorias)
