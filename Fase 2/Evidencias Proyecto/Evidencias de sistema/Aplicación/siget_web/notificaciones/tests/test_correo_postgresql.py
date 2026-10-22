from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from threading import Event
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.db import connections, transaction
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from asignaciones.models import Asignacion, EstadoAsignacion
from asignaciones.services import aprobar_solicitud_asignacion, crear_solicitud_asignacion, rechazar_solicitud_asignacion
from notificaciones.models import Notificacion
from notificaciones.services import (
    despachar_notificacion,
    generar_recordatorios,
    notificar_actualizacion_ticket,
    notificar_resolucion_solicitud,
    procesar_pendientes,
)
from tickets.models import EstadoTicket
from tickets.services import crear_ticket
from usuarios.tests.test_integracion_postgresql import PostgreSQLTestBase


@override_settings(
    RESEND_API_KEY="re_solo_pruebas",
    RESEND_FROM_EMAIL="SIGET <notificaciones@example.org>",
    RESEND_MAX_ATTEMPTS=3,
    RESEND_RETRY_SECONDS=1,
    SIGET_PUBLIC_URL="http://localhost:8000",
)
class NotificacionesPostgreSQLTests(PostgreSQLTestBase):
    def setUp(self):
        super().setUp()
        self.http_patch = patch("notificaciones.resend_client.requests.post")
        self.http = self.http_patch.start()
        self.addCleanup(self.http_patch.stop)
        self.http.return_value = Mock(status_code=200, headers={}, json=Mock(return_value={"id": "correo-prueba"}))

    def solicitud(self):
        self.activo()
        return crear_solicitud_asignacion(self.solicitante, self.categoria.pk, "Equipo de trabajo")

    def aprobada(self):
        s = self.solicitud()
        aprobar_solicitud_asignacion(s, self.admin)
        return s, Notificacion.objects.get()

    def asignacion(self, horas=24):
        _, identificador = self.entregar()
        Notificacion.objects.all().delete()
        a = Asignacion.objects.get(pk=identificador)
        a.fecha_devolucion_prevista = timezone.now() + timedelta(hours=horas)
        a.save(update_fields=["fecha_devolucion_prevista"])
        return a

    def habilitar_ahora(self, n):
        n.refresh_from_db()
        n.proximo_intento = timezone.now() - timedelta(seconds=1)
        n.save(update_fields=["proximo_intento"])

    def test_aprobacion_api_guarda_aviso_y_despacha_despues_del_commit(self):
        s = self.solicitud()
        r = self.cliente(self.admin).post(f"/api/solicitudes-asignacion/{s.pk}/aprobar/", {}, format="json")
        self.assertEqual(r.status_code, 200)
        n = Notificacion.objects.get()
        self.assertEqual(n.estado_envio, "PENDIENTE")
        self.http.assert_not_called()
        self.assertEqual(n.datos_envio["to"], [self.solicitante.correo])
        self.assertIn("todavía no asigna", n.datos_envio["text"])
        enlace = "http://localhost:8000" + reverse("asignaciones_web:detalle", args=[s.pk])
        self.assertIn(enlace, n.datos_envio["text"])
        self.assertIn(f'href="{enlace}"', n.datos_envio["html"])
        self.assertNotIn("/confirmacion/", n.datos_envio["html"])
        self.assertTrue(despachar_notificacion(n.pk))
        n.refresh_from_db()
        self.assertEqual((n.estado_envio, n.id_proveedor, n.intentos_envio), ("ENVIADA", "correo-prueba", 1))
        self.assertIsNotNone(n.fecha_envio)
        self.assertFalse(despachar_notificacion(n.pk))
        self.http.assert_called_once()

    def test_rechazo_incluye_motivo_escapado_en_plantilla_html(self):
        s = self.solicitud()
        rechazar_solicitud_asignacion(s, self.admin, '<script>alert("x")</script>')
        n = Notificacion.objects.get()
        self.assertIn("Rechazada", n.titulo)
        self.assertIn("&lt;script&gt;", n.datos_envio["html"])
        self.assertNotIn("<script>", n.datos_envio["html"])
        self.assertTrue(despachar_notificacion(n.pk))

    def test_fallo_resend_no_revierte_aprobacion_confirmada(self):
        s, n = self.aprobada()
        self.http.return_value.status_code = 503
        despachar_notificacion(n.pk)
        s.refresh_from_db()
        n.refresh_from_db()
        self.assertEqual(s.id_estado_solicitud.nombre, "Aprobada")
        self.assertEqual(n.estado_envio, "ERROR")
        self.assertIn("503", n.ultimo_error)
        self.assertTrue(n.reintento_permitido)
        self.assertIsNotNone(n.proximo_intento)

    def test_rollback_del_negocio_no_deja_aviso(self):
        s = self.solicitud()
        with self.assertRaises(ValueError), transaction.atomic():
            aprobar_solicitud_asignacion(s, self.admin)
            raise ValueError("rollback deliberado")
        self.assertFalse(Notificacion.objects.exists())
        s.refresh_from_db()
        self.assertEqual(s.id_estado_solicitud.nombre, "Pendiente")
        self.http.assert_not_called()

    def test_reintento_respeta_espera_y_conserva_payload_idempotencia(self):
        _, n = self.aprobada()
        self.http.return_value.status_code = 429
        self.http.return_value.headers = {"Retry-After": "120"}
        despachar_notificacion(n.pk)
        first = self.http.call_args
        self.assertFalse(despachar_notificacion(n.pk))
        self.assertEqual(self.http.call_count, 1)
        self.habilitar_ahora(n)
        self.http.return_value.status_code = 200
        with override_settings(RESEND_FROM_EMAIL="Otro <otro@example.org>"):
            despachar_notificacion(n.pk)
        second = self.http.call_args
        self.assertEqual(first.kwargs["json"], second.kwargs["json"])
        self.assertEqual(first.kwargs["headers"]["Idempotency-Key"], second.kwargs["headers"]["Idempotency-Key"])
        n.refresh_from_db()
        self.assertEqual(n.intentos_envio, 2)
        self.assertEqual(n.estado_envio, "ENVIADA")

    def test_limite_de_intentos_no_se_supera(self):
        _, n = self.aprobada()
        self.http.return_value.status_code = 503
        for _ in range(3):
            self.habilitar_ahora(n)
            despachar_notificacion(n.pk)
        self.habilitar_ahora(n)
        self.assertFalse(despachar_notificacion(n.pk))
        n.refresh_from_db()
        self.assertFalse(n.reintento_permitido)
        self.assertEqual(n.intentos_envio, 3)
        self.assertEqual(self.http.call_count, 3)

    def test_repetir_evento_no_crea_otro_correo(self):
        s, n = self.aprobada()
        with transaction.atomic():
            otra = notificar_resolucion_solicitud(s)
        self.assertEqual(otra.pk, n.pk)
        self.assertEqual(Notificacion.objects.count(), 1)

    def test_dos_workers_no_envian_la_misma_notificacion(self):
        _, n = self.aprobada()
        entro, continuar = Event(), Event()

        def proveedor(*args, **kwargs):
            entro.set()
            self.assertTrue(continuar.wait(5))
            return Mock(status_code=200, json=Mock(return_value={"id": "concurrente"}))

        self.http.side_effect = proveedor

        def ejecutar():
            try:
                return despachar_notificacion(n.pk)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            primero = pool.submit(ejecutar)
            self.assertTrue(entro.wait(5))
            try:
                self.assertFalse(pool.submit(ejecutar).result(timeout=5))
            finally:
                continuar.set()
            self.assertTrue(primero.result(timeout=5))
        self.http.assert_called_once()

    def test_fuera_de_ventana_segura_no_reenvia_un_resultado_indeterminado(self):
        _, n = self.aprobada()
        n.fecha_primer_intento = timezone.now() - timedelta(hours=24)
        n.intentos_envio = 1
        n.save(update_fields=["fecha_primer_intento", "intentos_envio"])
        self.assertFalse(despachar_notificacion(n.pk))
        n.refresh_from_db()
        self.assertFalse(n.reintento_permitido)
        self.assertIn("manual", n.ultimo_error)
        self.http.assert_not_called()

    def test_intento_persistido_si_el_proceso_falla_durante_http(self):
        _, n = self.aprobada()
        self.http.side_effect = RuntimeError("simulación de caída")
        with self.assertRaises(RuntimeError):
            despachar_notificacion(n.pk)
        n.refresh_from_db()
        self.assertEqual(n.intentos_envio, 1)
        self.assertIsNotNone(n.fecha_primer_intento)
        self.http.side_effect = None
        self.assertTrue(despachar_notificacion(n.pk))

    def test_recordatorio_24_horas_persistido_una_vez(self):
        a = self.asignacion()
        self.assertEqual(generar_recordatorios(), 1)
        self.assertEqual(generar_recordatorios(), 0)
        n = Notificacion.objects.get()
        self.assertEqual(n.id_usuario, self.solicitante)
        self.assertIn(a.id_activo.codigo_inventario, n.mensaje)
        self.assertIn(timezone.localtime(a.fecha_devolucion_prevista).strftime("%d/%m/%Y %H:%M"), n.mensaje)
        self.assertEqual(procesar_pendientes(), 1)

    def test_recordatorios_no_incluyen_sin_fecha_fuera_de_ventana_ni_vencida(self):
        a = self.asignacion(25)
        self.assertEqual(generar_recordatorios(), 0)
        a.fecha_entrega = timezone.now() - timedelta(days=2)
        a.save(update_fields=["fecha_entrega"])
        for fecha in (None, timezone.now() - timedelta(seconds=1)):
            a.fecha_devolucion_prevista = fecha
            a.save(update_fields=["fecha_devolucion_prevista"])
            self.assertEqual(generar_recordatorios(), 0)

    def test_recordatorio_de_asignacion_devuelta_no_se_envia(self):
        a = self.asignacion()
        generar_recordatorios()
        a.id_estado_asignacion = EstadoAsignacion.objects.get(nombre="Finalizada")
        a.save(update_fields=["id_estado_asignacion"])
        self.assertEqual(generar_recordatorios(), 0)
        self.assertEqual(procesar_pendientes(), 0)
        n = Notificacion.objects.get()
        self.assertFalse(n.reintento_permitido)
        self.assertIn("cancelado", n.ultimo_error)
        self.http.assert_not_called()

    def test_cambio_de_fecha_invalida_el_aviso_anterior_y_crea_el_nuevo(self):
        a = self.asignacion(20)
        generar_recordatorios()
        anterior = Notificacion.objects.get()
        a.fecha_devolucion_prevista += timedelta(hours=1)
        a.save(update_fields=["fecha_devolucion_prevista"])
        self.assertEqual(generar_recordatorios(), 1)
        self.assertFalse(despachar_notificacion(anterior.pk))
        self.assertEqual(procesar_pendientes(), 1)
        self.http.assert_called_once()

    def test_notificacion_ticket_resuelto_y_deduplicacion(self):
        t = crear_ticket(self.solicitante, "Falla", "No enciende")
        with transaction.atomic():
            t.id_estado_ticket = EstadoTicket.objects.get(nombre="Resuelto")
            t.save(update_fields=["id_estado_ticket"])
            n = notificar_actualizacion_ticket(t, id_evento="auditoria-123", detalle="Reparación finalizada")
            repetido = notificar_actualizacion_ticket(t, id_evento="auditoria-123", detalle="Reparación finalizada")
        self.assertEqual(n.pk, repetido.pk)
        self.assertIn("Resuelto", n.titulo)
        enlace = "http://localhost:8000" + reverse("tickets_web:detalle", args=[t.pk])
        self.assertIn(enlace, n.datos_envio["text"])
        self.assertIn(f'href="{enlace}"', n.datos_envio["html"])
        self.assertNotIn("/confirmacion/", n.datos_envio["html"])
        self.assertTrue(despachar_notificacion(n.pk))

    def test_contrato_no_admite_eventos_sin_transaccion_ni_identificador(self):
        t = crear_ticket(self.solicitante, "Falla", "No enciende")
        with self.assertRaises(RuntimeError):
            notificar_actualizacion_ticket(t, id_evento="a", detalle="Atención")
        with transaction.atomic(), self.assertRaises(ValueError):
            notificar_actualizacion_ticket(t, id_evento="", detalle="Atención")
        for detalle in (None, "", "   "):
            with transaction.atomic(), self.assertRaises(ValueError):
                notificar_actualizacion_ticket(t, id_evento="auditoria-1", detalle=detalle)
        self.assertFalse(Notificacion.objects.exists())

    def test_esquema_aditivo_repetido_conserva_notificacion(self):
        _, n = self.aprobada()
        for _ in range(2):
            call_command("preparar_notificaciones", stdout=StringIO())
        self.assertTrue(Notificacion.objects.filter(pk=n.pk).exists())

    def test_comando_reintenta_despues_de_corregir_configuracion(self):
        _, n = self.aprobada()
        self.http.return_value.status_code = 401
        despachar_notificacion(n.pk)
        n.refresh_from_db()
        self.assertFalse(n.reintento_permitido)
        self.http.return_value.status_code = 200
        call_command("reintentar_correo", n.pk, stdout=StringIO())
        n.refresh_from_db()
        self.assertEqual(n.estado_envio, "ENVIADA")
