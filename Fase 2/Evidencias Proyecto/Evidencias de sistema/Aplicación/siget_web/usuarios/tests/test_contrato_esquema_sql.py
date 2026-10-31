"""Coherencia entre el SQL de instalación, los modelos y las actualizaciones."""
from django.apps import apps
from django.db import connection
from django.urls import reverse

from repuestos.models import Repuesto
from usuarios.models import RolPermiso
from usuarios.tests.test_integracion_postgresql import PostgreSQLTestBase


class ContratoEsquemaSQLTests(PostgreSQLTestBase):
    def test_las_tablas_y_columnas_de_los_modelos_existen_en_el_sql_base(self):
        with connection.cursor() as cursor:
            tablas = set(connection.introspection.table_names(cursor))
            for modelo in apps.get_models():
                if modelo._meta.managed or modelo._meta.proxy:
                    continue
                tabla = modelo._meta.db_table
                with self.subTest(tabla=tabla):
                    self.assertIn(tabla, tablas)
                    columnas = {campo.name for campo in connection.introspection.get_table_description(cursor, tabla)}
                    esperadas = {campo.column for campo in modelo._meta.local_fields}
                    self.assertFalse(esperadas - columnas, f"Faltan columnas de {tabla}: {esperadas - columnas}")

    def test_repuesto_se_crea_habilitado_desde_el_esquema_inicial(self):
        repuesto = Repuesto.objects.create(codigo_repuesto="REP-QA", nombre="Repuesto de prueba", stock_actual=7)
        repuesto.refresh_from_db()
        self.assertTrue(repuesto.activo)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT column_default, is_nullable FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'repuesto' AND column_name = 'activo'"
            )
            self.assertEqual(cursor.fetchone(), ("true", "NO"))


    def test_instalacion_habilita_reportes_solo_al_administrador(self):
        roles = set(
            RolPermiso.objects.filter(permiso__codigo="REPORTES_CONSULTAR")
            .values_list("rol__nombre", flat=True)
        )
        self.assertEqual(roles, {"Administrador del sistema"})

        filtros = {"fecha_inicio": "2026-10-01", "fecha_fin": "2026-10-31"}
        for nombre in ("dashboard-reportes", "reporte-parque-ti"):
            for usuario, esperado in (
                (self.admin, 200),
                (self.tecnico, 403),
                (self.solicitante, 403),
            ):
                with self.subTest(reporte=nombre, usuario=usuario.pk):
                    respuesta = self.cliente(usuario).get(reverse(nombre), filtros)
                    self.assertEqual(respuesta.status_code, esperado, respuesta.data)

        RolPermiso.objects.filter(permiso__codigo="REPORTES_CONSULTAR").delete()
        for nombre in ("dashboard-reportes", "reporte-parque-ti"):
            with self.subTest(reporte=nombre, permiso_retirado=True):
                respuesta = self.cliente(self.admin).get(reverse(nombre), filtros)
                self.assertEqual(respuesta.status_code, 403, respuesta.data)
