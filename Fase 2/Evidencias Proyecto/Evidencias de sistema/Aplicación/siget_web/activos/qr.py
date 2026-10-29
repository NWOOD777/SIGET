"""Generación QR para los activos registrados en el inventario."""

from .models import Activo
from .qr_client import ErrorGeneracionQR, ImagenQR, generar_qr


def generar_qr_activo(activo: Activo) -> ImagenQR:
    """Genera la imagen sin modificar el activo ni su información persistida."""
    if activo.pk is None or activo._state.adding:
        raise ErrorGeneracionQR("El activo debe estar registrado en el inventario.", codigo="activo_no_registrado")
    return generar_qr(activo.codigo_inventario)
