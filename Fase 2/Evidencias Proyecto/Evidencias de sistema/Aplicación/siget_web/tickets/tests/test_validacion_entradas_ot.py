"""Validación de entrada sin PostgreSQL, con límites de los AutoField existentes."""
from django.test import SimpleTestCase

from ordenes_trabajo.serializers import (
    CrearOrdenTrabajoSerializer, OperacionOTSerializer, PausarOrdenTrabajoSerializer,
    ReasignarOrdenTrabajoSerializer, RutaOrdenTrabajoSerializer,
)


class ValidacionEntradasOTTests(SimpleTestCase):
    def test_identificadores_limites_y_cadenas_ascii_compatibles(self):
        for serializer_class, nombre, base in (
            (CrearOrdenTrabajoSerializer, "id_ticket", {"descripcion_falla": "Falla", "procedimiento_inicial": "Revisión"}),
            (ReasignarOrdenTrabajoSerializer, "id_tecnico_responsable", {"observaciones": "Turno"}),
            (RutaOrdenTrabajoSerializer, "id_orden", {}),
        ):
            for valor in (1, 2147483647, "1", "0001", "2147483647"):
                with self.subTest(serializer=serializer_class.__name__, valor=valor):
                    serializer = serializer_class(data={**base, nombre: valor})
                    self.assertTrue(serializer.is_valid(), serializer.errors)
                    self.assertEqual(serializer.validated_data[nombre], int(valor))
            for valor in (None, True, False, 0, -1, 1.0, 2147483648, "", " ", "1.0", "²", "١", "１", "9"*5000, [], {}):
                with self.subTest(serializer=serializer_class.__name__, valor=str(valor)[:30]):
                    serializer = serializer_class(data={**base, nombre: valor})
                    self.assertFalse(serializer.is_valid())
                    self.assertIn(nombre, serializer.errors)

    def test_textos_obligatorios_estrictos_y_espacios(self):
        casos = (
            (CrearOrdenTrabajoSerializer, "descripcion_falla", {"id_ticket": 1, "procedimiento_inicial": "Revisión"}),
            (CrearOrdenTrabajoSerializer, "procedimiento_inicial", {"id_ticket": 1, "descripcion_falla": "Falla"}),
            (PausarOrdenTrabajoSerializer, "justificacion", {}),
            (ReasignarOrdenTrabajoSerializer, "observaciones", {"id_tecnico_responsable": 1}),
        )
        for clase, campo, base in casos:
            self.assertFalse(clase(data=base).is_valid())
            for valor in (None, "", " \n\t", 1, 1.5, True, False, [], {}, ["texto"]):
                with self.subTest(campo=campo, valor=valor):
                    serializer = clase(data={**base, campo: valor})
                    self.assertFalse(serializer.is_valid())
                    self.assertIn(campo, serializer.errors)
            serializer = clase(data={**base, campo: "  Texto válido  "})
            self.assertTrue(serializer.is_valid(), serializer.errors)
            self.assertEqual(serializer.validated_data[campo], "Texto válido")

    def test_booleano_estricto_y_predeterminado(self):
        base = {"id_ticket": 1, "descripcion_falla": "Falla", "procedimiento_inicial": "Revisión"}
        serializer = CrearOrdenTrabajoSerializer(data=base)
        self.assertTrue(serializer.is_valid())
        self.assertIs(serializer.validated_data["es_reparable"], True)
        for valor in (True, False):
            serializer = CrearOrdenTrabajoSerializer(data={**base, "es_reparable": valor})
            self.assertTrue(serializer.is_valid(), serializer.errors)
            self.assertIs(serializer.validated_data["es_reparable"], valor)
        for valor in (None, 0, 1, "true", "false", "", [], {}):
            serializer = CrearOrdenTrabajoSerializer(data={**base, "es_reparable": valor})
            self.assertFalse(serializer.is_valid())
            self.assertEqual(str(serializer.errors["es_reparable"][0]), "Debe ser verdadero o falso.")

    def test_operaciones_sin_campos_admiten_objeto_y_extras_ignorados(self):
        for datos in ({}, {"extra": "ignorado"}):
            serializer = OperacionOTSerializer(data=datos)
            self.assertTrue(serializer.is_valid(), serializer.errors)
            self.assertEqual(serializer.validated_data, {})
        for datos in (None, [], "texto", 7, True):
            self.assertFalse(OperacionOTSerializer(data=datos).is_valid())

    def test_mensajes_existentes_por_campo_se_conservan(self):
        serializer = CrearOrdenTrabajoSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertEqual(str(serializer.errors["id_ticket"][0]), "Debe indicar un ID de ticket válido.")
        self.assertEqual(str(serializer.errors["descripcion_falla"][0]), "La descripción de la falla es obligatoria.")
        self.assertEqual(str(serializer.errors["procedimiento_inicial"][0]), "El procedimiento inicial es obligatorio.")
