from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    help = "Amplía notificacion de forma aditiva e idempotente; conserva los datos."

    def handle(self, *args, **options):
        sql = (Path(__file__).resolve().parents[2] / "schema.sql").read_text()
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s, %s)", [71023, 0])
            cursor.execute(sql)
        self.stdout.write(self.style.SUCCESS("Esquema de notificaciones preparado; datos conservados."))
