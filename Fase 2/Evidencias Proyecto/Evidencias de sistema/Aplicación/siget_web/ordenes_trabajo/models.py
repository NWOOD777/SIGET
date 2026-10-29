from django.db import models


class EstadoOrdenTrabajo(models.Model):
    id_estado_ot = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50)
    descripcion = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        managed = False
        db_table = "estado_orden_trabajo"

    def __str__(self):
        return self.nombre


class OrdenTrabajo(models.Model):
    id_ticket_id: int
    id_tecnico_responsable_id: int

    id_orden = models.AutoField(primary_key=True)
    codigo_ot = models.CharField(max_length=50, unique=True)
    id_ticket = models.OneToOneField(
        "tickets.Ticket",
        on_delete=models.DO_NOTHING,
        db_column="id_ticket",
    )
    id_tecnico_responsable = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.DO_NOTHING,
        db_column="id_tecnico_responsable",
    )
    id_estado_ot = models.ForeignKey(
        EstadoOrdenTrabajo,
        on_delete=models.DO_NOTHING,
        db_column="id_estado_ot",
    )
    falla_reportada = models.TextField()
    fecha_inicio = models.DateTimeField()
    fecha_estimada_fin = models.DateTimeField(null=True, blank=True)
    fecha_termino = models.DateTimeField(null=True, blank=True)
    justificacion_pausa = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "orden_trabajo"

    def __str__(self):
        return self.codigo_ot


class Diagnostico(models.Model):
    id_diagnostico = models.AutoField(primary_key=True)
    id_orden = models.ForeignKey(
        OrdenTrabajo,
        on_delete=models.DO_NOTHING,
        db_column="id_orden",
    )
    id_tecnico = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.DO_NOTHING,
        db_column="id_tecnico",
    )
    descripcion_falla = models.TextField()
    procedimiento_inicial = models.TextField()
    es_reparable = models.BooleanField()
    fecha_diagnostico = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "diagnostico"


class Intervencion(models.Model):
    id_intervencion = models.AutoField(primary_key=True)
    id_orden = models.ForeignKey(
        OrdenTrabajo,
        on_delete=models.DO_NOTHING,
        db_column="id_orden",
    )
    id_tecnico = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.DO_NOTHING,
        db_column="id_tecnico",
    )
    descripcion_accion = models.TextField()
    resultado_prueba = models.TextField(null=True, blank=True)
    fecha_intervencion = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "intervencion"


class OrdenRepuesto(models.Model):
    id_orden_id: int
    id_repuesto_id: int
    id_usuario_anulacion_id: int | None

    id_orden_repuesto = models.AutoField(primary_key=True)

    id_orden = models.ForeignKey(
        OrdenTrabajo,
        on_delete=models.CASCADE,
        db_column="id_orden",
    )

    id_repuesto = models.ForeignKey(
        "repuestos.Repuesto",
        on_delete=models.PROTECT,
        db_column="id_repuesto",
    )

    cantidad = models.IntegerField()

    costo_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    fecha_imputacion = models.DateTimeField(auto_now_add=True)

    anulado = models.BooleanField(default=False)

    fecha_anulacion = models.DateTimeField(
        null=True,
        blank=True,
    )

    motivo_anulacion = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    id_usuario_anulacion = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.PROTECT,
        db_column="id_usuario_anulacion",
        null=True,
        blank=True,
    )

    class Meta:
        managed = False
        db_table = "orden_repuesto"

    def __str__(self):
        return f"OT {self.id_orden_id} - Repuesto {self.id_repuesto_id}"
