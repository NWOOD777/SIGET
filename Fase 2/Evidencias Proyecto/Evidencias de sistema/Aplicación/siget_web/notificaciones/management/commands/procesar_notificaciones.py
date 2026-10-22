import time

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, close_old_connections

from notificaciones.services import generar_recordatorios, procesar_pendientes


class Command(BaseCommand):
    help = "Genera recordatorios y despacha correos; --continuo ejecuta el proceso programado."

    def add_arguments(self, parser):
        parser.add_argument("--continuo", action="store_true")
        parser.add_argument("--intervalo", type=int, default=60)
        parser.add_argument("--limite", type=int, default=100)
        parser.add_argument("--sin-recordatorios", action="store_true")

    def handle(self, *args, **options):
        if options["intervalo"] < 1 or options["limite"] < 1:
            raise CommandError("Intervalo y límite deben ser positivos.")
        if settings.RESEND_TIMEOUT_SECONDS <= 0 or not 1 <= settings.RESEND_MAX_ATTEMPTS <= 20 or settings.RESEND_RETRY_SECONDS < 1:
            raise CommandError("Configuración inválida de timeout, máximo de intentos o espera.")
        call_command("preparar_notificaciones", verbosity=0)
        while True:
            try:
                recordatorios = 0 if options["sin_recordatorios"] else generar_recordatorios()
                procesados = procesar_pendientes(limite=options["limite"])
                self.stdout.write(f"Recordatorios nuevos: {recordatorios}; intentos procesados: {procesados}.")
            except DatabaseError as exc:
                if not options["continuo"]:
                    raise CommandError("Error de base de datos al procesar notificaciones.") from None
                self.stderr.write(f"Ciclo no completado: {type(exc).__name__}. Se reintentará.")
            finally:
                close_old_connections()
            if not options["continuo"]:
                return
            time.sleep(options["intervalo"])
