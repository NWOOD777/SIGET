from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from notificaciones.models import Notificacion
from notificaciones.services import despachar_notificacion


class Command(BaseCommand):
    help = "Rehabilita un aviso tras corregir configuración, sin reiniciar el contador o la idempotencia."

    def add_arguments(self, parser):
        parser.add_argument("id_notificacion", type=int)

    def handle(self, *args, **options):
        from django.conf import settings

        with transaction.atomic():
            n = Notificacion.objects.select_for_update().filter(pk=options["id_notificacion"]).first()
            if not n or n.estado_envio != "ERROR":
                raise CommandError("Solo se puede reintentar una notificación existente en ERROR.")
            if n.intentos_envio >= settings.RESEND_MAX_ATTEMPTS or (
                n.fecha_primer_intento and timezone.now() - n.fecha_primer_intento >= timedelta(hours=23)
            ):
                raise CommandError("Límite de intentos o ventana segura agotados; revisar el resultado en Resend antes de cualquier nuevo envío.")
            n.reintento_permitido = True
            n.proximo_intento = timezone.now()
            n.save(update_fields=["reintento_permitido", "proximo_intento"])
        despachar_notificacion(n.pk)
        n.refresh_from_db()
        self.stdout.write(f"Notificación {n.pk}: {n.estado_envio}.")
