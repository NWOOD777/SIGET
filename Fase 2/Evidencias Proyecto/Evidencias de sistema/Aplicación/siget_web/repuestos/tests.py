from django.test import SimpleTestCase

from .serializers import IngresoRepuestoSerializer


class IngresoRepuestoSerializerTests(SimpleTestCase):

    def setUp(self):
        self.datos_validos = {
            "nombre": "Memoria RAM DDR4",
            "cantidad": 5,
            "costo_unitario": "15000.00",
        }

    def test_ingreso_valido(self):
        serializer = IngresoRepuestoSerializer(data=self.datos_validos)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_nombre_obligatorio(self):
        datos = self.datos_validos.copy()
        datos.pop("nombre")

        serializer = IngresoRepuestoSerializer(data=datos)

        self.assertFalse(serializer.is_valid())
        self.assertIn("nombre", serializer.errors)

    def test_cantidad_obligatoria(self):
        datos = self.datos_validos.copy()
        datos.pop("cantidad")

        serializer = IngresoRepuestoSerializer(data=datos)

        self.assertFalse(serializer.is_valid())
        self.assertIn("cantidad", serializer.errors)

    def test_cantidad_cero(self):
        datos = self.datos_validos.copy()
        datos["cantidad"] = 0

        serializer = IngresoRepuestoSerializer(data=datos)

        self.assertFalse(serializer.is_valid())
        self.assertIn("cantidad", serializer.errors)

    def test_cantidad_negativa(self):
        datos = self.datos_validos.copy()
        datos["cantidad"] = -3

        serializer = IngresoRepuestoSerializer(data=datos)

        self.assertFalse(serializer.is_valid())
        self.assertIn("cantidad", serializer.errors)

    def test_cantidad_decimal(self):
        datos = self.datos_validos.copy()
        datos["cantidad"] = 2.5

        serializer = IngresoRepuestoSerializer(data=datos)

        self.assertFalse(serializer.is_valid())
        self.assertIn("cantidad", serializer.errors)

    def test_costo_negativo(self):
        datos = self.datos_validos.copy()
        datos["costo_unitario"] = "-1000.00"

        serializer = IngresoRepuestoSerializer(data=datos)

        self.assertFalse(serializer.is_valid())
        self.assertIn("costo_unitario", serializer.errors)

    def test_ingreso_repuesto_existente(self):
        datos = {
            "id_repuesto": 1,
            "cantidad": 3,
            "costo_unitario": "18000.00",
        }

        serializer = IngresoRepuestoSerializer(data=datos)

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_repuesto_existente_no_admite_nombre(self):
        datos = {
            "id_repuesto": 1,
            "nombre": "Memoria RAM",
            "cantidad": 3,
            "costo_unitario": "18000.00",
        }

        serializer = IngresoRepuestoSerializer(data=datos)

        self.assertFalse(serializer.is_valid())
        self.assertIn("nombre", serializer.errors)

    def test_id_repuesto_invalido(self):
        datos = {
            "id_repuesto": -1,
            "cantidad": 3,
            "costo_unitario": "18000.00",
        }

        serializer = IngresoRepuestoSerializer(data=datos)

        self.assertFalse(serializer.is_valid())
        self.assertIn("id_repuesto", serializer.errors)