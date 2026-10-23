from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from io import StringIO
from threading import Event, get_ident
from time import monotonic
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.db import connections, transaction
from django.test import override_settings
from psycopg import OperationalError

from asignaciones.services import aprobar_solicitud_asignacion, crear_solicitud_asignacion
from notificaciones.models import CANAL_PLATAFORMA, Notificacion
from notificaciones.senales import avisar_correo_pendiente, escuchar_correos, esperar_aviso
from notificaciones.services import procesar_pendientes, registrar_notificacion
from usuarios.tests.test_integracion_postgresql import PostgreSQLTestBase

COMANDO = "notificaciones.management.commands.procesar_notificaciones"


class FinDelConsumidor(Exception):
    pass


@override_settings(
    RESEND_API_KEY="re_solo_pruebas",
    RESEND_FROM_EMAIL="SIGET <notificaciones@example.org>",
    RESEND_MAX_ATTEMPTS=3,
    RESEND_RETRY_SECONDS=1,
    SIGET_PUBLIC_URL="http://localhost:8000",
)
class DespachoInmediatoPostgreSQLTests(PostgreSQLTestBase):
    def setUp(self):
        super().setUp()
        http_patch = patch("notificaciones.resend_client.requests.post")
        self.http = http_patch.start()
        self.addCleanup(http_patch.stop)
        self.http.return_value = Mock(status_code=200, headers={}, json=Mock(return_value={"id": "correo-prueba"}))

    def aviso(self, evento="ticket:prueba:actualizacion:1", **kwargs):
        return registrar_notificacion(
            usuario=self.solicitante,
            evento=evento,
            titulo="Actualización de soporte",
            mensaje="Respuesta de soporte registrada.",
            **kwargs,
        )

    def test_senal_sin_datos_solo_despues_del_commit_y_http_fuera_de_la_peticion(self):
        with escuchar_correos() as escucha:
            with transaction.atomic():
                n = self.aviso()
                self.assertFalse(esperar_aviso(escucha, 0.05))
                self.http.assert_not_called()
            senales = list(escucha.notifies(timeout=1, stop_after=1))
            self.assertEqual([(s.channel, s.payload) for s in senales], [("siget_correo_pendiente", "")])
            self.http.assert_not_called()
            self.assertEqual(procesar_pendientes(), 1)
            n.refresh_from_db()
            self.assertEqual(n.estado_envio, "ENVIADA")
            self.http.assert_called_once()

    def test_rollback_del_negocio_no_conserva_aviso_ni_emite_senal(self):
        with escuchar_correos() as escucha:
            with self.assertRaises(ValueError), transaction.atomic():
                self.aviso()
                raise ValueError("Rollback de la operación")
            self.assertFalse(esperar_aviso(escucha, 0.05))
        self.assertFalse(Notificacion.objects.exists())
        self.http.assert_not_called()

    def test_rollback_de_savepoint_descarta_su_senal_aunque_confirme_la_transaccion_exterior(self):
        with escuchar_correos() as escucha:
            with transaction.atomic():
                with self.assertRaises(ValueError), transaction.atomic():
                    self.aviso()
                    raise ValueError("Rollback del savepoint")
            self.assertFalse(esperar_aviso(escucha, 0.05))
        self.assertFalse(Notificacion.objects.exists())

    def test_repetir_evento_no_emite_otra_senal_ni_duplica_el_correo(self):
        with escuchar_correos() as escucha:
            with transaction.atomic():
                n = self.aviso()
            self.assertTrue(esperar_aviso(escucha, 1))
            with transaction.atomic():
                repetida = self.aviso()
            self.assertEqual(n.pk, repetida.pk)
            self.assertFalse(esperar_aviso(escucha, 0.05))
        self.assertEqual(procesar_pendientes(), 1)
        self.assertEqual(procesar_pendientes(), 0)
        self.http.assert_called_once()

    def test_aviso_exclusivo_de_plataforma_no_despierta_el_consumidor_ni_envia_correo(self):
        with escuchar_correos() as escucha:
            with transaction.atomic():
                n = self.aviso(canal=CANAL_PLATAFORMA)
            self.assertFalse(esperar_aviso(escucha, 0.05))
        self.assertEqual(procesar_pendientes(), 0)
        self.assertEqual(n.estado_envio, "NO_APLICA")
        self.http.assert_not_called()

    def test_fallo_de_senal_no_revierte_el_negocio_y_el_barrido_recupera_el_correo(self):
        self.activo()
        solicitud = crear_solicitud_asignacion(self.solicitante, self.categoria.pk, "Equipo de trabajo")

        def fallar_senal():
            raise OperationalError("Conexión de señal interrumpida")

        with (
            patch("notificaciones.services.avisar_correo_pendiente", new=fallar_senal),
            self.assertLogs("django.db.backends.base", level="ERROR"),
        ):
            aprobar_solicitud_asignacion(solicitud, self.admin)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.id_estado_solicitud.nombre, "Aprobada")
        n = Notificacion.objects.get()
        self.assertEqual(n.estado_envio, "PENDIENTE")
        self.assertEqual(procesar_pendientes(), 1)
        n.refresh_from_db()
        self.assertEqual(n.estado_envio, "ENVIADA")

    def test_consumidor_continuo_despierta_por_commit_sin_esperar_los_60_segundos(self):
        self.activo()
        solicitud = crear_solicitud_asignacion(self.solicitante, self.categoria.pk, "Equipo de trabajo")
        esperando, enviado, detener = Event(), Event(), Event()
        hilos_http = []

        def proveedor(*args, **kwargs):
            hilos_http.append(get_ident())
            enviado.set()
            return Mock(status_code=200, headers={}, json=Mock(return_value={"id": "correo-inmediato"}))

        def esperar(escucha, timeout):
            if detener.is_set():
                raise FinDelConsumidor
            esperando.set()
            resultado = esperar_aviso(escucha, min(timeout, 15))
            if detener.is_set():
                raise FinDelConsumidor
            return resultado

        def consumir():
            try:
                call_command("procesar_notificaciones", continuo=True, intervalo=60, sin_recordatorios=True, stdout=StringIO())
            except FinDelConsumidor:
                pass
            finally:
                connections.close_all()

        self.http.side_effect = proveedor
        with patch(f"{COMANDO}.esperar_aviso", new=esperar), ThreadPoolExecutor(max_workers=1) as pool:
            tarea = pool.submit(consumir)
            try:
                self.assertTrue(esperando.wait(5), "El consumidor no comenzó a escuchar")
                inicio = monotonic()
                respuesta = self.cliente(self.admin).post(f"/api/solicitudes-asignacion/{solicitud.pk}/aprobar/", {}, format="json")
                self.assertEqual(respuesta.status_code, 200)
                self.assertTrue(enviado.wait(5), "El aviso no despertó al consumidor después del commit")
                self.assertLess(monotonic() - inicio, 5)
                self.assertNotIn(get_ident(), hilos_http, "La petición web no debe efectuar el HTTP de correo")
            finally:
                detener.set()
                avisar_correo_pendiente()
                tarea.result(timeout=20)
        n = Notificacion.objects.get()
        self.assertEqual((n.estado_envio, n.intentos_envio), ("ENVIADA", 1))
        self.http.assert_called_once()

    def test_arranque_recupera_avisos_creados_cuando_no_habia_consumidor(self):
        with transaction.atomic():
            n = self.aviso()
        with patch(f"{COMANDO}.esperar_aviso", side_effect=FinDelConsumidor), self.assertRaises(FinDelConsumidor):
            call_command("procesar_notificaciones", continuo=True, sin_recordatorios=True, stdout=StringIO())
        n.refresh_from_db()
        self.assertEqual(n.estado_envio, "ENVIADA")
        self.http.assert_called_once()

    def test_timeout_del_respaldo_revisa_la_cola_y_los_recordatorios(self):
        reloj = [0.0]
        esperas = []

        def esperar(escucha, timeout):
            esperas.append(timeout)
            if len(esperas) > 1:
                raise FinDelConsumidor
            # Simula un aviso persistido sin señal y el paso del intervalo de respaldo.
            with patch("notificaciones.services.avisar_correo_pendiente", new=lambda: None), transaction.atomic():
                self.aviso()
            reloj[0] = 60.0
            return False

        with (
            patch(f"{COMANDO}.time.monotonic", side_effect=lambda: reloj[0]),
            patch(f"{COMANDO}.esperar_aviso", new=esperar),
            patch(f"{COMANDO}.generar_recordatorios", return_value=0) as recordatorios,
            self.assertRaises(FinDelConsumidor),
        ):
            call_command("procesar_notificaciones", continuo=True, intervalo=60, stdout=StringIO())
        self.assertEqual(esperas, [60, 60])
        self.assertEqual(recordatorios.call_count, 2)
        self.assertEqual(Notificacion.objects.get().estado_envio, "ENVIADA")

    def test_reconexion_vuelve_a_escuchar_y_recupera_la_cola(self):
        with transaction.atomic():
            n = self.aviso()
        with (
            patch(f"{COMANDO}.escuchar_correos", side_effect=[OperationalError("Desconectado"), nullcontext(Mock())]) as escuchar,
            patch(f"{COMANDO}.time.sleep") as pausa,
            patch(f"{COMANDO}.esperar_aviso", side_effect=FinDelConsumidor),
            self.assertRaises(FinDelConsumidor),
        ):
            call_command("procesar_notificaciones", continuo=True, sin_recordatorios=True, stdout=StringIO(), stderr=StringIO())
        self.assertEqual(escuchar.call_count, 2)
        pausa.assert_called_once_with(5)
        n.refresh_from_db()
        self.assertEqual(n.estado_envio, "ENVIADA")
