"""Cola persistente de notificaciones sobre la tabla externa de SIGET."""

from typing import TYPE_CHECKING

from django.db import models
from django.utils import timezone

CANAL_PLATAFORMA = "PLATAFORMA"
CANAL_CORREO_API = "CORREO_API"
CANAL_AMBOS = "AMBOS"
CANALES_PLATAFORMA = (CANAL_PLATAFORMA, CANAL_AMBOS)


class Notificacion(models.Model):
    if TYPE_CHECKING:
        id_usuario_id: int

    id_notificacion = models.AutoField(primary_key=True)
    id_usuario = models.ForeignKey("usuarios.Usuario", on_delete=models.CASCADE, db_column="id_usuario")
    modulo_origen = models.CharField(max_length=50)
    titulo = models.CharField(max_length=150)
    mensaje = models.TextField()
    canal = models.CharField(max_length=20, default=CANAL_CORREO_API)
    leida = models.BooleanField(default=False)
    estado_envio = models.CharField(max_length=20, default="PENDIENTE")
    intentos_envio = models.SmallIntegerField(default=0)
    ultimo_error = models.TextField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(default=timezone.now)
    fecha_ultimo_intento = models.DateTimeField(null=True, blank=True)
    fecha_envio = models.DateTimeField(null=True, blank=True)
    clave_evento = models.CharField(max_length=255, unique=True, null=True, blank=True)
    datos_envio = models.JSONField(default=dict)
    referencia = models.JSONField(default=dict)
    id_proveedor = models.CharField(max_length=100, null=True, blank=True)
    reintento_permitido = models.BooleanField(default=True)
    proximo_intento = models.DateTimeField(null=True, blank=True)
    fecha_primer_intento = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "notificacion"
