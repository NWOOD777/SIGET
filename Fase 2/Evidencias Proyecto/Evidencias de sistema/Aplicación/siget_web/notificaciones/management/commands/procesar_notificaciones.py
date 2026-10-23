import time

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, close_old_connections
from psycopg import Error as PsycopgError

from notificaciones.senales import escuchar_correos, esperar_aviso
from notificaciones.services import generar_recordatorios, procesar_pendientes


class Command(BaseCommand):
    help = "Genera recordatorios y despacha correos; --continuo escucha avisos nuevos al confirmar su operación."

    def add_arguments(self, parser):
        parser.add_argument("--continuo", action="store_true")
        parser.add_argument(
            "--intervalo", type=int, default=60,
            help="Segundos entre barridos de respaldo y generación de recordatorios; los avisos nuevos despiertan el proceso antes.",
        )
        parser.add_argument("--limite", type=int, default=100)
        parser.add_argument("--sin-recordatorios", action="store_true")

    def _procesar_ciclo(self, options, *, revisar_recordatorios):
        try:
            recordatorios = 0
            if revisar_recordatorios and not options["sin_recordatorios"]:
                recordatorios = generar_recordatorios()
            procesados = procesar_pendientes(limite=options["limite"])
            if revisar_recordatorios or procesados:
                self.stdout.write(f"Recordatorios nuevos: {recordatorios}; intentos procesados: {procesados}.")
            return procesados
        finally:
            close_old_connections()

    def handle(self, *args, **options):
        if options["intervalo"] < 1 or options["limite"] < 1:
            raise CommandError("Intervalo y límite deben ser positivos.")
        if settings.RESEND_TIMEOUT_SECONDS <= 0 or not 1 <= settings.RESEND_MAX_ATTEMPTS <= 20 or settings.RESEND_RETRY_SECONDS < 1:
            raise CommandError("Configuración inválida de timeout, máximo de intentos o espera.")
        call_command("preparar_notificaciones", verbosity=0)
        if not options["continuo"]:
            try:
                self._procesar_ciclo(options, revisar_recordatorios=True)
            except DatabaseError:
                raise CommandError("Error de base de datos al procesar notificaciones.") from None
            return

        while True:
            try:
                # Escuchar primero evita perder avisos entre el barrido inicial y la espera.
                with escuchar_correos() as escucha:
                    siguiente_revision = time.monotonic()
                    while True:
                        revisar = time.monotonic() >= siguiente_revision
                        if revisar:
                            siguiente_revision = time.monotonic() + options["intervalo"]
                        procesados = self._procesar_ciclo(options, revisar_recordatorios=revisar)
                        if procesados >= options["limite"]:
                            continue
                        esperar_aviso(escucha, siguiente_revision - time.monotonic())
            except (DatabaseError, PsycopgError) as exc:
                close_old_connections()
                self.stderr.write(f"Ciclo no completado: {type(exc).__name__}. Se reconectará para recuperar los pendientes.")
                time.sleep(min(options["intervalo"], 5))
