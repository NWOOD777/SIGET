"""Contrato de entrada de asignación administrativa, sin base de datos."""

from django.test import SimpleTestCase

from tickets.serializers import TicketAsignacionSerializer


class TicketAsignacionSerializerTests(SimpleTestCase):
    def test_datos_validos_y_motivo_limpio(self):
        serializer = TicketAsignacionSerializer(data={"id_tecnico_asignado": 2, "motivo": "  Especialidad requerida  "})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data, {"id_tecnico_asignado": 2, "motivo": "Especialidad requerida"})

    def test_campos_obligatorios(self):
        serializer = TicketAsignacionSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertEqual(set(serializer.errors), {"id_tecnico_asignado", "motivo"})

    def test_motivo_vacio_o_espacios(self):
        for motivo in (None, "", "  \n\t"):
            with self.subTest(motivo=motivo):
                serializer = TicketAsignacionSerializer(data={"id_tecnico_asignado": 2, "motivo": motivo})
                self.assertFalse(serializer.is_valid())
                self.assertIn("motivo", serializer.errors)

    def test_identificador_fuera_de_rango_o_invalido(self):
        for identificador in (None, 0, -1, 2147483648, "invalido", 1.5):
            with self.subTest(identificador=identificador):
                serializer = TicketAsignacionSerializer(data={"id_tecnico_asignado": identificador, "motivo": "Reasignación"})
                self.assertFalse(serializer.is_valid())
                self.assertIn("id_tecnico_asignado", serializer.errors)
