"""Respaldo PostgreSQL de los datos y estructura de SIGET."""
import os
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


def entorno_postgresql():
    conexion = settings.DATABASES["default"]
    entorno = os.environ.copy()
    entorno.update({
        "PGHOST": str(conexion["HOST"]), "PGPORT": str(conexion["PORT"]),
        "PGDATABASE": str(conexion["NAME"]), "PGUSER": str(conexion["USER"]),
        "PGPASSWORD": str(conexion["PASSWORD"]),
    })
    return entorno


class Command(BaseCommand):
    help = "Guarda la estructura y los datos de SIGET en formato PostgreSQL custom."

    def add_arguments(self, parser):
        parser.add_argument("--salida", required=True, type=Path)

    def handle(self, *args, **options):
        destino = options["salida"].expanduser().resolve()
        destino.parent.mkdir(parents=True, exist_ok=True)
        try:
            with destino.open("xb") as archivo:
                destino.chmod(0o600)
                try:
                    subprocess.run(
                        ["pg_dump", "--format=custom", "--no-owner", "--no-privileges",
                         "--exclude-table-data=public.django_session"],
                        env=entorno_postgresql(), stdout=archivo, stderr=subprocess.PIPE, check=True,
                    )
                except (OSError, subprocess.CalledProcessError) as error:
                    destino.unlink(missing_ok=True)
                    raise CommandError("No se pudo generar el respaldo. Compruebe PostgreSQL y pg_dump.") from error
        except FileExistsError as error:
            raise CommandError("El archivo de destino ya existe. Utilice otro nombre.") from error
        self.stdout.write(self.style.SUCCESS(f"Respaldo guardado en {destino}"))
