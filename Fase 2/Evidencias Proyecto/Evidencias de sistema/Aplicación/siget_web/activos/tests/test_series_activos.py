"""Validación de números de serie al registrar y modificar activos."""
from unittest.mock import patch

from django.test import SimpleTestCase

from activos.serializers import ActivoSerializer


class SeriesActivosTests(SimpleTestCase):
    def test_rechaza_espacios_sin_recortarlos_en_post_put_y_patch(self):
        for texto in ("notebook ultra cara", " SN123", "SN123 ", "SN\t123", "SN\n123", "SN\r123", "SN\u00a0123", "SN\u2003123", "***", "SN[123]", "SN;123", "SN\"123", "SN,123", "SN--123", "-SN123", "SN123-", "SN\u200b123"):
            for parcial in (False, True):
                with self.subTest(texto=repr(texto), parcial=parcial):
                    serializer = ActivoSerializer(data={"numero_serie": texto}, partial=parcial)
                    with patch("rest_framework.validators.UniqueValidator.__call__"):
                        self.assertFalse(serializer.is_valid())
                    errores = serializer.errors
                    assert isinstance(errores, dict)
                    self.assertIn("espacios", str(errores["numero_serie"]))

    def test_series_validas_conservan_el_valor(self):
        for texto in ("949423442", "PG01GTB2", "SN-LNV-2026-9988", "aB12_34/56.78"):
            with self.subTest(texto=texto):
                serializer = ActivoSerializer(data={"numero_serie": texto}, partial=True)
                with patch("rest_framework.validators.UniqueValidator.__call__"):
                    self.assertTrue(serializer.is_valid(), serializer.errors)
                datos = serializer.validated_data
                assert isinstance(datos, dict)
                self.assertEqual(datos["numero_serie"], texto)

    def test_patch_sin_serie_no_reescribe_el_identificador(self):
        serializer = ActivoSerializer(data={}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        datos = serializer.validated_data
        assert isinstance(datos, dict)
        self.assertNotIn("numero_serie", datos)

    def test_valor_cero_admitido_y_negativo_rechazado(self):
        for valor, valido in (("0", True), ("0.00", True), ("750000", True), ("-1", False)):
            with self.subTest(valor=valor):
                serializer = ActivoSerializer(data={"valor_adquisicion": valor}, partial=True)
                self.assertEqual(serializer.is_valid(), valido, serializer.errors)
                if not valido:
                    self.assertIn("valor_adquisicion", serializer.errors)

    def test_limite_de_cien_caracteres_no_se_recorta(self):
        for cantidad in (100, 101):
            serializer = ActivoSerializer(data={"numero_serie": "A" * cantidad}, partial=True)
            with patch("rest_framework.validators.UniqueValidator.__call__"):
                self.assertEqual(serializer.is_valid(), cantidad == 100)
