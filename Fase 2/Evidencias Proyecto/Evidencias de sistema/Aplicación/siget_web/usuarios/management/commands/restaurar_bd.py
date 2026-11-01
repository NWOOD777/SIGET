"""Recuperación transaccional de un respaldo de SIGET."""
import subprocess
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from usuarios.management.commands.respaldo_bd import entorno_postgresql


class Command(BaseCommand):
    help = "Restaura un respaldo PostgreSQL custom sobre la base configurada."

    def add_arguments(self, parser):
        parser.add_argument("--archivo", required=True, type=Path)
        parser.add_argument("--confirmar", action="store_true")

    def handle(self, *args, **options):
        if not options["confirmar"]:
            raise CommandError("La restauración reemplaza los datos. Repita con --confirmar en el entorno elegido.")
        origen = options["archivo"].expanduser().resolve()
        if not origen.is_file():
            raise CommandError("No se encontró el archivo de respaldo.")
        entorno = entorno_postgresql()
        try:
            subprocess.run(
                ["pg_restore", "--dbname=" + entorno["PGDATABASE"], "--clean", "--if-exists",
                 "--no-owner", "--no-privileges", "--single-transaction", "--exit-on-error", str(origen)],
                env=entorno, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            raise CommandError("No se pudo restaurar la base. La operación se revirtió; revise la conexión y el respaldo.") from error
        self.stdout.write(self.style.SUCCESS("Base restaurada correctamente. Inicie sesión nuevamente en SIGET."))
