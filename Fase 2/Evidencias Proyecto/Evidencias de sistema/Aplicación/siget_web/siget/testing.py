"""Inicializa el DDL administrado fuera de Django solamente en bases de pruebas."""
from pathlib import Path
import os
from django.conf import settings
from django.db import connection
from django.test.runner import DiscoverRunner


def cargar_esquema_pruebas():
    if not str(connection.settings_dict["NAME"]).startswith("test_"):
        raise RuntimeError("El DDL de pruebas solo puede ejecutarse en una base test_.")
    ubicaciones = [
        Path(os.environ.get("SIGET_DDL_PATH") or str(settings.BASE_DIR / "schema/init_siget_bd.sql")),
        settings.BASE_DIR.parent.parent / "Base de datos/init_siget_bd.sql",
    ]
    archivo = next((p for p in ubicaciones if p.is_file()), None)
    if archivo is None:
        raise RuntimeError("Falta init_siget_bd.sql. Verifique el montaje schema/ o SIGET_DDL_PATH.")
    with connection.cursor() as cursor:
        cursor.execute(archivo.read_text())


class PostgreSQLTestRunner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        nombre = settings.DATABASES["default"]["TEST"]["NAME"]
        if not str(nombre).startswith("test_"):
            raise RuntimeError("POSTGRES_TEST_DB debe comenzar con test_.")
        configuracion = super().setup_databases(**kwargs)
        try:
            cargar_esquema_pruebas()
        except Exception:
            self.teardown_databases(configuracion)
            raise
        return configuracion
