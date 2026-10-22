"""Prueba explícita, aislada de solicitudes reales y con destinatario indicado."""

from uuid import uuid4

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from notificaciones.resend_client import ErrorCorreo, enviar_correo


class Command(BaseCommand):
    help = "Envía un único correo de prueba al destinatario indicado; nunca muestra la clave."

    def add_arguments(self, parser):
        parser.add_argument("--destinatario", required=True)

    def handle(self, *args, **options):
        try:
            identificador = enviar_correo(
                {
                    "from": settings.RESEND_FROM_EMAIL,
                    "to": [options["destinatario"]],
                    "subject": "SIGET — Prueba de notificaciones",
                    "text": "Este es un mensaje de prueba de SIGET. La integración con Resend está enviando correos correctamente.",
                    "html": "<p>Este es un mensaje de prueba de <strong>SIGET</strong>.</p><p>La integración con Resend está enviando correos correctamente.</p>",
                },
                f"siget/prueba/{uuid4()}",
            )
        except ErrorCorreo as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write(self.style.SUCCESS(f"Correo aceptado por Resend. Identificador: {identificador}"))
