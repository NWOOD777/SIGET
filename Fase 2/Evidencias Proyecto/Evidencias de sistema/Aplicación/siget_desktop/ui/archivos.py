"""Ubicación inicial para guardar archivos exportados."""

from pathlib import Path

from PySide6.QtCore import QStandardPaths


def ruta_exportacion(nombre_archivo: str) -> str:
    """Propone Documentos del usuario o su carpeta personal si no existe."""
    documentos = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.DocumentsLocation
    )
    carpeta = Path(documentos) if documentos else Path.home()
    if not carpeta.is_dir():
        carpeta = Path.home()
    return str(carpeta / nombre_archivo)
