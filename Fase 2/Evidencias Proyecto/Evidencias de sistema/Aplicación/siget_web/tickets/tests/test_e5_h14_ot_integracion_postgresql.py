"""Integración OT/tickets y concurrencia con conexiones PostgreSQL separadas."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

from django.db import connections
from rest_framework.exceptions import ValidationError

from activos.models import EstadoActivo
from notificaciones.models import Notificacion
from ordenes_trabajo.models import Diagnostico, EstadoOrdenTrabajo, OrdenTrabajo
from ordenes_trabajo.services import crear_orden_trabajo, iniciar_reparacion
from tickets.models import ComentarioTicket
from tickets.tests.test_e5_h14_estados import EstadoFixture
from usuarios.models import BitacoraAuditoria


class IntegracionOTEstadosTests(EstadoFixture):
    def setUp(self):
        super().setUp()
        self.activo_ot = self.activo()
        self.activo_ot.id_estado_activo = EstadoActivo.objects.get(nombre="En revisión")
        self.activo_ot.save(update_fields=["id_estado_activo"])
        self.ticket.id_activo = self.activo_ot
        self.ticket.save(update_fields=["id_activo"])

    def crear_ot(self):
        return crear_orden_trabajo(self.ticket.pk, self.tecnico, "Falla", "Revisión inicial")

    def test_ot_en_abierto_y_reparacion_conservan_su_comportamiento(self):
        orden = self.crear_ot()
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.id_estado_ticket.nombre, "Abierto")
        self.assertEqual(orden.id_estado_ot.nombre, "En Diagnóstico")
        self.assertEqual(Diagnostico.objects.get(id_orden=orden).procedimiento_inicial, "Revisión inicial")
        self.activo_ot.refresh_from_db()
        self.assertEqual(self.activo_ot.id_estado_activo.nombre, "En revisión")
        with self.assertRaises(ValidationError):
            self.crear_ot()
        self.assertEqual(OrdenTrabajo.objects.count(), 1)
        iniciar_reparacion(orden.pk, self.tecnico)
        orden.refresh_from_db()
        self.assertEqual(orden.id_estado_ot.nombre, "En Reparación")
        self.activo_ot.refresh_from_db()
        self.assertEqual(self.activo_ot.id_estado_activo.nombre, "En reparación")

    def test_ot_no_se_crea_en_resuelto_o_cerrado(self):
        for nombre in ("Resuelto", "Cerrado"):
            with self.subTest(estado=nombre):
                self.origen(nombre)
                with self.assertRaises(ValidationError):
                    self.crear_ot()
                self.assertFalse(OrdenTrabajo.objects.exists())
                self.assertFalse(Diagnostico.objects.exists())
                self.sin_efectos()

    def test_validaciones_previas_de_ot_siguen_vigentes(self):
        for falla, procedimiento in ((" ", "Revisión"), ("Falla", " ")):
            with self.assertRaises(ValidationError):
                crear_orden_trabajo(self.ticket.pk, self.tecnico, falla, procedimiento)
        with self.assertRaises(ValidationError):
            crear_orden_trabajo(999999, self.tecnico, "Falla", "Revisión")
        self.activo_ot.id_estado_activo = EstadoActivo.objects.get(nombre="Disponible")
        self.activo_ot.save(update_fields=["id_estado_activo"])
        with self.assertRaises(ValidationError):
            self.crear_ot()
        self.ticket.id_activo = None
        self.ticket.save(update_fields=["id_activo"])
        with self.assertRaises(ValidationError):
            self.crear_ot()
        self.assertFalse(OrdenTrabajo.objects.exists())
        self.assertFalse(Diagnostico.objects.exists())
        self.sin_efectos()

    def test_ot_vigente_impide_resolver_y_cerrar(self):
        orden = self.crear_ot()
        antes = (BitacoraAuditoria.objects.count(), Notificacion.objects.count())
        for ot in ("En Diagnóstico", "En Reparación", "Pausada"):
            orden.id_estado_ot = EstadoOrdenTrabajo.objects.get(nombre=ot)
            orden.save(update_fields=["id_estado_ot"])
            for origen, destino in (("En Proceso", "Resuelto"), ("Resuelto", "Cerrado")):
                with self.subTest(ot=ot, destino=destino):
                    self.origen(origen)
                    self.assertEqual(self.cambiar(destino).status_code, 400)
                    self.ticket.refresh_from_db()
                    self.assertEqual(self.ticket.id_estado_ticket.nombre, origen)
        self.assertFalse(ComentarioTicket.objects.exists())
        self.assertEqual((BitacoraAuditoria.objects.count(), Notificacion.objects.count()), antes)

    def test_ot_completada_permite_resolver_y_cerrar_sin_alterar_ot_activo_diagnostico(self):
        orden = self.crear_ot()
        orden.id_estado_ot = EstadoOrdenTrabajo.objects.get(nombre="Completada")
        orden.save(update_fields=["id_estado_ot"])
        antes = OrdenTrabajo.objects.values().get(pk=orden.pk)
        diagnostico = Diagnostico.objects.values().get(id_orden=orden)
        self.origen("En Proceso")
        self.assertEqual(self.cambiar("Resuelto").status_code, 200)
        self.assertEqual(self.cambiar("Cerrado").status_code, 200)
        self.assertEqual(OrdenTrabajo.objects.values().get(pk=orden.pk), antes)
        self.assertEqual(Diagnostico.objects.values().get(id_orden=orden), diagnostico)
        self.activo_ot.refresh_from_db()
        self.assertEqual(self.activo_ot.id_estado_activo.nombre, "En revisión")

    def carrera(self, primero, segundo, parche, accion, rollback=False):
        """Pausa el primer escritor y observa el FOR UPDATE del segundo."""
        tomado, intentando, continuar = Event(), Event(), Event()
        if parche.startswith("ordenes"):
            from ordenes_trabajo.services import registrar_auditoria as auditar_real
        else:
            from tickets.services import registrar_auditoria as auditar_real

        def auditar(**datos):
            if datos["accion"] == accion:
                tomado.set()
                if not continuar.wait(10):
                    raise TimeoutError("Operación no liberada")
                if rollback:
                    raise ValidationError("Rollback deliberado")
            return auditar_real(**datos)

        def ejecutar(operacion, observar=False):
            conexion = connections["default"]
            def observar_sql(execute, sql, params, many, context):
                if "FOR UPDATE" in sql and '"ticket"' in sql:
                    intentando.set()
                return execute(sql, params, many, context)
            try:
                with conexion.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '8s'")
                    cursor.execute("SET statement_timeout = '15s'")
                if observar:
                    with conexion.execute_wrapper(observar_sql):
                        return operacion()
                return operacion()
            except ValidationError:
                return 400
            finally:
                connections.close_all()

        with patch(parche, side_effect=auditar), ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(ejecutar, primero)
            try:
                self.assertTrue(tomado.wait(10))
                b = pool.submit(ejecutar, segundo, True)
                self.assertTrue(intentando.wait(10))
                self.assertFalse(b.done())
            finally:
                continuar.set()
            return a.result(timeout=20), b.result(timeout=20)

    def ot_status(self):
        self.crear_ot()
        return 201

    def test_ot_gana_y_resolucion_concurrente_rechazada(self):
        self.origen("En Proceso")
        resultados = self.carrera(self.ot_status, lambda: self.cambiar("Resuelto").status_code,
                                 "ordenes_trabajo.services.registrar_auditoria", "OT_CREADA")
        self.assertEqual(resultados, (201, 400))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.id_estado_ticket.nombre, "En Proceso")
        self.assertEqual(OrdenTrabajo.objects.count(), 1)
        self.assertFalse(ComentarioTicket.objects.exists())

    def test_resolucion_gana_y_ot_concurrente_rechazada(self):
        self.origen("En Proceso")
        resultados = self.carrera(lambda: self.cambiar("Resuelto").status_code, self.ot_status,
                                 "tickets.services.registrar_auditoria", "TICKET_ESTADO_CAMBIADO")
        self.assertEqual(resultados, (200, 400))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.id_estado_ticket.nombre, "Resuelto")
        self.assertFalse(OrdenTrabajo.objects.exists())
        self.assertFalse(Diagnostico.objects.exists())
        self.assertEqual(ComentarioTicket.objects.count(), 1)

    def test_rollback_resolucion_desbloquea_creacion_ot(self):
        self.origen("En Proceso")
        resultados = self.carrera(lambda: self.cambiar("Resuelto").status_code, self.ot_status,
                                 "tickets.services.registrar_auditoria", "TICKET_ESTADO_CAMBIADO", rollback=True)
        self.assertEqual(resultados, (400, 201))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.id_estado_ticket.nombre, "En Proceso")
        self.assertIsNone(self.ticket.fecha_resolucion)
        self.assertFalse(ComentarioTicket.objects.exists())
        self.assertFalse(BitacoraAuditoria.objects.filter(accion="TICKET_ESTADO_CAMBIADO").exists())
        self.assertEqual(Notificacion.objects.count(), self.base_avisos)
        self.assertEqual(OrdenTrabajo.objects.count(), 1)

    def test_dos_cambios_concurrentes_revalidan_estado(self):
        resultados = self.carrera(lambda: self.cambiar().status_code, lambda: self.cambiar().status_code,
                                 "tickets.services.registrar_auditoria", "TICKET_ESTADO_CAMBIADO")
        self.assertEqual(resultados, (200, 400))
        self.assertEqual(ComentarioTicket.objects.count(), 1)
        self.assertEqual(BitacoraAuditoria.objects.filter(accion="TICKET_ESTADO_CAMBIADO").count(), 1)
        self.assertEqual(Notificacion.objects.count(), self.base_avisos + 1)

    def test_resolucion_concurrente_con_atencion_rechaza_sin_falso_404(self):
        self.origen("En Proceso")
        def atender():
            return self.cliente(self.tecnico).post(f"/api/tickets/{self.ticket.pk}/atenciones/",
                {"mensaje": "Revisión"}, format="json").status_code
        resultados = self.carrera(lambda: self.cambiar("Resuelto").status_code, atender,
                                 "tickets.services.registrar_auditoria", "TICKET_ESTADO_CAMBIADO")
        self.assertEqual(resultados, (200, 400))
        self.assertEqual(ComentarioTicket.objects.count(), 1)
        self.assertFalse(BitacoraAuditoria.objects.filter(accion="TICKET_ATENDIDO").exists())

    def test_resolucion_concurrente_con_reasignacion_rechaza_sin_falso_404(self):
        self.origen("En Proceso")
        def reasignar():
            return self.cliente(self.admin).post(f"/api/tickets/{self.ticket.pk}/asignar/",
                {"id_tecnico_asignado": self.segundo.pk, "motivo": "Cambio de turno"}, format="json").status_code
        resultados = self.carrera(lambda: self.cambiar("Resuelto").status_code, reasignar,
                                 "tickets.services.registrar_auditoria", "TICKET_ESTADO_CAMBIADO")
        self.assertEqual(resultados, (200, 400))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.id_tecnico_asignado, self.tecnico)
        self.assertFalse(BitacoraAuditoria.objects.filter(accion="TICKET_REASIGNADO").exists())
