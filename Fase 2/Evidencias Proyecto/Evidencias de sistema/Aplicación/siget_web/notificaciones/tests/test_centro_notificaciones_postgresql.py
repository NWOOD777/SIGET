"""Pruebas de integración en PostgreSQL para E10-H29 — Centro de avisos en plataforma."""

from datetime import timedelta
from unittest.mock import Mock, patch

from django.db import transaction
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from asignaciones.models import Asignacion
from asignaciones.services import (
    aprobar_solicitud_asignacion,
    crear_solicitud_asignacion,
    rechazar_solicitud_asignacion,
    registrar_devolucion_asignacion,
    registrar_entrega_asignacion,
)
from notificaciones.models import (
    CANAL_AMBOS,
    CANAL_CORREO_API,
    CANAL_PLATAFORMA,
    Notificacion,
)
from notificaciones.services import (
    contar_notificaciones_pendientes,
    despachar_notificacion,
    generar_recordatorios,
    notificar_actualizacion_ticket,
    notificar_entrega_asignacion,
    procesar_pendientes,
    registrar_notificacion,
)
from tickets.models import EstadoTicket, Ticket
from tickets.services import (
    ESTADO_TICKET_EN_PROCESO,
    asignar_ticket,
    cambiar_estado_ticket,
    crear_ticket,
    registrar_atencion_ticket,
)
from usuarios.tests.test_integracion_postgresql import PostgreSQLTestBase


@override_settings(
    RESEND_API_KEY="re_solo_pruebas",
    RESEND_FROM_EMAIL="SIGET <notificaciones@example.org>",
    RESEND_MAX_ATTEMPTS=3,
    RESEND_RETRY_SECONDS=1,
    SIGET_PUBLIC_URL="http://localhost:8000",
)
class CentroNotificacionesPostgreSQLTests(PostgreSQLTestBase):
    def setUp(self):
        super().setUp()
        self.http_patch = patch("notificaciones.resend_client.requests.post")
        self.http = self.http_patch.start()
        self.addCleanup(self.http_patch.stop)
        self.http.return_value = Mock(
            status_code=200,
            headers={},
            json=Mock(return_value={"id": "correo-prueba"}),
        )

    def crear_solicitud(self, usuario=None):
        self.activo()
        return crear_solicitud_asignacion(
            usuario or self.solicitante,
            self.categoria.pk,
            "Equipo portátil para labores académicas",
        )

    def test_criterio_1_indicador_numerico_en_barra_superior_al_cambiar_ticket_o_asignacion(self):
        """CA1: Al cambiar el estado de un ticket o asignación, el portal muestra el contador en barra superior."""
        web = self.cliente(self.solicitante)
        r_inicial = web.get(reverse("inicio"))
        self.assertEqual(r_inicial.status_code, 200)
        self.assertNotIn('id="top-notificaciones-contador"', r_inicial.content.decode())

        # 1. Cambio en solicitud de asignación (Aprobada)
        solicitud = self.crear_solicitud()
        aprobar_solicitud_asignacion(solicitud, self.admin)

        # 2. Cambio en ticket (Asignación + En Proceso + Atención)
        ticket = crear_ticket(self.solicitante, "Error de red", "Sin conexión cableada")
        asignar_ticket(
            id_ticket=ticket.pk,
            administrador=self.admin,
            id_tecnico_asignado=self.tecnico.pk,
            motivo="Asignación inicial a soporte",
        )
        estado_en_proceso = EstadoTicket.objects.get(nombre=ESTADO_TICKET_EN_PROCESO)
        cambiar_estado_ticket(
            id_ticket=ticket.pk,
            id_estado_ticket=estado_en_proceso.pk,
            tecnico=self.tecnico,
            mensaje="Se inicia diagnóstico de red",
        )
        registrar_atencion_ticket(
            id_ticket=ticket.pk,
            tecnico=self.tecnico,
            mensaje="Se revisa punto de red en puesto de trabajo",
        )

        # 1 aviso de solicitud + 3 avisos de ticket (asignación, cambio de estado, atención) = 4 pendientes
        self.assertEqual(contar_notificaciones_pendientes(self.solicitante), 4)

        # Verificar indicador numérico en la barra superior a través de distintas páginas del portal
        for url in (
            reverse("inicio"),
            reverse("usuarios:mis_equipos"),
            reverse("asignaciones_web:solicitar"),
            reverse("tickets_web:seguimiento"),
            reverse("usuarios:perfil"),
            reverse("usuarios:notificaciones"),
        ):
            resp = web.get(url)
            self.assertEqual(resp.status_code, 200, f"Fallo al cargar {url}")
            html = resp.content.decode("utf-8")
            self.assertIn('id="top-notificaciones-link"', html)
            self.assertIn('id="top-notificaciones-contador"', html)
            self.assertIn('data-pendientes="4"', html)
            self.assertNotIn("Notificaciones (próximamente)", html)

    def test_criterio_2_lectura_detalle_marca_leido_persiste_y_reduce_contador_idempotente(self):
        """CA2: Al abrir un aviso pendiente desde la bandeja (título o Ver detalle), se marca leído via POST+CSRF, baja el contador y muestra el mensaje completo."""
        solicitud = self.crear_solicitud()
        aprobar_solicitud_asignacion(solicitud, self.admin)
        aviso_solicitud = Notificacion.objects.get()

        ticket = crear_ticket(self.solicitante, "Pantalla parpadea", "Falla intermitente")
        with transaction.atomic():
            aviso_ticket = notificar_actualizacion_ticket(
                ticket,
                id_evento="evento-lectura-1",
                detalle="Diagnóstico de pantalla en curso por soporte técnico.",
            )

        web = self.cliente(self.solicitante)
        self.assertEqual(contar_notificaciones_pendientes(self.solicitante), 2)

        # La bandeja usa formularios POST con CSRF hacia marcar_notificacion_leida tanto en el título como en «Ver detalle»
        r_bandeja = web.get(reverse("usuarios:notificaciones"))
        self.assertEqual(r_bandeja.status_code, 200)
        html_bandeja = r_bandeja.content.decode("utf-8")
        url_leer_ticket = reverse("usuarios:marcar_notificacion_leida", args=[aviso_ticket.pk])
        url_detalle_ticket = reverse("usuarios:detalle_notificacion", args=[aviso_ticket.pk])
        self.assertIn(f'action="{url_leer_ticket}"', html_bandeja)
        self.assertIn(f'class="notificacion-titulo-btn">{aviso_ticket.titulo}</button>', html_bandeja)
        self.assertIn(">Ver detalle</button>", html_bandeja)
        self.assertNotIn(f'href="{url_detalle_ticket}"', html_bandeja)

        # GET directo al detalle mantiene las consultas GET sin modificaciones de datos
        r_detalle_get = web.get(url_detalle_ticket)
        self.assertEqual(r_detalle_get.status_code, 200)
        self.assertIn("Diagnóstico de pantalla en curso por soporte técnico.", r_detalle_get.content.decode("utf-8"))
        aviso_ticket.refresh_from_db()
        self.assertFalse(aviso_ticket.leida)
        self.assertEqual(contar_notificaciones_pendientes(self.solicitante), 2)

        # Abrir el aviso desde la bandeja (POST a marcar_notificacion_leida) persiste leida=True, reduce el contador de 2 a 1 y redirige al detalle con el mensaje completo
        r_abrir_detalle = web.post(url_leer_ticket)
        self.assertRedirects(r_abrir_detalle, url_detalle_ticket)
        aviso_ticket.refresh_from_db()
        self.assertTrue(aviso_ticket.leida)
        self.assertEqual(contar_notificaciones_pendientes(self.solicitante), 1)

        r_detalle_leido = web.get(url_detalle_ticket)
        html_post = r_detalle_leido.content.decode("utf-8")
        self.assertIn("Diagnóstico de pantalla en curso por soporte técnico.", html_post)
        self.assertIn('data-pendientes="1"', html_post)
        self.assertIn("Leída", html_post)

        # Repetir POST sobre el mismo aviso es idempotente y nunca vuelve negativo el contador
        web.post(url_leer_ticket)
        self.assertEqual(contar_notificaciones_pendientes(self.solicitante), 1)

        # Abrir el segundo aviso desde la bandeja deja el contador en 0 y muestra su detalle completo
        url_leer_solicitud = reverse("usuarios:marcar_notificacion_leida", args=[aviso_solicitud.pk])
        url_detalle_solicitud = reverse("usuarios:detalle_notificacion", args=[aviso_solicitud.pk])
        r_abrir_segundo = web.post(url_leer_solicitud, follow=True)
        self.assertRedirects(r_abrir_segundo, url_detalle_solicitud)
        self.assertIn(aviso_solicitud.mensaje, r_abrir_segundo.content.decode("utf-8"))
        self.assertEqual(contar_notificaciones_pendientes(self.solicitante), 0)
        web.post(url_leer_solicitud)
        self.assertEqual(contar_notificaciones_pendientes(self.solicitante), 0)

    def test_criterio_3_bandeja_sin_pendientes_muestra_mensaje_exacto(self):
        """CA3: Si no hay avisos pendientes, debe mostrarse exactamente el texto requerido."""
        texto_exacto = "No tienes notificaciones pendientes en este momento"
        web = self.cliente(self.solicitante)

        # Caso A: Bandeja completamente vacía
        r_vacia = web.get(reverse("usuarios:notificaciones"))
        self.assertEqual(r_vacia.status_code, 200)
        self.assertIn(texto_exacto, r_vacia.content.decode("utf-8"))

        # Caso B: Con un aviso pendiente no se muestra el mensaje de bandeja sin pendientes
        solicitud = self.crear_solicitud()
        aprobar_solicitud_asignacion(solicitud, self.admin)
        aviso = Notificacion.objects.get()
        r_con_pendiente = web.get(reverse("usuarios:notificaciones"))
        self.assertNotIn(texto_exacto, r_con_pendiente.content.decode("utf-8"))

        # Caso C: Una vez leído el aviso, vuelve a mostrarse el mensaje exacto
        web.post(reverse("usuarios:marcar_notificacion_leida", args=[aviso.pk]))
        r_leida = web.get(reverse("usuarios:notificaciones"))
        self.assertEqual(r_leida.status_code, 200)
        self.assertIn(texto_exacto, r_leida.content.decode("utf-8"))

    def test_criterio_4_abrir_aviso_solicitud_aprobada_redirige_a_detalle_solicitud(self):
        """CA4: Al abrir un aviso de solicitud aprobada, redirige a la vista de detalle de esa solicitud."""
        solicitud = self.crear_solicitud()
        aprobar_solicitud_asignacion(solicitud, self.admin)
        aviso = Notificacion.objects.get()

        web = self.cliente(self.solicitante)
        r_abrir = web.post(reverse("usuarios:abrir_notificacion", args=[aviso.pk]))
        url_esperada = reverse("asignaciones_web:detalle", args=[solicitud.pk])
        self.assertRedirects(r_abrir, url_esperada)
        self.assertNotIn("/confirmacion/", r_abrir["Location"])

        aviso.refresh_from_db()
        self.assertTrue(aviso.leida)
        self.assertEqual(contar_notificaciones_pendientes(self.solicitante), 0)

        r_destino = web.get(url_esperada)
        self.assertEqual(r_destino.status_code, 200)
        html_destino = r_destino.content.decode("utf-8")
        self.assertIn("Coordina con el área de soporte la entrega del equipo", html_destino)

    def test_entrega_y_devolucion_crean_avisos_internos_sin_duplicados_y_redirigen_a_equipo(self):
        """Entrega y devolución generan avisos de canal PLATAFORMA con clave estable y navegación a mis-equipos."""
        activo = self.activo()
        solicitud = crear_solicitud_asignacion(self.solicitante, self.categoria.pk, "Uso diario")
        aprobar_solicitud_asignacion(solicitud, self.admin)

        asignacion = registrar_entrega_asignacion(solicitud, activo.pk, self.tecnico)
        aviso_entrega = Notificacion.objects.get(titulo__startswith="Equipo entregado:")
        self.assertEqual(aviso_entrega.canal, CANAL_PLATAFORMA)
        self.assertEqual(aviso_entrega.estado_envio, "NO_APLICA")
        self.assertFalse(aviso_entrega.reintento_permitido)
        self.assertEqual(aviso_entrega.datos_envio, {})
        self.assertEqual(aviso_entrega.referencia, {"tipo": "asignacion", "id": asignacion.pk})
        self.assertIn(activo.codigo_inventario, aviso_entrega.mensaje)

        # Idempotencia por clave_evento
        with transaction.atomic():
            duplicado = notificar_entrega_asignacion(asignacion)
        self.assertEqual(duplicado.pk, aviso_entrega.pk)

        # Devolución con falla técnica genera aviso interno e incluye el código del ticket si aplica
        registrar_devolucion_asignacion(
            asignacion,
            self.tecnico,
            "Con falla técnica",
            "Bisagra suelta",
        )
        ticket_revision = Ticket.objects.get(id_activo=activo)
        aviso_devolucion = Notificacion.objects.get(titulo__startswith="Devolución registrada:")
        self.assertEqual(aviso_devolucion.canal, CANAL_PLATAFORMA)
        self.assertEqual(aviso_devolucion.estado_envio, "NO_APLICA")
        self.assertEqual(aviso_devolucion.referencia, {"tipo": "asignacion", "id": asignacion.pk})
        self.assertIn("Con falla técnica", aviso_devolucion.mensaje)
        self.assertIn(ticket_revision.codigo_ticket, aviso_devolucion.mensaje)

        # Abrir el aviso de entrega o devolución redirige al detalle del equipo en el portal
        web = self.cliente(self.solicitante)
        r_abrir = web.post(reverse("usuarios:abrir_notificacion", args=[aviso_entrega.pk]))
        self.assertRedirects(
            r_abrir,
            reverse("usuarios:detalle_equipo", args=[asignacion.pk]),
        )

    def test_recordatorios_existentes_compatibles_con_avisos_de_entrega_y_excluidos_de_bandeja(self):
        """Los recordatorios quedan en CORREO_API, no aparecen en bandeja y no colisionan con avisos de entrega."""
        _, asignacion_id = self.entregar()
        asignacion = Asignacion.objects.get(pk=asignacion_id)
        asignacion.fecha_devolucion_prevista = timezone.now() + timedelta(hours=12)
        asignacion.save(update_fields=["fecha_devolucion_prevista"])

        # Existe el aviso de entrega en PLATAFORMA; procesar_pendientes no debe fallar ni cancelarlo
        aviso_entrega = Notificacion.objects.get(titulo__startswith="Equipo entregado:")
        self.assertEqual(generar_recordatorios(), 1)
        recordatorio = Notificacion.objects.get(canal=CANAL_CORREO_API)

        # El recordatorio de solo correo no se cuenta ni aparece en la bandeja del portal
        web = self.cliente(self.solicitante)
        r_bandeja = web.get(reverse("usuarios:notificaciones"))
        self.assertNotIn("Recordatorio de devolución", r_bandeja.content.decode("utf-8"))
        r_detalle_correo = web.get(reverse("usuarios:detalle_notificacion", args=[recordatorio.pk]))
        self.assertEqual(r_detalle_correo.status_code, 404)

        # El despacho de correos procesa la aprobación (AMBOS) y el recordatorio (CORREO_API) sin tocar el aviso de entrega
        enviados = procesar_pendientes()
        self.assertEqual(enviados, 2)
        aviso_entrega.refresh_from_db()
        self.assertEqual(aviso_entrega.estado_envio, "NO_APLICA")
        recordatorio.refresh_from_db()
        self.assertEqual(recordatorio.estado_envio, "ENVIADA")

    def test_aviso_ambos_visible_aunque_falle_resend_y_lectura_no_altera_cola_de_correo(self):
        """Una falla de Resend no oculta el aviso interno; marcarlo como leído no altera el envío de correo."""
        solicitud = self.crear_solicitud()
        aprobar_solicitud_asignacion(solicitud, self.admin)
        aviso = Notificacion.objects.get()
        self.assertEqual(aviso.canal, CANAL_AMBOS)

        # Simular fallo 503 de Resend
        self.http.return_value.status_code = 503
        despachar_notificacion(aviso.pk)
        aviso.refresh_from_db()
        self.assertEqual(aviso.estado_envio, "ERROR")
        self.assertEqual(aviso.intentos_envio, 1)
        self.assertTrue(aviso.reintento_permitido)

        # El aviso sigue visible en la bandeja del portal y el contador es 1
        web = self.cliente(self.solicitante)
        r_bandeja = web.get(reverse("usuarios:notificaciones"))
        self.assertEqual(r_bandeja.status_code, 200)
        self.assertIn(aviso.titulo, r_bandeja.content.decode("utf-8"))
        self.assertEqual(contar_notificaciones_pendientes(self.solicitante), 1)

        # Marcar como leído en plataforma no cambia estado_envio, intentos_envio, datos_envio ni dispara HTTP
        self.http.reset_mock()
        web.post(reverse("usuarios:marcar_notificacion_leida", args=[aviso.pk]))
        self.http.assert_not_called()
        aviso.refresh_from_db()
        self.assertTrue(aviso.leida)
        self.assertEqual(aviso.estado_envio, "ERROR")
        self.assertEqual(aviso.intentos_envio, 1)
        self.assertTrue(aviso.reintento_permitido)

    def test_seguridad_aislamiento_usuario_roles_csrf_y_escapado_xss(self):
        """Verifica acceso anónimo, rol no autorizado, aviso ajeno, protección CSRF/POST y escapado HTML."""
        solicitud_ajena = self.crear_solicitud(usuario=self.otro)
        rechazar_solicitud_asignacion(
            solicitud_ajena,
            self.admin,
            '<script>alert("xss")</script>',
        )
        aviso_ajeno = Notificacion.objects.get(id_usuario=self.otro)

        # 1. Acceso anónimo -> 403
        anon = Client()
        self.assertEqual(anon.get(reverse("usuarios:notificaciones")).status_code, 403)
        self.assertEqual(anon.get(reverse("usuarios:detalle_notificacion", args=[aviso_ajeno.pk])).status_code, 403)
        self.assertEqual(anon.post(reverse("usuarios:marcar_notificacion_leida", args=[aviso_ajeno.pk])).status_code, 403)

        # 2. Rol no autorizado (Técnico sin rol Usuario solicitante) -> 403
        web_tecnico = self.cliente(self.tecnico)
        self.assertEqual(web_tecnico.get(reverse("usuarios:notificaciones")).status_code, 403)

        # 3. Solicitante autenticado no ve ni puede operar avisos de otro usuario -> 404
        web_propio = self.cliente(self.solicitante)
        self.assertEqual(contar_notificaciones_pendientes(self.solicitante), 0)
        r_bandeja_propia = web_propio.get(reverse("usuarios:notificaciones"))
        self.assertNotIn(aviso_ajeno.titulo, r_bandeja_propia.content.decode("utf-8"))
        self.assertEqual(
            web_propio.get(reverse("usuarios:detalle_notificacion", args=[aviso_ajeno.pk])).status_code,
            404,
        )
        self.assertEqual(
            web_propio.post(reverse("usuarios:marcar_notificacion_leida", args=[aviso_ajeno.pk])).status_code,
            404,
        )
        self.assertEqual(
            web_propio.post(reverse("usuarios:abrir_notificacion", args=[aviso_ajeno.pk])).status_code,
            404,
        )
        aviso_ajeno.refresh_from_db()
        self.assertFalse(aviso_ajeno.leida)

        # 4. Peticiones GET a endpoints de lectura/apertura rechazan mutación con 405
        web_otro = self.cliente(self.otro)
        self.assertEqual(
            web_otro.get(reverse("usuarios:marcar_notificacion_leida", args=[aviso_ajeno.pk])).status_code,
            405,
        )
        self.assertEqual(
            web_otro.get(reverse("usuarios:abrir_notificacion", args=[aviso_ajeno.pk])).status_code,
            405,
        )
        aviso_ajeno.refresh_from_db()
        self.assertFalse(aviso_ajeno.leida)

        # 5. Protección CSRF activa en POST y no redirige a URLs externas enviadas por el cliente
        csrf_client = self.cliente(self.otro, csrf=True)
        r_sin_csrf = csrf_client.post(reverse("usuarios:marcar_notificacion_leida", args=[aviso_ajeno.pk]))
        self.assertEqual(r_sin_csrf.status_code, 403)

        # 6. Escapado XSS y no exposición de datos internos (datos_envio, ultimo_error, destinatarios)
        aviso_ajeno.ultimo_error = "ERROR_INTERNO_PROVEEDOR_SECRETO"
        aviso_ajeno.save(update_fields=["ultimo_error"])
        r_detalle_otro = web_otro.get(reverse("usuarios:detalle_notificacion", args=[aviso_ajeno.pk]))
        html_otro = r_detalle_otro.content.decode("utf-8")
        self.assertIn('&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;', html_otro)
        self.assertNotIn('<script>alert("xss")</script>', html_otro)
        self.assertNotIn("ERROR_INTERNO_PROVEEDOR_SECRETO", html_otro)
        self.assertNotIn("notificaciones@example.org", html_otro)

        # Ignora parámetros next/url maliciosos del cliente
        r_abrir_seguro = web_otro.post(
            reverse("usuarios:abrir_notificacion", args=[aviso_ajeno.pk]) + "?next=https://malicioso.example.org",
            {"next": "https://malicioso.example.org", "url": "https://malicioso.example.org"},
        )
        self.assertRedirects(
            r_abrir_seguro,
            reverse("asignaciones_web:detalle", args=[solicitud_ajena.pk]),
        )

    def test_recurso_no_disponible_o_ajeno_no_genera_error_ni_expone_enlace(self):
        """Si la referencia apunta a un recurso inexistente o ajeno, muestra el aviso sin romper ni redirigir fuera."""
        with transaction.atomic():
            aviso_inexistente = registrar_notificacion(
                usuario=self.solicitante,
                evento="solicitud:999999:resolucion",
                titulo="Solicitud histórica",
                mensaje="Aviso cuyo recurso ya no está disponible.",
                referencia={"tipo": "solicitud", "id": 999999},
                canal=CANAL_PLATAFORMA,
            )

        web = self.cliente(self.solicitante)
        r_detalle = web.get(reverse("usuarios:detalle_notificacion", args=[aviso_inexistente.pk]))
        self.assertEqual(r_detalle.status_code, 200)
        self.assertNotIn("Ver solicitud #999999", r_detalle.content.decode("utf-8"))

        r_abrir = web.post(reverse("usuarios:abrir_notificacion", args=[aviso_inexistente.pk]))
        self.assertRedirects(
            r_abrir,
            reverse("usuarios:detalle_notificacion", args=[aviso_inexistente.pk]),
        )
        aviso_inexistente.refresh_from_db()
        self.assertTrue(aviso_inexistente.leida)
