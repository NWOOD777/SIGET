from typing import TYPE_CHECKING

from django.db import models
from django.utils import timezone

from activos.models import Activo, CategoriaActivo, EstadoActivo
from usuarios.models import Usuario


class EstadoSolicitudAsignacion(models.Model):
    id_estado_solicitud = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        managed = False
        db_table = "estado_solicitud_asignacion"

    def __str__(self):
        return self.nombre


class SolicitudAsignacion(models.Model):
    id_solicitud = models.AutoField(primary_key=True)
    id_usuario = models.ForeignKey(
        Usuario,
        on_delete=models.RESTRICT,
        db_column="id_usuario",
        related_name="solicitudes_asignacion",
    )
    id_categoria = models.ForeignKey(
        CategoriaActivo,
        on_delete=models.RESTRICT,
        db_column="id_categoria",
        related_name="solicitudes",
    )
    id_estado_solicitud = models.ForeignKey(
        EstadoSolicitudAsignacion,
        on_delete=models.RESTRICT,
        db_column="id_estado_solicitud",
        related_name="solicitudes",
    )
    id_administrador_resolutor = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="id_administrador_resolutor",
        related_name="solicitudes_resueltas",
    )
    fecha_solicitud = models.DateTimeField(default=timezone.now)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)
    motivo = models.TextField()
    motivo_rechazo = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "solicitud_asignacion"

    def __str__(self):
        return f"Solicitud #{self.id_solicitud} - {self.id_categoria.nombre} ({self.id_estado_solicitud.nombre})"


class EstadoAsignacion(models.Model):
    id_estado_asignacion = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        managed = False
        db_table = "estado_asignacion"

    def __str__(self):
        return self.nombre


class Asignacion(models.Model):
    if TYPE_CHECKING:
        # Django genera este identificador a partir de la ForeignKey.
        id_activo_id: int

    id_asignacion = models.AutoField(primary_key=True)
    id_solicitud = models.OneToOneField(
        SolicitudAsignacion,
        on_delete=models.RESTRICT,
        db_column="id_solicitud",
        related_name="asignacion",
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
        related_name="entregas_realizadas",
    )
    id_estado_asignacion = models.ForeignKey(
        EstadoAsignacion,
        on_delete=models.RESTRICT,
        db_column="id_estado_asignacion",
        related_name="asignaciones",
    )
    fecha_entrega = models.DateTimeField(default=timezone.now)
    fecha_devolucion_prevista = models.DateTimeField(null=True, blank=True)
    fecha_finalizacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "asignacion"

    def __str__(self):
        return f"Asignacion #{self.id_asignacion} (Activo: {self.id_activo.codigo_inventario})"


class DevolucionActivo(models.Model):
    id_asignacion_id: int

    id_devolucion = models.AutoField(primary_key=True)
    id_asignacion = models.OneToOneField(
        Asignacion,
        on_delete=models.RESTRICT,
        db_column="id_asignacion",
        related_name="devolucion",
    )
    id_tecnico_receptor = models.ForeignKey(
        Usuario,
        on_delete=models.RESTRICT,
        db_column="id_tecnico_receptor",
        related_name="devoluciones_recibidas",
    )
    id_estado_activo_resultante = models.ForeignKey(
        EstadoActivo,
        on_delete=models.RESTRICT,
        db_column="id_estado_activo_resultante",
        related_name="devoluciones_resultantes",
    )
    fecha_devolucion = models.DateTimeField(default=timezone.now)
    condicion_fisica = models.CharField(max_length=50)
    motivo_devolucion = models.CharField(max_length=100, null=True, blank=True)
    observaciones = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "devolucion_activo"

    def __str__(self):
        return f"Devolucion #{self.id_devolucion} (Asignacion #{self.id_asignacion.id_asignacion})"


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
