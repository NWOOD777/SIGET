"""Compara validación Python, serializer y CHECK real sin tocar desarrollo."""
import sys

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase

from ordenes_trabajo.cierre_serializers import CierreTecnicoEntradaSerializer
from ordenes_trabajo.models import CierreTecnico
from ordenes_trabajo.validaciones_cierre import ESPACIOS_CIERRE, validar_contenido_cierre
from tickets.tests.test_consolidacion_ot_postgresql import ConsolidacionOTFixture


class PoliticaUnicodeTests(SimpleTestCase):
    def test_conjunto_explicito_coincide_con_python(self):
        self.assertEqual(set(ESPACIOS_CIERRE), {chr(n) for n in range(sys.maxunicode + 1) if chr(n).isspace()})
        self.assertEqual(len(ESPACIOS_CIERRE), 29)


class EquivalenciaUnicodePostgreSQLTests(ConsolidacionOTFixture):
    def setUp(self):
        super().setUp()
        self.orden = self.crear_ot()

    def comparar(self, resultado, campo):
        casos = [None, "", " ", "\t\n\r", *ESPACIOS_CIERRE, ESPACIOS_CIERRE,
                 "\u00a0 \u202f\u2003\u3000", "Texto real", ESPACIOS_CIERRE + "Solución válida" + ESPACIOS_CIERRE,
                 "\u200b"]  # ZERO WIDTH SPACE no pertenece a str.isspace(): no se cambia esa semántica.
        for valor in casos:
            with self.subTest(campo=campo, valor=repr(valor)):
                datos = dict(resultado=resultado)
                if resultado == "REPARACION_EXITOSA":
                    datos.update(solucion_aplicada="Solución", pruebas_realizadas="Pruebas")
                datos[campo] = valor
                esperado = valor is not None and bool(valor.strip(ESPACIOS_CIERRE))
                try:
                    validar_contenido_cierre(**datos)
                    python_valido = True
                except ValidationError:
                    python_valido = False
                serializer = CierreTecnicoEntradaSerializer(data=datos)
                self.assertEqual(python_valido, esperado)
                self.assertEqual(serializer.is_valid(), esperado, serializer.errors)
                # ORM create omite full_clean: el rechazo procede del CHECK real.
                with transaction.atomic():
                    try:
                        with transaction.atomic():
                            CierreTecnico.objects.create(id_orden=self.orden, id_tecnico=self.tecnico, **datos)
                        sql_valido = True
                    except IntegrityError as error:
                        diag = getattr(error.__cause__, "diag", None)
                        self.assertEqual(getattr(diag, "constraint_name", None), "ck_cierre_tecnico_contenido")
                        sql_valido = False
                    self.assertEqual(sql_valido, esperado)
                    transaction.set_rollback(True)

    def test_solucion(self):
        self.comparar("REPARACION_EXITOSA", "solucion_aplicada")

    def test_pruebas(self):
        self.comparar("REPARACION_EXITOSA", "pruebas_realizadas")

    def test_informe(self):
        self.comparar("NO_REPARABLE", "informe_descarte")

    def test_opcionales_con_espacios_conservan_semantica(self):
        datos = dict(resultado="NO_REPARABLE", informe_descarte="Informe", solucion_aplicada=ESPACIOS_CIERRE,
                     pruebas_realizadas=None)
        validar_contenido_cierre(**datos)
        self.assertTrue(CierreTecnicoEntradaSerializer(data=datos).is_valid())
        cierre = CierreTecnico.objects.create(id_orden=self.orden, id_tecnico=self.tecnico, **datos)
        cierre.refresh_from_db()
        self.assertEqual(cierre.solucion_aplicada, ESPACIOS_CIERRE)
