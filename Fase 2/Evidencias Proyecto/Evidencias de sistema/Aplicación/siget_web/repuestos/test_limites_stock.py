from django.urls import reverse

from repuestos.models import MovimientoRepuesto, Repuesto
from usuarios.tests.test_integracion_postgresql import PostgreSQLTestBase


class LimitesStockTests(PostgreSQLTestBase):
    def setUp(self):
        super().setUp()
        self.repuesto = Repuesto.objects.create(codigo_repuesto="REP-LIMITE", nombre="Pieza", stock_actual=2147483646, precio_unitario=10)

    def test_cantidad_fuera_de_rango_y_suma_desbordada_no_modifican_stock(self):
        for cantidad in (999999999999999999999, 2147483648, 2, -1, True):
            with self.subTest(cantidad=cantidad):
                respuesta = self.cliente(self.admin).post(reverse("ingreso-repuesto"), {
                    "id_repuesto": self.repuesto.pk, "cantidad": cantidad, "costo_unitario": "10",
                }, format="json")
                self.assertEqual(respuesta.status_code, 400, respuesta.data)
                self.repuesto.refresh_from_db()
                self.assertEqual(self.repuesto.stock_actual, 2147483646)
                self.assertEqual(MovimientoRepuesto.objects.count(), 0)

    def test_ultima_unidad_del_rango_se_puede_ingresar(self):
        respuesta = self.cliente(self.admin).post(reverse("ingreso-repuesto"), {
            "id_repuesto": self.repuesto.pk, "cantidad": 1, "costo_unitario": "10",
        }, format="json")
        self.assertIn(respuesta.status_code, (200, 201), respuesta.data)
        self.repuesto.refresh_from_db()
        self.assertEqual(self.repuesto.stock_actual, 2147483647)
