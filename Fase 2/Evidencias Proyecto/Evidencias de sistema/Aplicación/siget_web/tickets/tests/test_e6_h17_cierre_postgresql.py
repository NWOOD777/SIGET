"""Integración del cierre interno, exclusivamente sobre test_siget_db."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Event
from unittest.mock import patch

from django.db import connections, IntegrityError, transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from asignaciones.models import HistorialEstadoActivo
from notificaciones.models import Notificacion
from ordenes_trabajo.cierre import cerrar_orden_trabajo
from ordenes_trabajo.models import CierreTecnico, Diagnostico, OrdenTrabajo
from ordenes_trabajo.repuestos import asignar_repuesto_orden, anular_asignacion_repuesto
from ordenes_trabajo.services import iniciar_reparacion, pausar_orden_trabajo
from repuestos.models import Repuesto, MovimientoRepuesto
from tickets.models import ComentarioTicket
from tickets.tests.test_consolidacion_ot_postgresql import ConsolidacionOTFixture
from usuarios.models import BitacoraAuditoria, RolPermiso
from usuarios.services import registrar_auditoria


class CierreTecnicoIntegracionTests(ConsolidacionOTFixture):
    def setUp(self):
        super().setUp()
        self.orden = self.crear_ot()
        self.repuesto = Repuesto.objects.create(codigo_repuesto="REP-CIERRE", nombre="Pieza", stock_actual=5, precio_unitario=Decimal("10.00"))

    def cerrar(self, **datos):
        entrada = dict(id_orden=self.orden.pk, tecnico=self.segundo, resultado="NO_REPARABLE", informe_descarte="Daño irreparable")
        entrada.update(datos)
        return cerrar_orden_trabajo(**entrada)

    def foto(self):
        return [list(modelo.objects.values().order_by(modelo._meta.pk.name)) for modelo in (
            CierreTecnico, OrdenTrabajo, type(self.ticket), type(self.activo_ot), ComentarioTicket,
            HistorialEstadoActivo, BitacoraAuditoria, Notificacion, Repuesto, MovimientoRepuesto,
        )]

    def test_exito_conserva_responsables_diagnostico_y_registra_trazabilidad(self):
        iniciar_reparacion(self.orden.pk, self.tecnico)
        diagnostico = list(Diagnostico.objects.values())
        cierre = self.cerrar(resultado="REPARACION_EXITOSA", solucion_aplicada="Cambio de pieza", pruebas_realizadas="Prueba de encendido")
        self.orden.refresh_from_db(); self.ticket.refresh_from_db(); self.activo_ot.refresh_from_db()
        self.assertEqual(self.orden.id_estado_ot.nombre, "Completada")
        self.assertEqual(self.activo_ot.id_estado_activo.nombre, "Disponible")
        self.assertEqual(self.ticket.id_estado_ticket.nombre, "Resuelto")
        self.assertEqual(cierre.id_tecnico_id, self.segundo.pk)
        self.assertEqual(self.orden.id_tecnico_responsable_id, self.tecnico.pk)
        self.assertEqual(self.ticket.id_tecnico_asignado_id, self.tecnico.pk)
        self.assertEqual(cierre.fecha_cierre, self.orden.fecha_termino)
        self.assertEqual(cierre.fecha_cierre, self.ticket.fecha_resolucion)
        self.assertEqual(list(Diagnostico.objects.values()), diagnostico)
        self.assertTrue(HistorialEstadoActivo.objects.filter(id_activo=self.activo_ot, id_usuario=self.segundo, id_estado_activo=self.activo_ot.id_estado_activo).exists())
        for accion in ("OT_COMPLETADA", "TICKET_ESTADO_CAMBIADO"):
            self.assertTrue(BitacoraAuditoria.objects.filter(accion=accion, id_usuario=self.segundo).exists())
        self.assertEqual(ComentarioTicket.objects.get().id_usuario_id, self.segundo.pk)

    def test_no_reparable_desde_diagnostico(self):
        cierre = self.cerrar()
        self.activo_ot.refresh_from_db()
        self.assertEqual(self.activo_ot.id_estado_activo.nombre, "Dado de baja")
        self.assertEqual(cierre.resultado, "NO_REPARABLE")
        aviso = Notificacion.objects.get(referencia__tipo="cierre_tecnico")
        self.assertEqual(aviso.id_usuario_id, self.admin.pk)
        self.assertEqual(aviso.canal, "CORREO_API")
        self.assertIn("Daño irreparable", aviso.mensaje)

    def test_no_reparable_desde_reparacion(self):
        iniciar_reparacion(self.orden.pk, self.tecnico)
        self.cerrar()
        self.assertEqual(CierreTecnico.objects.count(), 1)

    def test_ticket_desde_cada_estado_permitido(self):
        for estado in ("Abierto", "En Proceso", "En Espera"):
            with self.subTest(estado=estado), transaction.atomic():
                self.origen(estado)
                self.cerrar()
                self.assertEqual(ComentarioTicket.objects.count(), 1)
                transaction.set_rollback(True)

    def test_ticket_resuelto_y_cerrado_sin_efectos(self):
        for estado in ("Resuelto", "Cerrado"):
            self.origen(estado)
            antes = self.foto()
            with self.assertRaises(ValidationError): self.cerrar()
            self.assertEqual(self.foto(), antes)

    def test_campos_invalidos_sin_efectos(self):
        for entrada in ({"informe_descarte": " \t"}, {"resultado": "OTRO"}, {"resultado": "REPARACION_EXITOSA", "solucion_aplicada": "", "pruebas_realizadas": ""}):
            antes = self.foto()
            with self.assertRaises(ValidationError): self.cerrar(**entrada)
            self.assertEqual(self.foto(), antes)

    def test_estados_ot_invalidos(self):
        with self.assertRaises(ValidationError): self.cerrar(resultado="REPARACION_EXITOSA", solucion_aplicada="Cambio", pruebas_realizadas="OK")
        pausar_orden_trabajo(self.orden.pk, self.tecnico, "Espera")
        antes = self.foto()
        with self.assertRaises(ValidationError): self.cerrar()
        self.assertEqual(self.foto(), antes)

    def test_roles_inactivo_y_permisos(self):
        for actor in (self.admin, self.solicitante):
            with self.assertRaises(PermissionDenied): self.cerrar(tecnico=actor)
        self.segundo.activo = False; self.segundo.save(update_fields=["activo"])
        with self.assertRaises(PermissionDenied): self.cerrar()
        self.segundo.activo = True; self.segundo.save(update_fields=["activo"])
        for permiso in ("OT_GESTIONAR", "TICKET_ATENDER"):
            with transaction.atomic():
                RolPermiso.objects.filter(permiso__codigo=permiso).delete()
                with self.assertRaises(PermissionDenied): self.cerrar()
                transaction.set_rollback(True)
        self.assertFalse(CierreTecnico.objects.exists())

    def test_activo_inconsistente_no_se_corrige(self):
        from activos.models import EstadoActivo
        self.activo_ot.id_estado_activo = EstadoActivo.objects.get(nombre="Disponible")
        self.activo_ot.save(update_fields=["id_estado_activo"])
        antes = self.foto()
        with self.assertRaises(ValidationError): self.cerrar()
        self.assertEqual(self.foto(), antes)

    def test_asignacion_sin_finalizar_impide_cierre(self):
        from asignaciones.models import Asignacion, EstadoAsignacion, EstadoSolicitudAsignacion, SolicitudAsignacion
        solicitud = SolicitudAsignacion.objects.create(id_usuario=self.solicitante, id_categoria=self.categoria,
            id_estado_solicitud=EstadoSolicitudAsignacion.objects.get(nombre="Aprobada"), motivo="Equipo")
        Asignacion.objects.create(id_solicitud=solicitud, id_activo=self.activo_ot, id_tecnico_entrega=self.tecnico,
            id_estado_asignacion=EstadoAsignacion.objects.get(nombre="Activa"))
        antes = self.foto()
        with self.assertRaises(ValidationError): self.cerrar()
        self.assertEqual(self.foto(), antes)

    def test_otra_ot_vigente_impide_cierre(self):
        from tickets.services import crear_ticket
        otro_ticket = crear_ticket(self.otro, "Otra falla", "Detalle", id_activo=self.activo_ot.pk)
        OrdenTrabajo.objects.create(codigo_ot="OT-SEGUNDA", id_ticket=otro_ticket, id_tecnico_responsable=self.tecnico,
            id_estado_ot=self.orden.id_estado_ot, falla_reportada="Falla", fecha_inicio=self.orden.fecha_inicio)
        antes = self.foto()
        with self.assertRaises(ValidationError): self.cerrar()
        self.assertEqual(self.foto(), antes)

    def test_ot_inexistente_y_ticket_sin_activo(self):
        with self.assertRaises(ValidationError): self.cerrar(id_orden=2147483647)
        self.ticket.id_activo = None; self.ticket.save(update_fields=["id_activo"])
        antes = self.foto()
        with self.assertRaises(ValidationError): self.cerrar()
        self.assertEqual(self.foto(), antes)

    def test_administradores_validos_activos_reciben_avisos_individuales(self):
        otro_admin = self.usuario(6, "Administrador del sistema")
        inactivo = self.usuario(7, "Administrador del sistema")
        inactivo.activo = False; inactivo.save(update_fields=["activo"])
        self.cerrar()
        avisos = Notificacion.objects.filter(referencia__tipo="cierre_tecnico")
        self.assertEqual(set(avisos.values_list("id_usuario_id", flat=True)), {self.admin.pk, otro_admin.pk})
        self.assertEqual(len(set(avisos.values_list("clave_evento", flat=True))), 2)

    def test_fallo_senal_posterior_no_revierte_cierre(self):
        def fallar():
            raise RuntimeError("Consumidor no disponible")
        with patch("notificaciones.services.avisar_correo_pendiente", new=fallar):
            self.cerrar()
        self.assertEqual(CierreTecnico.objects.count(), 1)
        self.assertEqual(Notificacion.objects.filter(referencia__tipo="cierre_tecnico", estado_envio="PENDIENTE").count(), 1)

    def test_duplicado_y_repuestos_despues_del_cierre(self):
        iniciar_reparacion(self.orden.pk, self.tecnico)
        imputacion = asignar_repuesto_orden(self.orden.pk, self.repuesto.pk, 1, self.tecnico)
        self.cerrar()
        antes = self.foto()
        for operacion in (self.cerrar, lambda: asignar_repuesto_orden(self.orden.pk, self.repuesto.pk, 1, self.tecnico),
                          lambda: anular_asignacion_repuesto(self.orden.pk, imputacion["id_orden_repuesto"], "Devolver", self.tecnico)):
            with self.assertRaises(ValidationError): operacion()
            self.assertEqual(self.foto(), antes)

    def test_rollback_auditoria_y_notificaciones(self):
        for funcion in ("registrar_auditoria", "notificar_actualizacion_ticket", "registrar_notificacion"):
            antes = self.foto()
            with patch("ordenes_trabajo.cierre." + funcion, side_effect=RuntimeError("Fallo instrumental")):
                with self.assertRaises(RuntimeError): self.cerrar()
            self.assertEqual(self.foto(), antes)

    def test_sin_administradores_validos_no_bloquea_y_audita(self):
        self.admin.correo = "invalido"; self.admin.save(update_fields=["correo"])
        self.cerrar()
        self.assertTrue(BitacoraAuditoria.objects.filter(accion="CIERRE_SIN_DESTINATARIOS").exists())
        self.assertFalse(Notificacion.objects.filter(referencia__tipo="cierre_tecnico").exists())

    def test_notificacion_solicitante_usa_auditoria_real(self):
        import hashlib
        cierre = self.cerrar()
        evento = BitacoraAuditoria.objects.filter(accion="TICKET_ESTADO_CAMBIADO").latest("pk")
        clave = hashlib.sha256(f"ticket:{self.ticket.pk}:actualizacion:{evento.pk}".encode()).hexdigest()
        self.assertEqual(Notificacion.objects.filter(clave_evento=clave).count(), 1)
        self.assertEqual(CierreTecnico.objects.get().pk, cierre.pk)
        self.http.assert_not_called()

    def test_sql_rechaza_duplicado_y_texto_vacio(self):
        cierre = self.cerrar()
        for cambios in ({"id_cierre_tecnico": None}, {"informe_descarte": " \t\n"}, {"id_tecnico_id": 2147483647}):
            datos = dict(CierreTecnico.objects.values().get(pk=cierre.pk)); datos.update(cambios)
            with self.assertRaises(IntegrityError), transaction.atomic():
                if datos["id_cierre_tecnico"] is None: CierreTecnico.objects.create(**datos)
                else: CierreTecnico.objects.filter(pk=cierre.pk).update(**cambios)

    def carrera(self, primero, segundo, modulo):
        tomado, intentando, liberar = Event(), Event(), Event()
        def auditar(**datos):
            if not tomado.is_set():
                tomado.set()
                if not liberar.wait(8): raise TimeoutError("No se liberó la operación")
            return registrar_auditoria(**datos)
        def ejecutar(operacion, observar=False):
            db = connections["default"]
            self.assertEqual(db.settings_dict["NAME"], "test_siget_db")
            def observar_sql(execute, sql, params, many, context):
                if "FOR UPDATE" in sql: intentando.set()
                return execute(sql, params, many, context)
            try:
                with db.cursor() as c:
                    c.execute("SET lock_timeout='4s'"); c.execute("SET statement_timeout='8s'")
                if observar:
                    with db.execute_wrapper(observar_sql): operacion()
                else: operacion()
                return "ok"
            except ValidationError: return "rechazado"
            finally: db.close()
        with patch(modulo + ".registrar_auditoria", side_effect=auditar), ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(ejecutar, primero)
            try:
                self.assertTrue(tomado.wait(8))
                b = pool.submit(ejecutar, segundo, True)
                self.assertTrue(intentando.wait(8))
                self.assertFalse(b.done())
            finally: liberar.set()
            return a.result(timeout=12), b.result(timeout=12)

    def test_dos_cierres_simultaneos(self):
        self.assertEqual(self.carrera(self.cerrar, self.cerrar, "ordenes_trabajo.cierre"), ("ok", "rechazado"))
        self.assertEqual(CierreTecnico.objects.count(), 1)

    def test_cierre_antes_del_consumo(self):
        iniciar_reparacion(self.orden.pk, self.tecnico)
        self.assertEqual(self.carrera(self.cerrar, lambda: asignar_repuesto_orden(self.orden.pk, self.repuesto.pk, 1, self.tecnico), "ordenes_trabajo.cierre"), ("ok", "rechazado"))
        self.repuesto.refresh_from_db(); self.assertEqual(self.repuesto.stock_actual, 5)

    def test_consumo_antes_del_cierre(self):
        iniciar_reparacion(self.orden.pk, self.tecnico)
        self.assertEqual(self.carrera(lambda: asignar_repuesto_orden(self.orden.pk, self.repuesto.pk, 1, self.tecnico), self.cerrar, "ordenes_trabajo.repuestos"), ("ok", "ok"))
        self.repuesto.refresh_from_db(); self.assertEqual(self.repuesto.stock_actual, 4)

    def test_cierre_antes_de_anulacion(self):
        iniciar_reparacion(self.orden.pk, self.tecnico)
        a = asignar_repuesto_orden(self.orden.pk, self.repuesto.pk, 1, self.tecnico)
        self.assertEqual(self.carrera(self.cerrar, lambda: anular_asignacion_repuesto(self.orden.pk, a["id_orden_repuesto"], "Motivo", self.tecnico), "ordenes_trabajo.cierre"), ("ok", "rechazado"))

    def test_anulacion_antes_del_cierre(self):
        iniciar_reparacion(self.orden.pk, self.tecnico)
        a = asignar_repuesto_orden(self.orden.pk, self.repuesto.pk, 1, self.tecnico)
        self.assertEqual(self.carrera(lambda: anular_asignacion_repuesto(self.orden.pk, a["id_orden_repuesto"], "Motivo", self.tecnico), self.cerrar, "ordenes_trabajo.repuestos"), ("ok", "ok"))
        self.repuesto.refresh_from_db(); self.assertEqual(self.repuesto.stock_actual, 5)
