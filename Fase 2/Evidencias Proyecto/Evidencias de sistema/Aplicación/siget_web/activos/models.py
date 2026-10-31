from typing import TYPE_CHECKING

from django.db import models


class CategoriaActivo(models.Model):
    id_categoria = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        managed = False
        db_table = "categoria_activo"

    def __str__(self):
        return self.nombre


class Marca(models.Model):
    id_marca = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100, unique=True)

    class Meta:
        managed = False
        db_table = "marca"

    def __str__(self):
        return self.nombre


class ModeloActivo(models.Model):
    id_modelo = models.AutoField(primary_key=True)

    id_marca = models.ForeignKey(
        Marca,
        models.DO_NOTHING,
        db_column="id_marca",
    )

    id_categoria = models.ForeignKey(
        CategoriaActivo,
        models.DO_NOTHING,
        db_column="id_categoria",
    )

    nombre = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = "modelo_activo"

    def __str__(self):
        return self.nombre


class Ubicacion(models.Model):
    id_ubicacion = models.AutoField(primary_key=True)
    nombre_area = models.CharField(max_length=100)
    edificio = models.CharField(max_length=50, null=True, blank=True)
    piso = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        managed = False
        db_table = "ubicacion"

    def __str__(self):
        return self.nombre_area


class EstadoActivo(models.Model):
    id_estado_activo = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        managed = False
        db_table = "estado_activo"

    def __str__(self):
        return self.nombre


class Activo(models.Model):
    if TYPE_CHECKING:
        id_modelo_id: int
        id_ubicacion_id: int
        id_estado_activo_id: int

    id_activo = models.AutoField(primary_key=True)
    codigo_inventario = models.CharField(max_length=50, unique=True)
    numero_serie = models.CharField(max_length=100, unique=True)

    id_modelo = models.ForeignKey(
        ModeloActivo,
        models.DO_NOTHING,
        db_column="id_modelo",
    )

    id_ubicacion = models.ForeignKey(
        Ubicacion,
        models.DO_NOTHING,
        db_column="id_ubicacion",
    )

    id_estado_activo = models.ForeignKey(
        EstadoActivo,
        models.DO_NOTHING,
        db_column="id_estado_activo",
    )

    valor_adquisicion = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    fecha_compra = models.DateField(
        null=True,
        blank=True,
    )

    fecha_garantia = models.DateField(
        null=True,
        blank=True,
    )

    fecha_registro = models.DateTimeField(
    auto_now_add=True,
    )

    class Meta:
        managed = False
        db_table = "activo"

    def __str__(self):
        return self.codigo_inventario


class CodigoQR(models.Model):
    id_qr = models.AutoField(primary_key=True)
    id_activo = models.OneToOneField(Activo, models.DO_NOTHING, db_column="id_activo")
    payload_qr = models.TextField(unique=True)
    formato_imagen = models.CharField(max_length=20, default="PNG")
    fecha_generacion = models.DateTimeField(auto_now_add=True)
    veces_reimpreso = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = "codigo_qr"
