"""Criterios de E3-H8 sobre la API y PostgreSQL, con sesiones de los roles reales."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.db import DatabaseError, connection, connections
from django.utils import timezone

from asignaciones.models import Asignacion, EstadoSolicitudAsignacion, SolicitudAsignacion
from usuarios.models import BitacoraAuditoria, Permiso, Rol, RolPermiso
from usuarios.tests.test_integracion_postgresql import PostgreSQLTestBase


class GestionSolicitudPostgreSQLTests(PostgreSQLTestBase):
    def pendiente(self):
        self.activo()
        r = self.cliente(self.solicitante).post('/api/solicitudes-asignacion/', {
            'id_categoria': self.categoria.pk, 'motivo': 'Trabajo de campo',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        return SolicitudAsignacion.objects.get(pk=r.data['id_solicitud'])

    def resolver(self, solicitud, accion, usuario=None, datos=None):
        if datos is None:
            datos = {'motivo_rechazo': 'Sin justificación de uso'} if accion == 'rechazar' else {}
        return self.cliente(usuario or self.admin).post(
            f'/api/solicitudes-asignacion/{solicitud.pk}/{accion}/', datos, format='json')

    def test_consulta_pendientes_por_estado_y_categoria(self):
        s = self.pendiente()
        SolicitudAsignacion.objects.create(id_usuario=self.otro, id_categoria=self.categoria,
            id_estado_solicitud=EstadoSolicitudAsignacion.objects.get(nombre='Rechazada'), motivo='Resuelta')
        c = self.cliente(self.admin)
        for estado in ('Pendiente', getattr(s, "id_estado_solicitud_id")):
            r = c.get('/api/solicitudes-asignacion/', {'estado': estado, 'categoria': self.categoria.pk})
            self.assertEqual(r.status_code, 200)
            self.assertEqual([v['id_solicitud'] for v in r.data], [s.pk])
        self.assertEqual(self.cliente().get('/api/solicitudes-asignacion/', {'estado': 'Pendiente'}).status_code, 403)

    def test_aprobar_registra_resolutor_fecha_auditoria_y_no_reserva_activo(self):
        s = self.pendiente()
        # La aprobación no acepta una selección física, aunque el cliente la envíe.
        r = self.resolver(s, 'aprobar', datos={'id_activo': 99999})
        self.assertEqual(r.status_code, 200, r.data)
        s.refresh_from_db()
        self.assertEqual(s.id_estado_solicitud.nombre, 'Aprobada')
        self.assertEqual(s.id_administrador_resolutor, self.admin)
        self.assertIsNotNone(s.fecha_resolucion)
        self.assertGreaterEqual(s.fecha_resolucion, s.fecha_solicitud)
        self.assertFalse(Asignacion.objects.exists())
        from activos.models import Activo
        self.assertEqual(Activo.objects.get().id_estado_activo.nombre, 'Disponible')
        a = BitacoraAuditoria.objects.get(accion='SOLICITUD_APROBADA')
        self.assertEqual(a.id_usuario, self.admin)
        self.assertEqual(a.id_registro_afectado, s.pk)
        self.assertEqual(a.entidad_afectada, 'solicitud_asignacion')

    def test_rechazar_registra_motivo_resolutor_fecha_y_auditoria(self):
        s = self.pendiente()
        r = self.resolver(s, 'rechazar', datos={'motivo_rechazo': '  Sin presupuesto  '})
        self.assertEqual(r.status_code, 200, r.data)
        s.refresh_from_db()
        self.assertEqual(s.id_estado_solicitud.nombre, 'Rechazada')
        self.assertEqual(s.motivo_rechazo, 'Sin presupuesto')
        self.assertEqual(s.id_administrador_resolutor, self.admin)
        self.assertGreaterEqual(s.fecha_resolucion, s.fecha_solicitud)
        a = BitacoraAuditoria.objects.get(accion='SOLICITUD_RECHAZADA')
        self.assertEqual(a.id_usuario, self.admin)
        self.assertEqual(a.id_registro_afectado, s.pk)
        self.assertIn('Sin presupuesto', a.detalle_evento)
        self.assertFalse(Asignacion.objects.exists())

    def test_aprobacion_revalida_stock_perdido_desde_la_solicitud(self):
        s = self.pendiente()
        from activos.models import Activo, EstadoActivo
        Activo.objects.update(id_estado_activo=EstadoActivo.objects.get(nombre='En revisión'))
        self.assertEqual(self.resolver(s, 'aprobar').status_code, 400)
        s.refresh_from_db()
        self.assertEqual(s.id_estado_solicitud.nombre, 'Pendiente')
        self.assertIsNone(s.fecha_resolucion)
        self.assertIsNone(s.id_administrador_resolutor)
        self.assertFalse(BitacoraAuditoria.objects.filter(accion='SOLICITUD_APROBADA').exists())
        self.assertFalse(Asignacion.objects.exists())

    def test_solicitud_inexistente_en_consulta_aprobacion_y_rechazo(self):
        s = SolicitudAsignacion(id_solicitud=99999)
        self.assertEqual(self.cliente(self.admin).get('/api/solicitudes-asignacion/99999/').status_code, 404)
        for accion in ('aprobar', 'rechazar'):
            self.assertEqual(self.resolver(s, accion).status_code, 404)
        self.assertFalse(BitacoraAuditoria.objects.exists())

    def test_rechazo_sin_motivo_no_modifica_solicitud(self):
        s = self.pendiente()
        for datos in ({}, {'motivo_rechazo': ''}, {'motivo_rechazo': '   '}, [], {'motivo_rechazo': None}):
            with self.subTest(datos=datos):
                self.assertEqual(self.resolver(s, 'rechazar', datos=datos).status_code, 400)
        s.refresh_from_db()
        self.assertEqual(s.id_estado_solicitud.nombre, 'Pendiente')
        self.assertIsNone(s.fecha_resolucion)
        self.assertFalse(BitacoraAuditoria.objects.filter(accion='SOLICITUD_RECHAZADA').exists())

    def test_decisiones_no_sobrescriben_solicitudes_ya_gestionadas(self):
        for estado in ('Aprobada', 'Rechazada', 'Atendida'):
            fecha = timezone.now()
            s = SolicitudAsignacion.objects.create(id_usuario=self.solicitante, id_categoria=self.categoria,
                id_estado_solicitud=EstadoSolicitudAsignacion.objects.get(nombre=estado),
                id_administrador_resolutor=self.admin, fecha_resolucion=fecha,
                fecha_solicitud=fecha, motivo='Ya gestionada', motivo_rechazo='Decisión previa')
            for accion in ('aprobar', 'rechazar'):
                self.assertEqual(self.resolver(s, accion).status_code, 400)
            s.refresh_from_db()
            self.assertEqual(s.id_estado_solicitud.nombre, estado)
            self.assertEqual(s.motivo_rechazo, 'Decisión previa')
        self.assertFalse(BitacoraAuditoria.objects.exists())

    def test_solo_administrador_resuelve_aunque_otros_roles_reciban_permiso(self):
        s = self.pendiente()
        permiso = Permiso.objects.get(codigo='SOLICITUD_RESOLVER')
        for nombre in ('Técnico de soporte', 'Usuario solicitante'):
            RolPermiso.objects.get_or_create(rol=Rol.objects.get(nombre=nombre), permiso=permiso)
        for usuario in (self.tecnico, self.solicitante):
            for accion in ('aprobar', 'rechazar'):
                self.assertEqual(self.resolver(s, accion, usuario=usuario).status_code, 403)
        for accion in ('aprobar', 'rechazar'):
            self.assertEqual(self.cliente().post(f'/api/solicitudes-asignacion/{s.pk}/{accion}/',
                {'motivo_rechazo': 'Sin sesión'}, format='json').status_code, 403)
        s.refresh_from_db()
        self.assertEqual(s.id_estado_solicitud.nombre, 'Pendiente')
        self.assertIsNone(s.fecha_resolucion)

    def competir(self, funcion):
        barrera = Barrier(2, timeout=10)
        def ejecutar(n):
            try:
                c = self.cliente(self.admin)
                barrera.wait()
                return funcion(c, n)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(ejecutar, (1, 2)))

    def test_aprobacion_y_rechazo_simultaneos_solo_registran_una_decision(self):
        s = self.pendiente()
        def decidir(c, n):
            accion = 'aprobar' if n == 1 else 'rechazar'
            return c.post(f'/api/solicitudes-asignacion/{s.pk}/{accion}/',
                {'motivo_rechazo': 'Decisión concurrente'}, format='json').status_code
        self.assertCountEqual(self.competir(decidir), [200, 400])
        self.assertEqual(BitacoraAuditoria.objects.filter(accion__in=['SOLICITUD_APROBADA', 'SOLICITUD_RECHAZADA']).count(), 1)
        self.assertFalse(Asignacion.objects.exists())
        s.refresh_from_db()
        self.assertIn(s.id_estado_solicitud.nombre, ['Aprobada', 'Rechazada'])
        self.assertEqual(s.id_administrador_resolutor, self.admin)

    def test_dos_aprobaciones_simultaneas_no_duplican_auditoria(self):
        s = self.pendiente()
        self.assertCountEqual(self.competir(lambda c, n: c.post(
            f'/api/solicitudes-asignacion/{s.pk}/aprobar/', {}, format='json').status_code), [200, 400])
        self.assertEqual(BitacoraAuditoria.objects.filter(accion='SOLICITUD_APROBADA').count(), 1)

    def test_error_sql_en_auditoria_revierte_aprobacion_y_rechazo(self):
        s = self.pendiente()
        def fallo(*args, **kwargs):
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1 / 0')
        for accion in ('aprobar', 'rechazar'):
            with self.subTest(accion=accion):
                with patch('asignaciones.services.registrar_auditoria', side_effect=fallo):
                    with self.assertRaises(DatabaseError):
                        self.resolver(s, accion)
                s.refresh_from_db()
                self.assertEqual(s.id_estado_solicitud.nombre, 'Pendiente')
                self.assertIsNone(s.fecha_resolucion)
                self.assertIsNone(s.id_administrador_resolutor)
                self.assertIsNone(s.motivo_rechazo)
                self.assertFalse(BitacoraAuditoria.objects.filter(accion__in=['SOLICITUD_APROBADA', 'SOLICITUD_RECHAZADA']).exists())
