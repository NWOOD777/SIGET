
from contextlib import nullcontext
from datetime import datetime, timezone as dt_timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from activos.models import EstadoActivo
from asignaciones.models import (
    Asignacion,
    DevolucionActivo,
    EstadoAsignacion,
    HistorialEstadoActivo,
)
from asignaciones.permissions import PuedeRegistrarDevolucion
from asignaciones.views import RegistrarDevolucionView


class RegistrarDevolucionTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.tecnico = SimpleNamespace(pk=2)
        self.estado_revision = SimpleNamespace(pk=3)
        self.estado_finalizada = SimpleNamespace(pk=2)

        self.activo = MagicMock()
        self.activo.pk = 20

        self.asignacion = MagicMock()
        self.asignacion.pk = 15
        self.asignacion.id_estado_asignacion_id = 1
        self.asignacion.fecha_finalizacion = None
        self.asignacion.id_activo = self.activo
        self.asignacion.id_solicitud.id_usuario_id = 3

        self.manager_asignacion = MagicMock()
        (
            self.manager_asignacion
            .select_for_update.return_value
            .select_related.return_value
            .get.return_value
        ) = self.asignacion

        self.manager_devolucion = MagicMock()
        self.manager_devolucion.filter.return_value.exists.return_value = False

        self.manager_estado_activo = MagicMock()
        self.manager_estado_activo.get.return_value = self.estado_revision

        self.manager_estado_asignacion = MagicMock()
        self.manager_estado_asignacion.get.return_value = self.estado_finalizada

        self.manager_historial = MagicMock()

        self.patches = [
            patch.object(Asignacion, "objects", self.manager_asignacion),
            patch.object(DevolucionActivo, "objects", self.manager_devolucion),
            patch.object(EstadoActivo, "objects", self.manager_estado_activo),
            patch.object(
                EstadoAsignacion, "objects", self.manager_estado_asignacion
            ),
            patch.object(
                HistorialEstadoActivo, "objects", self.manager_historial
            ),
            patch(
                "asignaciones.views.transaction.atomic",
                return_value=nullcontext(),
            ),
            patch(
                "asignaciones.views.obtener_usuario_actual",
                return_value=self.tecnico,
            ),
            patch("asignaciones.views.registrar_auditoria"),
            patch(
                "asignaciones.permissions.obtener_usuario_actual",
                return_value=self.tecnico,
            ),
            patch(
                "asignaciones.permissions.usuario_tiene_rol",
                return_value=True,
            ),
        ]

        for mocked_patch in self.patches:
            mocked_patch.start()
            self.addCleanup(mocked_patch.stop)

    def crear_request(self, datos=None):
        if datos is None:
            datos = {"condicion_fisica": "Buen estado"}

        request = self.factory.post(
            "/api/asignaciones/15/devolucion/",
            datos,
            format="json",
        )
        request.session = {"siget_usuario_id": 2}
        return request

    def ejecutar(self, datos=None, pk=15):
        return RegistrarDevolucionView.as_view()(
            self.crear_request(datos),
            pk=pk,
        )

    def test_registra_devolucion_y_finaliza_asignacion(self):
        response = self.ejecutar()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["id_asignacion"], 15)
        self.assertEqual(response.data["id_activo"], 20)
        self.assertEqual(response.data["id_usuario_solicitante"], 3)
        self.assertEqual(response.data["id_tecnico_receptor"], 2)
        self.assertEqual(response.data["estado_asignacion"], "Finalizada")
        self.assertEqual(response.data["estado_activo"], "En revisión")

        self.manager_devolucion.create.assert_called_once()
        self.asignacion.save.assert_called_once()
        self.activo.save.assert_called_once()
        self.manager_historial.create.assert_called_once()

        with patch("asignaciones.views.registrar_auditoria") as auditoria:
            # La auditoría se valida en el test específico de abajo.
            pass

    def test_registra_historial_y_auditoria(self):
        with patch("asignaciones.views.registrar_auditoria") as auditoria:
            response = self.ejecutar()

        self.assertEqual(response.status_code, 201)
        self.manager_historial.create.assert_called_once()

        datos_historial = self.manager_historial.create.call_args.kwargs
        self.assertEqual(datos_historial["id_activo"], self.activo)
        self.assertEqual(datos_historial["id_estado_activo"], self.estado_revision)
        self.assertEqual(datos_historial["id_usuario"], self.tecnico)
        self.assertIn("E4-H11", datos_historial["observacion"])

        auditoria.assert_called_once()
        datos_auditoria = auditoria.call_args.kwargs
        self.assertEqual(datos_auditoria["usuario"], self.tecnico)
        self.assertEqual(datos_auditoria["entidad_afectada"], "devolucion_activo")
        self.assertEqual(datos_auditoria["id_registro_afectado"], 15)

    def test_rechaza_asignacion_inexistente(self):
        self.manager_asignacion.select_for_update.return_value \
            .select_related.return_value.get.side_effect = Asignacion.DoesNotExist

        response = self.ejecutar(pk=9999)

        self.assertEqual(response.status_code, 404)
        self.manager_devolucion.create.assert_not_called()
        self.manager_historial.create.assert_not_called()

    def test_rechaza_asignacion_ya_finalizada(self):
        self.asignacion.id_estado_asignacion_id = 2
        self.asignacion.fecha_finalizacion = datetime.now(dt_timezone.utc)

        response = self.ejecutar()

        self.assertEqual(response.status_code, 409)
        self.manager_devolucion.create.assert_not_called()
        self.asignacion.save.assert_not_called()

    def test_rechaza_devolucion_duplicada(self):
        self.manager_devolucion.filter.return_value.exists.return_value = True

        response = self.ejecutar()

        self.assertEqual(response.status_code, 409)
        self.manager_devolucion.create.assert_not_called()
        self.asignacion.save.assert_not_called()
        self.activo.save.assert_not_called()

    def test_rechaza_condicion_fisica_invalida(self):
        response = self.ejecutar({"condicion_fisica": "Desconocida"})

        self.assertEqual(response.status_code, 400)
        self.manager_devolucion.create.assert_not_called()

    def test_rechaza_condicion_fisica_omitida(self):
        response = self.ejecutar({})

        self.assertEqual(response.status_code, 400)
        self.manager_devolucion.create.assert_not_called()

    def test_rechaza_usuario_sin_permisos(self):
        with patch(
            "asignaciones.permissions.usuario_tiene_rol",
            return_value=False,
        ):
            response = self.ejecutar()

        self.assertEqual(response.status_code, 403)
        self.manager_devolucion.create.assert_not_called()

    def test_rechaza_usuario_sin_sesion(self):
        with (
            patch(
                "asignaciones.permissions.obtener_usuario_actual",
                return_value=None,
            ),
            patch(
                "asignaciones.views.obtener_usuario_actual",
                return_value=None,
            ),
        ):
            response = self.ejecutar()

        self.assertEqual(response.status_code, 403)
        self.manager_devolucion.create.assert_not_called()
