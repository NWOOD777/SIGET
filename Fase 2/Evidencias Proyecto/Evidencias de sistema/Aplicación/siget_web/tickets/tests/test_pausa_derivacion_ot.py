from datetime import timedelta

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from ordenes_trabajo.services import (
    calcular_tiempo_pausa_ot,
    pausar_orden_trabajo,
    reanudar_orden_trabajo,
    reasignar_orden_trabajo,
)
from tickets.tests.test_tickets_ordenes_postgresql import (
    IntegracionOTEstadosTests,
)
from usuarios.models import BitacoraAuditoria


class IntegracionOTPausaDerivacionTests(IntegracionOTEstadosTests):
    def test_pausar_ot_registra_motivo_y_auditoria(self):
        orden = self.crear_ot()
        resultado = pausar_orden_trabajo(
            orden.pk, self.tecnico, "Esperando repuesto"
        )

        orden.refresh_from_db()
        self.assertEqual(orden.id_estado_ot.nombre, "Pausada")
        self.assertEqual(orden.justificacion_pausa, "Esperando repuesto")
        self.assertEqual(resultado.pk, orden.pk)
        self.assertTrue(
            BitacoraAuditoria.objects.filter(
                accion="OT_PAUSADA"
            ).exists()
        )

    def test_pausar_ot_rechaza_justificacion_vacia(self):
        orden = self.crear_ot()

        with self.assertRaises(ValidationError):
            pausar_orden_trabajo(orden.pk, self.tecnico, "  ")

        orden.refresh_from_db()
        self.assertEqual(orden.id_estado_ot.nombre, "En Diagnóstico")
        self.assertFalse(
            BitacoraAuditoria.objects.filter(
                accion="OT_PAUSADA"
            ).exists()
        )

    def test_reanudar_ot_pausada_y_limpia_justificacion(self):
        orden = self.crear_ot()
        pausar_orden_trabajo(
            orden.pk, self.tecnico, "Esperando repuesto"
        )

        reanudar_orden_trabajo(orden.pk, self.tecnico)

        orden.refresh_from_db()
        self.assertEqual(orden.id_estado_ot.nombre, "En Reparación")
        self.assertFalse(orden.justificacion_pausa)
        self.assertTrue(
            BitacoraAuditoria.objects.filter(
                accion="OT_REANUDADA"
            ).exists()
        )

    def test_no_permite_reanudar_ot_no_pausada(self):
        orden = self.crear_ot()

        with self.assertRaises(ValidationError):
            reanudar_orden_trabajo(orden.pk, self.tecnico)

        orden.refresh_from_db()
        self.assertEqual(orden.id_estado_ot.nombre, "En Diagnóstico")

    def test_calcular_tiempo_pausa_ot_reconoce_pausa_abierta(self):
        orden = self.crear_ot()
        pausar_orden_trabajo(
            orden.pk, self.tecnico, "Esperando repuesto"
        )

        tiempo = calcular_tiempo_pausa_ot(orden.pk)

        self.assertGreaterEqual(tiempo, timedelta(0))

    def test_reasignar_ot_rechaza_observaciones_vacias(self):
        orden = self.crear_ot()

        with self.assertRaises(ValidationError):
            reasignar_orden_trabajo(
                orden.pk, self.tecnico, self.segundo, " "
            )

        orden.refresh_from_db()
        self.assertEqual(orden.id_tecnico_responsable, self.tecnico)
        self.assertFalse(
            BitacoraAuditoria.objects.filter(
                accion="OT_REASIGNADA"
            ).exists()
        )

    def test_calcular_tiempo_pausa_ot_con_intervalo_cerrado(self):
        orden = self.crear_ot()
        pausar_orden_trabajo(
            orden.pk, self.tecnico, "Esperando repuesto"
        )
        reanudar_orden_trabajo(orden.pk, self.tecnico)

        eventos = list(
            BitacoraAuditoria.objects.filter(
                modulo="ORDENES_TRABAJO",
                entidad_afectada="orden_trabajo",
                id_registro_afectado=orden.pk,
                accion__in=["OT_PAUSADA", "OT_REANUDADA"],
            ).order_by("fecha_evento", "id_auditoria")
        )
        self.assertEqual(len(eventos), 2)

        inicio = timezone.now() - timedelta(minutes=30)
        fin = inicio + timedelta(minutes=10)

        BitacoraAuditoria.objects.filter(
            pk=eventos[0].pk
        ).update(fecha_evento=inicio)
        BitacoraAuditoria.objects.filter(
            pk=eventos[1].pk
        ).update(fecha_evento=fin)

        tiempo = calcular_tiempo_pausa_ot(
            orden.pk,
            hasta=fin + timedelta(minutes=5),
        )

        self.assertEqual(tiempo, timedelta(minutes=10))

    def test_calcular_tiempo_pausa_ot_con_intervalo_abierto(self):
        orden = self.crear_ot()
        pausar_orden_trabajo(
            orden.pk, self.tecnico, "Esperando repuesto"
        )

        evento = BitacoraAuditoria.objects.get(
            modulo="ORDENES_TRABAJO",
            entidad_afectada="orden_trabajo",
            id_registro_afectado=orden.pk,
            accion="OT_PAUSADA",
        )

        inicio = timezone.now() - timedelta(minutes=20)
        BitacoraAuditoria.objects.filter(
            pk=evento.pk
        ).update(fecha_evento=inicio)

        tiempo = calcular_tiempo_pausa_ot(
            orden.pk,
            hasta=inicio + timedelta(minutes=15),
        )

        self.assertEqual(tiempo, timedelta(minutes=15))
