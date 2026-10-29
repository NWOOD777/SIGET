"""Comprueba la conexión y la respuesta vectorial del proveedor QR."""

from hashlib import sha256
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from activos.qr_client import ErrorGeneracionQR, generar_qr


class Command(BaseCommand):
    help = "Verifica QR Server con un código de inventario sin modificar la base de datos."

    def add_arguments(self, parser):
        parser.add_argument("--codigo", required=True, help="Código de inventario que se codificará.")
        parser.add_argument("--salida", type=Path, help="Ruta de salida SVG. Debe ser un archivo nuevo.")

    def handle(self, *args, **options):
        destino = options["salida"]
        if destino is not None and (destino.exists() or destino.suffix.lower() != ".svg" or not destino.parent.is_dir()):
            raise CommandError("La salida debe ser un archivo .svg nuevo dentro de una carpeta existente.")
        try:
            imagen = generar_qr(options["codigo"])
        except ErrorGeneracionQR as exc:
            raise CommandError(str(exc)) from None
        if destino is not None:
            try:
                with destino.open("xb") as archivo:
                    archivo.write(imagen.contenido)
            except OSError:
                raise CommandError("No se pudo guardar la imagen SVG.") from None
        self.stdout.write(self.style.SUCCESS(f"QR Server: SVG recibido y validado ({len(imagen.contenido)} bytes)."))
        self.stdout.write(f"SHA-256: {sha256(imagen.contenido).hexdigest()}")
