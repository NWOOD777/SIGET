"""Consulta de etiquetas y validación del equipo con PostgreSQL."""

from activos.models import CategoriaActivo, EstadoActivo, ModeloActivo
from asignaciones.models import Asignacion
from usuarios.models import BitacoraAuditoria
from usuarios.tests.test_integracion_postgresql import PostgreSQLTestBase


class IdentificacionPostgreSQLTests(PostgreSQLTestBase):
    url = "/api/activos/identificar/"

    def consultar(self, identificador, **contexto):
        return self.cliente(self.tecnico).get(self.url, {"identificador": identificador, **contexto})

    def test_busqueda_exacta_codigo_serie_y_ceros_iniciales(self):
        activo = self.activo()
        activo.numero_serie = "00001234"
        activo.save()
        for identificador in (activo.codigo_inventario, activo.codigo_inventario.lower(), "00001234"):
            with self.subTest(identificador=identificador):
                respuesta = self.consultar(identificador)
                self.assertEqual(respuesta.status_code, 200, respuesta.data)
                self.assertEqual(respuesta.data["id_activo"], activo.pk)
                self.assertEqual(respuesta.data["modelo"], self.modelo.nombre)
                self.assertNotIn("rut", respuesta.data)
        for identificador in ("1234", "ACT-000", "NO-REGISTRADO"):
            self.assertEqual(self.consultar(identificador).status_code, 404)

    def test_serie_sensible_a_mayusculas_y_colision_entre_referencias(self):
        primero, segundo = self.activo(), self.activo()
        self.assertEqual(self.consultar(primero.numero_serie.lower()).status_code, 404)
        segundo.numero_serie = primero.codigo_inventario
        segundo.save()
        self.assertEqual(self.consultar(primero.codigo_inventario).status_code, 409)

    def test_rechaza_identificadores_y_contextos_invalidos(self):
        self.activo()
        for valor in (
            "",
            " ACT-0001",
            "ACT-0001 ",
            "ACT 0001",
            "ACT-0001\n",
            "ACT-0001\t",
            "á123",
            "https://example.com/ACT-0001",
            "' OR 1=1",
            "A" * 101,
        ):
            with self.subTest(valor=repr(valor)):
                self.assertEqual(self.consultar(valor).status_code, 400)
        for contexto in ({"id_solicitud": 0}, {"id_asignacion": -1}, {"id_solicitud": "x"}, {"id_solicitud": 1, "id_asignacion": 1}):
            self.assertEqual(self.consultar("ACT-0001", **contexto).status_code, 400)

    def test_roles_validados_en_postgresql_y_consulta_sin_escrituras(self):
        activo = self.activo()
        for usuario in (None, self.solicitante, self.otro):
            self.assertIn(self.cliente(usuario).get(self.url, {"identificador": activo.codigo_inventario}).status_code, (401, 403))
        auditorias = BitacoraAuditoria.objects.count()
        for usuario in (self.admin, self.tecnico):
            self.assertEqual(self.cliente(usuario).get(self.url, {"identificador": activo.codigo_inventario}).status_code, 200)
        self.assertEqual(BitacoraAuditoria.objects.count(), auditorias)
        self.assertFalse(Asignacion.objects.exists())
        activo.refresh_from_db()
        self.assertEqual(activo.id_estado_activo.nombre, "Disponible")

    def test_entrega_solicitud_aprobada_categoria_y_disponibilidad(self):
        activo, solicitud = self.preparar_entrega()
        self.assertEqual(self.consultar(activo.codigo_inventario, id_solicitud=solicitud).status_code, 200)
        incompatible = self.activo()
        categoria = CategoriaActivo.objects.create(nombre="Monitor")
        incompatible.id_modelo = ModeloActivo.objects.create(nombre="Pantalla", id_marca=self.marca, id_categoria=categoria)
        incompatible.save()
        self.assertEqual(self.consultar(incompatible.codigo_inventario, id_solicitud=solicitud).status_code, 409)
        activo.id_estado_activo = EstadoActivo.objects.get(nombre="En revisión")
        activo.save()
        self.assertEqual(self.consultar(activo.codigo_inventario, id_solicitud=solicitud).status_code, 409)
        respuesta = self.cliente(self.tecnico).post(f"/api/solicitudes-asignacion/{solicitud}/entregar/", {"id_activo": activo.pk}, format="json")
        self.assertIn(respuesta.status_code, (400, 409))
        self.assertFalse(Asignacion.objects.exists())

    def test_solicitud_pendiente_inexistente_o_atendida(self):
        activo, solicitud = self.preparar_entrega()
        pendiente = (
            self.cliente(self.otro)
            .post("/api/solicitudes-asignacion/", {"id_categoria": self.categoria.pk, "motivo": "Solicitud adicional"}, format="json")
            .data["id_solicitud"]
        )
        self.assertEqual(self.consultar(activo.codigo_inventario, id_solicitud=pendiente).status_code, 409)
        self.assertEqual(self.consultar(activo.codigo_inventario, id_solicitud=99999).status_code, 404)
        self.cliente(self.tecnico).post(f"/api/solicitudes-asignacion/{solicitud}/entregar/", {"id_activo": activo.pk}, format="json")
        self.assertEqual(self.consultar(activo.codigo_inventario, id_solicitud=solicitud).status_code, 409)

    def test_devolucion_comprueba_equipo_y_asignacion_activa(self):
        activo, asignacion = self.entregar()
        otro = self.activo()
        self.assertEqual(self.consultar(activo.codigo_inventario, id_asignacion=asignacion).status_code, 200)
        self.assertEqual(self.consultar(otro.codigo_inventario, id_asignacion=asignacion).status_code, 409)
        self.assertEqual(self.consultar(activo.codigo_inventario, id_asignacion=99999).status_code, 404)
        self.cliente(self.tecnico).post(f"/api/asignaciones/{asignacion}/devolucion/", {"condicion_fisica": "Buen estado"}, format="json")
        self.assertEqual(self.consultar(activo.codigo_inventario, id_asignacion=asignacion).status_code, 409)
