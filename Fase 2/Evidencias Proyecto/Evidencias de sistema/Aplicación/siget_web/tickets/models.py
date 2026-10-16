from django.db import models
from django.utils import timezone

from activos.models import Activo
from usuarios.models import Usuario


class PrioridadTicket(models.Model):
    id_prioridad = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50, unique=True)
    nivel_urgencia = models.IntegerField(unique=True)
    descripcion = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        managed = False
        db_table = "prioridad_ticket"

    def __str__(self):
        return f"{self.nombre} (Urgencia {self.nivel_urgencia})"


class SLA(models.Model):
    id_sla = models.AutoField(primary_key=True)
    id_prioridad = models.OneToOneField(
        PrioridadTicket,
        on_delete=models.RESTRICT,
        db_column="id_prioridad",
        related_name="sla",
    )
    tiempo_respuesta_horas = models.IntegerField()
    tiempo_resolucion_horas = models.IntegerField()
    descripcion = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        managed = False
        db_table = "sla"

    def __str__(self):
        return f"SLA {self.id_prioridad.nombre} (Resp: {self.tiempo_respuesta_horas}h / Resol: {self.tiempo_resolucion_horas}h)"


class EstadoTicket(models.Model):
    id_estado_ticket = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        managed = False
        db_table = "estado_ticket"

    def __str__(self):
        return self.nombre


class Ticket(models.Model):
    id_ticket = models.AutoField(primary_key=True)
    codigo_ticket = models.CharField(max_length=50, unique=True)
    id_usuario_solicitante = models.ForeignKey(
        Usuario,
        on_delete=models.RESTRICT,
        db_column="id_usuario_solicitante",
        related_name="tickets_solicitados",
    )
    id_tecnico_asignado = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="id_tecnico_asignado",
        related_name="tickets_asignados",
    )
    id_activo = models.ForeignKey(
        Activo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="id_activo",
        related_name="tickets",
    )
    id_estado_ticket = models.ForeignKey(
        EstadoTicket,
        on_delete=models.RESTRICT,
        db_column="id_estado_ticket",
        related_name="tickets",
    )
    id_prioridad = models.ForeignKey(
        PrioridadTicket,
        on_delete=models.RESTRICT,
        db_column="id_prioridad",
        related_name="tickets",
    )
    asunto = models.CharField(max_length=200)
    descripcion = models.TextField()
    fecha_creacion = models.DateTimeField(default=timezone.now)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "ticket"

    def __str__(self):
        return f"[{self.codigo_ticket}] {self.asunto} ({self.id_estado_ticket.nombre})"


class ComentarioTicket(models.Model):
    id_comentario = models.AutoField(primary_key=True)
    id_ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        db_column="id_ticket",
        related_name="comentarios",
    )
    id_usuario = models.ForeignKey(
        Usuario,
        on_delete=models.RESTRICT,
        db_column="id_usuario",
        related_name="comentarios_ticket",
    )
    mensaje = models.TextField()
    fecha_registro = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = "comentario_ticket"

    def __str__(self):
        return f"Comentario #{self.id_comentario} en Ticket #{self.id_ticket.id_ticket}"


class AdjuntoTicket(models.Model):
    id_adjunto = models.AutoField(primary_key=True)
    id_ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        db_column="id_ticket",
        related_name="adjuntos",
    )
    nombre_archivo = models.CharField(max_length=255)
    ruta_archivo = models.CharField(max_length=500)
    tipo_mime = models.CharField(max_length=100, null=True, blank=True)
    tamano_bytes = models.BigIntegerField(null=True, blank=True)
    fecha_subida = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = "adjunto_ticket"

    def __str__(self):
        return f"{self.nombre_archivo} ({self.id_ticket.codigo_ticket})"


class EvaluacionCSAT(models.Model):
    id_evaluacion = models.AutoField(primary_key=True)
    id_ticket = models.OneToOneField(
        Ticket,
        on_delete=models.CASCADE,
        db_column="id_ticket",
        related_name="evaluacion_csat",
    )
    id_usuario = models.ForeignKey(
        Usuario,
        on_delete=models.RESTRICT,
        db_column="id_usuario",
        related_name="evaluaciones_csat",
    )
    calificacion_estrellas = models.IntegerField()
    comentario = models.TextField(null=True, blank=True)
    fecha_evaluacion = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = "evaluacion_csat"

    def __str__(self):
        return f"CSAT {self.calificacion_estrellas}* (Ticket #{self.id_ticket.id_ticket})"
