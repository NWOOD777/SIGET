"""Alternativa A: fase explícita, legado conservador, activos y concurrencia."""
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

from django.db import connections, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from activos.models import Activo, EstadoActivo
from notificaciones.models import Notificacion
from ordenes_trabajo.auditoria_fases import MARCADOR_FASE
from ordenes_trabajo.models import OrdenTrabajo
from ordenes_trabajo.services import (
    iniciar_reparacion, pausar_orden_trabajo, reanudar_orden_trabajo,
    reasignar_orden_trabajo,
)
from tickets.tests.test_consolidacion_ot_postgresql import ConsolidacionOTFixture
from usuarios.models import BitacoraAuditoria


class ReanudacionFaseOTTests(ConsolidacionOTFixture):
    def evento(self, orden, accion="OT_PAUSADA"):
        return BitacoraAuditoria.objects.filter(
            modulo="ORDENES_TRABAJO", entidad_afectada="orden_trabajo",
            id_registro_afectado=orden.pk, accion=accion,
        ).order_by("-id_auditoria").first()

    def instantanea(self, orden):
        return (OrdenTrabajo.objects.values().get(pk=orden.pk),
                Activo.objects.values().get(pk=orden.id_ticket.id_activo_id),
                BitacoraAuditoria.objects.count(), Notificacion.objects.count())

    def legado(self, orden):
        evento = self.evento(orden)
        evento.detalle_evento = f"Se pausó la OT {orden.codigo_ot}. Motivo: {orden.justificacion_pausa}"
        evento.save(update_fields=["detalle_evento"])

    def test_fases_repetidas_historial_y_contrato_pyside(self):
        orden = self.crear_ot()
        cliente = self.cliente(self.tecnico)
        campos = None
        for fase, estado_activo in (("En Diagnóstico", "En revisión"), ("En Reparación", "En reparación")):
            if fase == "En Reparación":
                iniciar_reparacion(orden.pk, self.tecnico)
            for _ in range(3):
                respuesta = cliente.post(f"/api/ordenes-trabajo/{orden.pk}/pausar/", {"justificacion": "Repuesto pendiente"}, format="json")
                self.assertEqual(respuesta.status_code, 200)
                orden.refresh_from_db()
                datos = json.loads(self.evento(orden).detalle_evento.rsplit(MARCADOR_FASE, 1)[1])
                self.assertEqual(datos["estado_anterior"], fase)
                self.assertEqual(datos["id_orden"], orden.pk)
                self.assertEqual(datos["version"], 1)
                respuesta = cliente.post(f"/api/ordenes-trabajo/{orden.pk}/reanudar/")
                self.assertEqual(respuesta.status_code, 200, respuesta.data)
                self.assertEqual(respuesta.data["estado"], fase)
                self.assertIsNone(respuesta.data["justificacion_pausa"])
                campos = campos or set(respuesta.data)
                self.assertEqual(set(respuesta.data), campos)
                activo = Activo.objects.get(pk=orden.id_ticket.id_activo_id)
                self.assertEqual(activo.id_estado_activo.nombre, estado_activo)
                datos = json.loads(self.evento(orden, "OT_REANUDADA").detalle_evento.rsplit(MARCADOR_FASE, 1)[1])
                self.assertEqual(datos["estado_nuevo"], fase)
                self.assertEqual(datos["estado_anterior"], "Pausada")
        historial = cliente.get(f"/api/ordenes-trabajo/{orden.pk}/historial/")
        self.assertEqual(historial.status_code, 200)
        self.assertEqual(sum(e["accion"] == "OT_PAUSADA" for e in historial.data), 6)
        self.assertEqual(sum(e["accion"] == "OT_REANUDADA" for e in historial.data), 6)

    def test_legacy_primer_ciclo_en_ambas_fases_con_fechas_iguales(self):
        for reparar in (False, True):
            with self.subTest(reparar=reparar):
                orden = self.segunda_ot()
                if reparar:
                    iniciar_reparacion(orden.pk, self.tecnico)
                pausar_orden_trabajo(orden.pk, self.tecnico, "Pausa histórica")
                self.legado(orden)
                # El orden causal usa ID, sin depender de desempates de fecha.
                BitacoraAuditoria.objects.filter(entidad_afectada="orden_trabajo", id_registro_afectado=orden.pk).update(fecha_evento=timezone.now())
                reanudar_orden_trabajo(orden.pk, self.tecnico)
                orden.refresh_from_db()
                self.assertEqual(orden.id_estado_ot.nombre, "En Reparación" if reparar else "En Diagnóstico")

    def test_legacy_incompleto_o_ambiguo_rechazado_sin_efectos(self):
        for problema in ("sin_creacion", "sin_pausa", "reanudacion_antigua", "accion_desconocida"):
            with self.subTest(problema=problema):
                orden = self.segunda_ot()
                pausar_orden_trabajo(orden.pk, self.tecnico, "Histórica")
                self.legado(orden)
                if problema == "sin_creacion":
                    self.evento(orden, "OT_CREADA").delete()
                elif problema == "sin_pausa":
                    self.evento(orden).delete()
                elif problema == "reanudacion_antigua":
                    evento = self.evento(orden)
                    BitacoraAuditoria.objects.create(
                        id_usuario=self.tecnico, modulo="ORDENES_TRABAJO", accion="OT_REANUDADA",
                        entidad_afectada="orden_trabajo", id_registro_afectado=orden.pk, detalle_evento="Legado",
                    )
                    evento.pk = None
                    evento.save(force_insert=True)
                else:
                    BitacoraAuditoria.objects.create(
                        id_usuario=self.tecnico, modulo="ORDENES_TRABAJO", accion="OT_CAMBIO_DESCONOCIDO",
                        entidad_afectada="orden_trabajo", id_registro_afectado=orden.pk, detalle_evento="Sin contrato",
                    )
                antes = self.instantanea(orden)
                respuesta = self.cliente(self.tecnico).post(f"/api/ordenes-trabajo/{orden.pk}/reanudar/")
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn("certeza", str(respuesta.data))
                self.assertEqual(self.instantanea(orden), antes)

    def test_metadatos_invalidos_no_caen_en_reconstruccion_libre(self):
        cambios = ({"version": 2}, {"version": True}, {"id_orden": -1}, {"id_orden": True}, {"estado_anterior": "Completada"},
                   {"estado_anterior": []}, {"motivo": "Otro"}, {"accion": "OT_REANUDADA"})
        for cambio in cambios:
            with self.subTest(cambio=cambio):
                orden = self.segunda_ot()
                pausar_orden_trabajo(orden.pk, self.tecnico, "Motivo")
                evento = self.evento(orden)
                resumen, raw = evento.detalle_evento.rsplit(MARCADOR_FASE, 1)
                datos = json.loads(raw)
                datos.update(cambio)
                evento.detalle_evento = resumen + MARCADOR_FASE + json.dumps(datos)
                evento.save(update_fields=["detalle_evento"])
                antes = self.instantanea(orden)
                with self.assertRaises(ValidationError):
                    reanudar_orden_trabajo(orden.pk, self.tecnico)
                self.assertEqual(self.instantanea(orden), antes)

    def test_registro_estructurado_malformado_rechazado_sin_fallback(self):
        orden = self.crear_ot()
        pausar_orden_trabajo(orden.pk, self.tecnico, "Pausa")
        evento = self.evento(orden)
        for raw in ("{", "null", "[]"):
            evento.detalle_evento = "Pausa" + MARCADOR_FASE + raw
            evento.save(update_fields=["detalle_evento"])
            antes = self.instantanea(orden)
            with self.assertRaises(ValidationError):
                reanudar_orden_trabajo(orden.pk, self.tecnico)
            self.assertEqual(self.instantanea(orden), antes)

    def test_activo_incompatible_en_ambas_fases_no_se_corrige_implicitamente(self):
        for reparar in (False, True):
            orden = self.segunda_ot()
            if reparar:
                iniciar_reparacion(orden.pk, self.tecnico)
            pausar_orden_trabajo(orden.pk, self.tecnico, "Pausa")
            activo = orden.id_ticket.id_activo
            activo.id_estado_activo = EstadoActivo.objects.get(nombre="Disponible")
            activo.save(update_fields=["id_estado_activo"])
            antes = self.instantanea(orden)
            respuesta = self.cliente(self.tecnico).post(f"/api/ordenes-trabajo/{orden.pk}/reanudar/")
            self.assertEqual(respuesta.status_code, 400)
            self.assertIn("id_activo", respuesta.data)
            self.assertEqual(self.instantanea(orden), antes)

    def test_rollback_de_pausa_y_reanudacion_si_falla_auditoria(self):
        orden = self.crear_ot()
        for operacion in ("pausar", "reanudar"):
            if operacion == "reanudar":
                pausar_orden_trabajo(orden.pk, self.tecnico, "Espera")
            antes = self.instantanea(orden)
            with patch("ordenes_trabajo.services.registrar_auditoria", side_effect=ValidationError("Fallo")):
                with self.assertRaises(ValidationError):
                    if operacion == "pausar":
                        pausar_orden_trabajo(orden.pk, self.tecnico, "Espera")
                    else:
                        reanudar_orden_trabajo(orden.pk, self.tecnico)
            self.assertEqual(self.instantanea(orden), antes)

    def test_motivo_no_puede_suplantar_registro_estructurado(self):
        orden = self.crear_ot()
        motivo = 'Texto libre' + MARCADOR_FASE + '{"estado_anterior":"En Reparación"}'
        pausar_orden_trabajo(orden.pk, self.tecnico, motivo)
        reanudar_orden_trabajo(orden.pk, self.tecnico)
        orden.refresh_from_db()
        self.assertEqual(orden.id_estado_ot.nombre, "En Diagnóstico")

    def test_reanudacion_y_reasignacion_concurrentes_preservan_ambos_cambios(self):
        # Reutiliza el arnés con dos conexiones y esperas limitadas de consolidación.
        from tickets.tests.test_consolidacion_ot_postgresql import CaracterizacionIntegracionOTTests
        for primero_reanudar in (True, False):
            orden = self.segunda_ot()
            pausar_orden_trabajo(orden.pk, self.tecnico, "Pausa")
            reanudar = lambda: reanudar_orden_trabajo(orden.pk, self.tecnico)
            reasignar = lambda: reasignar_orden_trabajo(orden.pk, self.tecnico, self.segundo, "Turno")
            resultados = CaracterizacionIntegracionOTTests.carrera_controlada(
                self, reanudar if primero_reanudar else reasignar,
                reasignar if primero_reanudar else reanudar,
                "OT_REANUDADA" if primero_reanudar else "OT_REASIGNADA",
            )
            self.assertEqual(resultados, (200, 200))
            orden.refresh_from_db()
            self.assertEqual(orden.id_estado_ot.nombre, "En Diagnóstico")
            self.assertEqual(orden.id_tecnico_responsable_id, self.segundo.pk)

    def test_pausa_y_reanudacion_misma_ot_en_ambos_ordenes(self):
        from tickets.tests.test_consolidacion_ot_postgresql import CaracterizacionIntegracionOTTests
        for repeticion in range(3):
            for primero_pausar in (True, False):
                with self.subTest(repeticion=repeticion, primero_pausar=primero_pausar):
                    orden = self.segunda_ot()
                    if not primero_pausar:
                        pausar_orden_trabajo(orden.pk, self.tecnico, "Pausa previa")
                    pausar = lambda: pausar_orden_trabajo(orden.pk, self.tecnico, "Pausa nueva")
                    reanudar = lambda: reanudar_orden_trabajo(orden.pk, self.tecnico)
                    resultados = CaracterizacionIntegracionOTTests.carrera_controlada(
                        self, pausar if primero_pausar else reanudar,
                        reanudar if primero_pausar else pausar,
                        "OT_PAUSADA" if primero_pausar else "OT_REANUDADA",
                    )
                    self.assertEqual(resultados, (200, 200))
                    orden.refresh_from_db()
                    self.assertEqual(orden.id_estado_ot.nombre, "En Diagnóstico" if primero_pausar else "Pausada")
                    if not primero_pausar:
                        # La nueva pausa también debe conservar el origen correcto.
                        reanudar_orden_trabajo(orden.pk, self.tecnico)
                        orden.refresh_from_db()
                        self.assertEqual(orden.id_estado_ot.nombre, "En Diagnóstico")

    def test_activo_cambia_antes_del_bloqueo_y_reanudacion_revalida(self):
        orden = self.crear_ot()
        pausar_orden_trabajo(orden.pk, self.tecnico, "Pausa")
        listo, continuar = Event(), Event()

        def cambiar_activo():
            db = connections["default"]
            self.assertEqual(db.settings_dict["NAME"], "test_siget_db")
            try:
                with db.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '4s'")
                    cursor.execute("SET statement_timeout = '8s'")
                with transaction.atomic():
                    activo = Activo.objects.select_for_update(of=("self",)).get(pk=self.activo_ot.pk)
                    activo.id_estado_activo = EstadoActivo.objects.get(nombre="Disponible")
                    activo.save(update_fields=["id_estado_activo"])
                    listo.set()
                    if not continuar.wait(10):
                        raise TimeoutError("No se liberó activo")
            finally:
                db.close()

        def observar(execute, sql, params, many, context):
            if 'FROM "activo"' in sql and "FOR UPDATE" in sql:
                continuar.set()
            return execute(sql, params, many, context)

        with ThreadPoolExecutor(max_workers=1) as pool:
            futuro = pool.submit(cambiar_activo)
            try:
                self.assertTrue(listo.wait(10))
                with connections["default"].execute_wrapper(observar):
                    with self.assertRaises(ValidationError):
                        reanudar_orden_trabajo(orden.pk, self.tecnico)
            finally:
                continuar.set()
            futuro.result(timeout=15)
        orden.refresh_from_db()
        self.assertEqual(orden.id_estado_ot.nombre, "Pausada")
        self.assertFalse(self.evento(orden, "OT_REANUDADA"))
