
from django.db import models
from django.utils import timezone

from activos.models import Activo
from usuarios.models import Usuario


class EstadoAsignacion(models.Model):
    id_estado_asignacion = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50)

    class Meta:
        managed = False
        db_table = "estado_asignacion"


class SolicitudAsignacion(models.Model):
    id_solicitud = models.AutoField(primary_key=True)

    id_usuario = models.ForeignKey(
        Usuario,
        on_delete=models.RESTRICT,
        db_column="id_usuario",
        related_name="solicitudes_asignacion",
    )

    class Meta:
        managed = False
        db_table = "solicitud_asignacion"


class Asignacion(models.Model):
    id_asignacion = models.AutoField(primary_key=True)

    id_solicitud = models.ForeignKey(
        SolicitudAsignacion,
        on_delete=models.RESTRICT,
        db_column="id_solicitud",
        related_name="asignaciones",
    )

    id_activo = models.ForeignKey(
        Activo,
        on_delete=models.RESTRICT,
        db_column="id_activo",
        related_name="asignaciones",
    )

    id_tecnico_entrega = models.ForeignKey(
        Usuario,
        on_delete=models.RESTRICT,
        db_column="id_tecnico_entrega",
        related_name="asignaciones_entregadas",
    )

    id_estado_asignacion = models.ForeignKey(
        EstadoAsignacion,
        on_delete=models.RESTRICT,
        db_column="id_estado_asignacion",
        related_name="asignaciones",
    )

    fecha_entrega = models.DateTimeField(default=timezone.now)
    fecha_devolucion_prevista = models.DateTimeField(
        null=True,
        blank=True,
    )
    fecha_finalizacion = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        managed = False
        db_table = "asignacion"


class DevolucionActivo(models.Model):
    id_devolucion = models.AutoField(primary_key=True)

    id_asignacion = models.ForeignKey(
        Asignacion,
        on_delete=models.RESTRICT,
        db_column="id_asignacion",
        related_name="devoluciones",
    )

    id_tecnico_receptor = models.ForeignKey(
        Usuario,
        on_delete=models.RESTRICT,
        db_column="id_tecnico_receptor",
        related_name="devoluciones_recibidas",
    )

    id_estado_activo_resultante = models.ForeignKey(
        "activos.EstadoActivo",
        on_delete=models.RESTRICT,
        db_column="id_estado_activo_resultante",
    )

    fecha_devolucion = models.DateTimeField(default=timezone.now)

    condicion_fisica = models.CharField(max_length=50)
    motivo_devolucion = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )
    observaciones = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "devolucion_activo"


class HistorialEstadoActivo(models.Model):
    id_historial_estado = models.AutoField(primary_key=True)

    id_activo = models.ForeignKey(
        Activo,
        on_delete=models.CASCADE,
        db_column="id_activo",
        related_name="historial_estados",
    )

    id_estado_activo = models.ForeignKey(
        "activos.EstadoActivo",
        on_delete=models.RESTRICT,
        db_column="id_estado_activo",
    )

    id_usuario = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        db_column="id_usuario",
        null=True,
        blank=True,
    )

    fecha_cambio = models.DateTimeField(default=timezone.now)
    observacion = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "historial_estado_activo"
