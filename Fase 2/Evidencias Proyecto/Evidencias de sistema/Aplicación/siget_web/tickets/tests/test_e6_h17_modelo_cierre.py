"""Pruebas sin PostgreSQL; no ejecutan el SQL de instalación pendiente."""
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.test import SimpleTestCase

from ordenes_trabajo.cierre_serializers import CierreTecnicoEntradaSerializer
from ordenes_trabajo.models import CierreTecnico, OrdenTrabajo
from ordenes_trabajo.validaciones_cierre import validar_contenido_cierre
from usuarios.models import Usuario


class CierreTecnicoContenidoTests(SimpleTestCase):
    def test_reparacion_exitosa(self):
        validar_contenido_cierre(resultado="REPARACION_EXITOSA", solucion_aplicada="Cambio de pieza", pruebas_realizadas="Encendido")

    def test_no_reparable_sin_campos_de_exito(self):
        validar_contenido_cierre(resultado="NO_REPARABLE", informe_descarte="Placa destruida")

    def test_resultados_invalidos(self):
        for resultado in (None, "", "OTRO", [], 1, True):
            with self.subTest(resultado=resultado), self.assertRaises(ValidationError):
                validar_contenido_cierre(resultado=resultado)

    def test_obligatorios_vacios(self):
        for campo in ("solucion_aplicada", "pruebas_realizadas"):
            for valor in (None, "", " \t\n"):
                datos = dict(resultado="REPARACION_EXITOSA", solucion_aplicada="Solución", pruebas_realizadas="Pruebas")
                datos[campo] = valor
                with self.subTest(campo=campo, valor=valor), self.assertRaises(ValidationError):
                    validar_contenido_cierre(**datos)

    def test_informe_obligatorio(self):
        for valor in (None, "", " \t\n"):
            with self.subTest(valor=valor), self.assertRaises(ValidationError):
                validar_contenido_cierre(resultado="NO_REPARABLE", informe_descarte=valor)

    def test_tipos_de_texto(self):
        for valor in (123, True, [], {}):
            with self.subTest(valor=valor), self.assertRaises(ValidationError):
                validar_contenido_cierre(resultado="NO_REPARABLE", informe_descarte=valor)

    def test_serializer_normaliza_y_excluye_actor_fecha(self):
        s = CierreTecnicoEntradaSerializer(data={"resultado": "NO_REPARABLE", "informe_descarte": "  Placa destruida  ", "id_tecnico": 999, "fecha_cierre": "2000-01-01"})
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data, {"resultado": "NO_REPARABLE", "informe_descarte": "Placa destruida"})

    def test_serializer_rechaza_cuerpo_y_textos_invalidos(self):
        for datos in ([], {"resultado": "NO_REPARABLE"}, {"resultado": "NO_REPARABLE", "informe_descarte": 1}, {"resultado": "X" * 33}):
            s = CierreTecnicoEntradaSerializer(data=datos)
            self.assertFalse(s.is_valid())


class CierreTecnicoModeloTests(SimpleTestCase):
    def test_modelo_no_administrado_y_relaciones_protegidas(self):
        self.assertFalse(CierreTecnico._meta.managed)
        self.assertEqual(CierreTecnico._meta.db_table, "cierre_tecnico")
        for nombre, destino in (("id_orden", OrdenTrabajo), ("id_tecnico", Usuario)):
            campo = CierreTecnico._meta.get_field(nombre)
            self.assertIs(campo.remote_field.model, destino)
            self.assertIs(campo.remote_field.on_delete, models.PROTECT)
        self.assertTrue(CierreTecnico._meta.get_field("id_orden").unique)

    def test_fecha_servidor_no_editable(self):
        self.assertIsNotNone(CierreTecnico().fecha_cierre)
        self.assertFalse(CierreTecnico._meta.get_field("fecha_cierre").editable)

    def test_clean_comparte_validaciones(self):
        with self.assertRaises(ValidationError):
            CierreTecnico(resultado="NO_REPARABLE", informe_descarte=" ").clean()

    def test_unicidad_validada_por_django(self):
        cierre = CierreTecnico(id_orden_id=7)
        with patch.object(CierreTecnico._default_manager, "filter") as consulta:
            consulta.return_value.exists.return_value = True
            with self.assertRaises(ValidationError) as error:
                cierre.validate_unique()
        self.assertIn("id_orden", error.exception.message_dict)

    def test_relaciones_inexistentes_rechazadas(self):
        for campo, destino in (("id_orden", OrdenTrabajo), ("id_tecnico", Usuario)):
            with self.subTest(campo=campo), patch.object(destino._base_manager, "using") as consulta:
                consulta.return_value.filter.return_value.complex_filter.return_value.exists.return_value = False
                with self.assertRaises(ValidationError):
                    CierreTecnico._meta.get_field(campo).validate(999, CierreTecnico())

    def test_longitud_resultado(self):
        with self.assertRaises(ValidationError):
            CierreTecnico._meta.get_field("resultado").clean("X" * 33, CierreTecnico())

    def test_sql_aditivo_y_referencia_coinciden(self):
        aditivo = (settings.BASE_DIR / "ordenes_trabajo/sql/e6_h17_cierre_tecnico.sql").read_text(encoding="utf-8")
        referencia = settings.BASE_DIR.parent.parent / "Base de datos/init_siget_bd.sql"
        # En Docker el esquema de referencia se monta en una ruta independiente.
        if not referencia.is_file():
            referencia = Path("/opt/siget/schema/init_siget_bd.sql")
        bloque = aditivo[aditivo.index("CREATE TABLE"):aditivo.index("COMMIT;")]
        self.assertIn(bloque, referencia.read_text(encoding="utf-8"))
        self.assertNotIn("DROP ", aditivo)
        for fragmento in ("PRIMARY KEY", "UNIQUE", "ON DELETE RESTRICT", "ck_cierre_tecnico_resultado", "ck_cierre_tecnico_contenido", "CURRENT_TIMESTAMP"):
            self.assertIn(fragmento, aditivo)
