from django.db import models


class Repuesto(models.Model):
    id_repuesto = models.AutoField(primary_key=True)
    codigo_repuesto = models.CharField(max_length=50, unique=True)
    nombre = models.CharField(max_length=150)
    marca_modelo = models.CharField(max_length=150, null=True, blank=True)
    unidad_medida = models.CharField(max_length=50, default="Unidad")
    stock_actual = models.IntegerField(default=0)
    stock_minimo = models.IntegerField(default=5)
    activo = models.BooleanField(default=True)
    precio_unitario = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    ubicacion_bodega = models.CharField(
        max_length=100, null=True, blank=True
    )

    class Meta:
        managed = False
        db_table = "repuesto"


class MovimientoRepuesto(models.Model):
    id_movimiento = models.AutoField(primary_key=True)

    repuesto = models.ForeignKey(
        Repuesto,
        on_delete=models.PROTECT,
        db_column="id_repuesto",
    )

    usuario = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.PROTECT,
        db_column="id_usuario",
    )

    tipo_movimiento = models.CharField(max_length=50)
    cantidad = models.IntegerField()

    costo_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        default=0,
    )

    motivo = models.CharField(
        max_length=255, null=True, blank=True
    )

    fecha_movimiento = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "movimiento_repuesto"