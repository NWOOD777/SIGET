
import unittest
from unittest.mock import patch
from uuid import uuid4

from django.db import connection

from rest_framework.test import APIRequestFactory

from asignaciones.models import (
    Asignacion,
    DevolucionActivo,
    HistorialEstadoActivo,
)
from asignaciones.views import RegistrarDevolucionView


class RegistrarDevolucionRollbackIntegrationTest(unittest.TestCase):
    """
    Prueba de integración contra la base PostgreSQL existente.
    Verifica que un error de auditoría revierta todos los cambios.
    """

    def setUp(self):
        self.solicitud_id = None
        self.activo_id = None
        self.asignacion_id = None
        self.codigo = f"TEST-E4H10-RB-{uuid4().hex[:8].upper()}"

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO solicitud_asignacion
                    (id_usuario, id_categoria, id_estado_solicitud,
                     fecha_solicitud, motivo)
                VALUES (1, 1, 4, CURRENT_TIMESTAMP,
                        'Prueba automática de rollback E4-H10')
                RETURNING id_solicitud
                """
            )
            self.solicitud_id = cursor.fetchone()[0]

            cursor.execute(
                """
                INSERT INTO activo
                    (codigo_inventario, numero_serie, id_modelo,
                     id_ubicacion, id_estado_activo, valor_adquisicion)
                VALUES (%s, %s, 1, 1, 2, 100000)
                RETURNING id_activo
                """,
                [self.codigo, f"SERIE-{self.codigo}"],
            )
            self.activo_id = cursor.fetchone()[0]

            cursor.execute(
                """
                INSERT INTO asignacion
                    (id_solicitud, id_activo, id_tecnico_entrega,
                     id_estado_asignacion, fecha_entrega)
                VALUES (%s, %s, 2, 1, CURRENT_TIMESTAMP)
                RETURNING id_asignacion
                """,
                [self.solicitud_id, self.activo_id],
            )
            self.asignacion_id = cursor.fetchone()[0]

    def tearDown(self):
        # Eliminar exclusivamente los datos creados por esta prueba.
        with connection.cursor() as cursor:
            if self.asignacion_id is not None:
                cursor.execute(
                    "DELETE FROM devolucion_activo WHERE id_asignacion = %s",
                    [self.asignacion_id],
                )
                cursor.execute(
                    """
                    DELETE FROM bitacora_auditoria
                    WHERE entidad_afectada = 'devolucion_activo'
                      AND id_registro_afectado = %s
                    """,
                    [self.asignacion_id],
                )

            if self.activo_id is not None:
                cursor.execute(
                    "DELETE FROM historial_estado_activo WHERE id_activo = %s",
                    [self.activo_id],
                )

            if self.asignacion_id is not None:
                cursor.execute(
                    "DELETE FROM asignacion WHERE id_asignacion = %s",
                    [self.asignacion_id],
                )

            if self.activo_id is not None:
                cursor.execute(
                    "DELETE FROM activo WHERE id_activo = %s",
                    [self.activo_id],
                )

            if self.solicitud_id is not None:
                cursor.execute(
                    "DELETE FROM solicitud_asignacion WHERE id_solicitud = %s",
                    [self.solicitud_id],
                )

    def test_error_auditoria_revierte_toda_la_devolucion(self):
        factory = APIRequestFactory()
        request = factory.post(
            f"/api/asignaciones/{self.asignacion_id}/devolucion/",
            {
                "condicion_fisica": "Buen estado",
                "observaciones": "Prueba automática de rollback",
            },
            format="json",
        )

        # Simular una sesión autenticada del técnico de soporte.
        request.session = {"siget_usuario_id": 2}

        with patch(
            "asignaciones.views.registrar_auditoria",
            side_effect=RuntimeError("Fallo controlado de auditoría"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "Fallo controlado de auditoría"
            ):
                RegistrarDevolucionView.as_view()(
                    request, pk=self.asignacion_id
                )

        # Consultar directamente PostgreSQL después del rollback.
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id_estado_asignacion, fecha_finalizacion
                FROM asignacion
                WHERE id_asignacion = %s
                """,
                [self.asignacion_id],
            )
            estado_asignacion, fecha_finalizacion = cursor.fetchone()

            cursor.execute(
                """
                SELECT id_estado_activo
                FROM activo
                WHERE id_activo = %s
                """,
                [self.activo_id],
            )
            estado_activo = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM devolucion_activo
                WHERE id_asignacion = %s
                """,
                [self.asignacion_id],
            )
            devoluciones = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM historial_estado_activo
                WHERE id_activo = %s
                """,
                [self.activo_id],
            )
            historiales = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM bitacora_auditoria
                WHERE entidad_afectada = 'devolucion_activo'
                  AND id_registro_afectado = %s
                """,
                [self.asignacion_id],
            )
            auditorias = cursor.fetchone()[0]

        self.assertEqual(estado_asignacion, 1, "La asignación debe seguir activa")
        self.assertIsNone(
            fecha_finalizacion,
            "La asignación no debe quedar finalizada",
        )
        self.assertEqual(estado_activo, 2, "El activo debe seguir asignado")
        self.assertEqual(devoluciones, 0, "No debe persistir la devolución")
        self.assertEqual(historiales, 0, "No debe persistir el historial")
        self.assertEqual(auditorias, 0, "No debe persistir la auditoría")
