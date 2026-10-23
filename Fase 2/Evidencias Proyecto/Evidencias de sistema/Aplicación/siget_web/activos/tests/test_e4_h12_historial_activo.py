
from types import SimpleNamespace
from unittest.mock import patch

from activos.models import Activo
from activos.views import ActivoHistorialView

from .helpers import (
    ActivosTestBase,
    crear_request_con_sesion,
    obtener_data_dict,
)


class HistorialActivoE4H12Tests(ActivosTestBase):
    """Pruebas para E4-H12: historial y trazabilidad del equipo."""

    def consultar(self, search="ACT-0010", usuario_id=1):
        request = crear_request_con_sesion(
            self.factory,
            "GET",
            "/api/activos/historial/",
            usuario_id=usuario_id,
            data={"search": search} if search is not None else {},
        )

        with (
            patch(
                "activos.permissions.obtener_usuario_actual",
                return_value=(
                    self.admin_user if usuario_id == 1
                    else self.tecnico_user if usuario_id == 2
                    else None
                ),
            ),
            patch(
                "activos.permissions.es_administrador",
                return_value=usuario_id == 1,
            ),
            patch.object(Activo.objects, "select_related") as mock_activos,
            patch("activos.views.Asignacion.objects.filter") as mock_asignaciones,
            patch("activos.views.DevolucionActivo.objects.filter") as mock_devoluciones,
            patch("activos.views.HistorialEstadoActivo.objects.filter") as mock_estados,
        ):
            mock_activos.return_value.get.return_value = self.activo

            mock_asignaciones.return_value.select_related.return_value = []
            mock_devoluciones.return_value.select_related.return_value = []
            mock_estados.return_value.select_related.return_value = []

            response = ActivoHistorialView.as_view()(request)

        return response

    def test_01_consultar_historial_por_codigo(self):
        response = self.consultar("ACT-0010")

        self.assertEqual(response.status_code, 200)
        data = obtener_data_dict(response)
        self.assertEqual(data["activo"]["codigo_inventario"], "ACT-0010")
        self.assertIn("movimientos", data)
        self.assertEqual(data["total_movimientos"], 0)

    def test_02_buscar_por_numero_de_serie(self):
        response = self.consultar("SN-DELL-9999")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            obtener_data_dict(response)["activo"]["numero_serie"],
            "SN-DELL-9999",
        )

    def test_03_activo_existente_sin_movimientos(self):
        response = self.consultar()

        self.assertEqual(response.status_code, 200)
        data = obtener_data_dict(response)
        self.assertEqual(data["movimientos"], [])
        self.assertEqual(data["total_movimientos"], 0)
        self.assertIn("No hay movimientos", data["mensaje"])

    def test_04_activo_inexistente_devuelve_404(self):
        request = crear_request_con_sesion(
            self.factory,
            "GET",
            "/api/activos/historial/",
            usuario_id=1,
            data={"search": "NO-EXISTE"},
        )

        with (
            patch(
                "activos.permissions.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch("activos.permissions.es_administrador", return_value=True),
            patch.object(Activo.objects, "select_related") as mock_activos,
        ):
            mock_activos.return_value.get.side_effect = Activo.DoesNotExist
            response = ActivoHistorialView.as_view()(request)

        self.assertEqual(response.status_code, 404)

    def test_05_busqueda_vacia_devuelve_400(self):
        response = self.consultar(None)

        self.assertEqual(response.status_code, 400)

    def test_06_usuario_no_administrador_recibe_403(self):
        request = crear_request_con_sesion(
            self.factory,
            "GET",
            "/api/activos/historial/",
            usuario_id=2,
            data={"search": "ACT-0010"},
        )

        with (
            patch(
                "activos.permissions.obtener_usuario_actual",
                return_value=self.tecnico_user,
            ),
            patch("activos.permissions.es_administrador", return_value=False),
            patch("activos.permissions.usuario_tiene_rol", return_value=False),
            patch("activos.permissions.usuario_tiene_permiso", return_value=False),

        ):
            response = ActivoHistorialView.as_view()(request)

        self.assertEqual(response.status_code, 403)

    def test_07_historial_incluye_asignacion_devolucion_y_estado(self):
        usuario = SimpleNamespace(
            id_usuario=3,
            nombres="Usuario",
            apellidos="Solicitante",
        )
        tecnico = SimpleNamespace(
            id_usuario=2,
            nombres="Tecnico",
            apellidos="Soporte",
        )
        estado = SimpleNamespace(nombre="Disponible")

        solicitud = SimpleNamespace(id_usuario=usuario)
        asignacion = SimpleNamespace(
            id_asignacion=200,
            id_solicitud=solicitud,
            id_tecnico_entrega=tecnico,
            id_estado_asignacion=SimpleNamespace(nombre="Finalizada"),
            fecha_entrega="2026-10-12T10:00:00Z",
            fecha_devolucion_prevista=None,
            fecha_finalizacion="2026-10-15T15:00:00Z",
        )
        devolucion = SimpleNamespace(
            id_devolucion=300,
            id_asignacion_id=200,
            id_asignacion=asignacion,
            id_tecnico_receptor=tecnico,
            fecha_devolucion="2026-10-15T15:00:00Z",
            condicion_fisica="Buen estado",
            motivo_devolucion="Fin de proyecto",
            observaciones="Sin daños",
            id_estado_activo_resultante=estado,
        )
        cambio = SimpleNamespace(
            id_historial_estado=400,
            fecha_cambio="2026-10-15T15:00:00Z",
            id_estado_activo=estado,
            id_usuario=tecnico,
            observacion="Devolución del equipo",
        )

        request = crear_request_con_sesion(
            self.factory,
            "GET",
            "/api/activos/historial/",
            usuario_id=1,
            data={"search": "ACT-0010"},
        )

        with (
            patch(
                "activos.permissions.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch("activos.permissions.es_administrador", return_value=True),
            patch.object(Activo.objects, "select_related") as mock_activos,
            patch("activos.views.Asignacion.objects.filter") as mock_asignaciones,
            patch("activos.views.DevolucionActivo.objects.filter") as mock_devoluciones,
            patch("activos.views.HistorialEstadoActivo.objects.filter") as mock_estados,
        ):
            mock_activos.return_value.get.return_value = self.activo
            mock_asignaciones.return_value.select_related.return_value = [asignacion]
            mock_devoluciones.return_value.select_related.return_value = [devolucion]
            mock_estados.return_value.select_related.return_value = [cambio]

            response = ActivoHistorialView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        data = obtener_data_dict(response)
        tipos = [movimiento["tipo"] for movimiento in data["movimientos"]]

        self.assertIn("asignacion", tipos)
        self.assertIn("devolucion", tipos)
        self.assertIn("cambio_estado", tipos)
        self.assertEqual(data["total_movimientos"], 3)

        fechas = [movimiento["fecha"] for movimiento in data["movimientos"]]
        self.assertEqual(fechas, sorted(fechas))
