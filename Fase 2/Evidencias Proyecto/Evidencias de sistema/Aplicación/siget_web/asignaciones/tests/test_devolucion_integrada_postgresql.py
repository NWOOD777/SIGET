"""Pruebas de integración del registro de devoluciones mediante la API REST.

Usa fixtures propias y una base test_ protegida por PostgreSQLTestRunner,
sin IDs de usuarios preexistentes.
"""
from unittest.mock import patch

from django.db import DatabaseError, connection
from django.utils import timezone

from asignaciones.models import Asignacion, DevolucionActivo, HistorialEstadoActivo
from tickets.models import Ticket
from usuarios.models import BitacoraAuditoria
from usuarios.tests.test_integracion_postgresql import PostgreSQLTestBase


class DevolucionIntegradaPostgreSQLTests(PostgreSQLTestBase):
    def devolver(self, aid, datos=None, usuario=None):
        return self.cliente(usuario or self.tecnico).post(
            f"/api/asignaciones/{aid}/devolucion/",
            {"condicion_fisica": "Buen estado"} if datos is None else datos,
            format="json",
        )

    def test_registra_devolucion_y_finaliza_asignacion(self):
        activo, aid = self.entregar()
        respuesta = self.devolver(aid)
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        asignacion = Asignacion.objects.get(pk=aid)
        devolucion = DevolucionActivo.objects.get(id_asignacion=asignacion)
        self.assertEqual(asignacion.id_estado_asignacion.nombre, "Finalizada")
        self.assertIsNotNone(asignacion.fecha_finalizacion)
        self.assertEqual(devolucion.id_tecnico_receptor, self.tecnico)
        self.assertEqual(devolucion.id_asignacion.id_solicitud.id_usuario, self.solicitante)
        activo.refresh_from_db()
        self.assertEqual(activo.id_estado_activo.nombre, "Disponible")

    def test_registra_historial_y_auditoria(self):
        activo, aid = self.entregar()
        respuesta = self.devolver(aid, {"condicion_fisica": "Con daño físico", "observaciones": "Pantalla quebrada"})
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        devolucion = DevolucionActivo.objects.get(id_asignacion_id=aid)
        historial = HistorialEstadoActivo.objects.get(id_activo=activo)
        self.assertEqual(historial.id_usuario, self.tecnico)
        self.assertEqual(historial.id_estado_activo.nombre, "En revisión")
        self.assertEqual(historial.fecha_cambio, devolucion.fecha_devolucion)
        self.assertIn("Evaluación inicial", historial.observacion or "")
        auditoria = BitacoraAuditoria.objects.get(accion="DEVOLUCION_REGISTRADA")
        self.assertEqual(auditoria.id_usuario, self.tecnico)
        self.assertEqual(auditoria.entidad_afectada, "devolucion_activo")
        self.assertEqual(auditoria.id_registro_afectado, devolucion.pk)
        self.assertIn(Ticket.objects.get().codigo_ticket, auditoria.detalle_evento)

    def test_rechaza_asignacion_inexistente(self):
        self.assertEqual(self.devolver(99999).status_code, 404)
        self.assertFalse(DevolucionActivo.objects.exists())
        self.assertFalse(HistorialEstadoActivo.objects.exists())

    def test_rechaza_asignacion_ya_finalizada(self):
        _, aid = self.entregar()
        self.assertEqual(self.devolver(aid).status_code, 201)
        self.assertEqual(self.devolver(aid).status_code, 400)
        self.assertEqual(DevolucionActivo.objects.count(), 1)
        self.assertEqual(HistorialEstadoActivo.objects.count(), 1)

    def test_rechaza_devolucion_duplicada(self):
        _, aid = self.entregar()
        self.assertEqual(self.devolver(aid).status_code, 201)
        # Incluso si un estado incoherente vuelve a abrir la asignación.
        asignacion = Asignacion.objects.get(pk=aid)
        from asignaciones.models import EstadoAsignacion
        asignacion.id_estado_asignacion = EstadoAsignacion.objects.get(nombre="Activa")
        asignacion.fecha_finalizacion = None
        asignacion.save()
        self.assertEqual(self.devolver(aid).status_code, 400)
        self.assertEqual(DevolucionActivo.objects.count(), 1)
        self.assertEqual(HistorialEstadoActivo.objects.count(), 1)

    def test_rechaza_condicion_fisica_invalida(self):
        _, aid = self.entregar()
        self.assertEqual(self.devolver(aid, {"condicion_fisica": "Desconocida"}).status_code, 400)
        self.assertFalse(DevolucionActivo.objects.exists())

    def test_rechaza_condicion_fisica_omitida(self):
        _, aid = self.entregar()
        self.assertEqual(self.devolver(aid, {}).status_code, 400)
        self.assertFalse(DevolucionActivo.objects.exists())

    def test_rechaza_usuario_sin_permisos(self):
        _, aid = self.entregar()
        for usuario in (self.admin, self.solicitante):
            with self.subTest(usuario=usuario.correo):
                self.assertEqual(self.devolver(aid, usuario=usuario).status_code, 403)
        self.assertFalse(DevolucionActivo.objects.exists())
        self.assertFalse(HistorialEstadoActivo.objects.exists())

    def test_rechaza_usuario_sin_sesion(self):
        _, aid = self.entregar()
        r = self.cliente().post(f"/api/asignaciones/{aid}/devolucion/", {"condicion_fisica": "Buen estado"}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertFalse(DevolucionActivo.objects.exists())

    def test_rechaza_fecha_finalizacion_aunque_estado_diga_activa(self):
        _, aid = self.entregar()
        Asignacion.objects.filter(pk=aid).update(fecha_finalizacion=timezone.now())
        self.assertEqual(self.devolver(aid).status_code, 400)
        self.assertFalse(DevolucionActivo.objects.exists())

    @staticmethod
    def fallo_sql(*args, **kwargs):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 / 0")

    def comprobar_rollback(self, activo, aid, auditorias_antes):
        asignacion = Asignacion.objects.get(pk=aid)
        self.assertEqual(asignacion.id_estado_asignacion.nombre, "Activa")
        self.assertIsNone(asignacion.fecha_finalizacion)
        activo.refresh_from_db()
        self.assertEqual(activo.id_estado_activo.nombre, "Asignado")
        self.assertFalse(DevolucionActivo.objects.filter(id_asignacion_id=aid).exists())
        self.assertFalse(HistorialEstadoActivo.objects.filter(id_activo=activo).exists())
        self.assertFalse(Ticket.objects.exists())
        self.assertEqual(BitacoraAuditoria.objects.count(), auditorias_antes)

    def test_error_auditoria_revierte_toda_la_devolucion(self):
        activo, aid = self.entregar()
        auditorias_antes = BitacoraAuditoria.objects.count()
        for condicion in ("Buen estado", "Con falla técnica", "Con daño físico"):
            with self.subTest(condicion=condicion):
                # El error ocurre después del historial y, si corresponde, del ticket.
                with patch("asignaciones.services.registrar_auditoria", side_effect=self.fallo_sql):
                    with self.assertRaises(DatabaseError):
                        self.devolver(aid, {"condicion_fisica": condicion})
                self.comprobar_rollback(activo, aid, auditorias_antes)

    def test_error_historial_revierte_devolucion_y_ticket(self):
        activo, aid = self.entregar()
        auditorias_antes = BitacoraAuditoria.objects.count()
        with patch("asignaciones.services.HistorialEstadoActivo.objects.create", side_effect=self.fallo_sql):
            with self.assertRaises(DatabaseError):
                self.devolver(aid, {"condicion_fisica": "Con falla técnica"})
        self.comprobar_rollback(activo, aid, auditorias_antes)
