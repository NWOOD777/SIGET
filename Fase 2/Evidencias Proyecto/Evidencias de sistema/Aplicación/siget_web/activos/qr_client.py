"""Generación de imágenes vectoriales mediante QR Server."""

import logging
import math
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit
from xml.etree import ElementTree

import requests
from django.conf import settings

logger = logging.getLogger(__name__)
SVG_NAMESPACE = "http://www.w3.org/2000/svg"
MAX_BYTES = 1024 * 1024
PATRON_CODIGO = re.compile(r"ACT-[0-9]{4,46}\Z", re.ASCII)


class ErrorGeneracionQR(Exception):
    def __init__(self, mensaje: str, *, codigo: str, transitorio: bool = False):
        super().__init__(mensaje)
        self.codigo = codigo
        self.transitorio = transitorio


@dataclass(frozen=True)
class ImagenQR:
    payload: str
    contenido: bytes
    formato: str = field(default="SVG", init=False)
    tipo_contenido: str = field(default="image/svg+xml", init=False)


def _error_proveedor(mensaje: str, codigo: str, transitorio: bool = True) -> ErrorGeneracionQR:
    logger.warning("Generación QR: %s.", codigo)
    return ErrorGeneracionQR(mensaje, codigo=codigo, transitorio=transitorio)


def _configuracion() -> tuple[str, tuple[float, float], int]:
    url = settings.QR_SERVER_URL
    try:
        partes = urlsplit(url)
        valido = (
            partes.scheme == "https"
            and partes.hostname == "api.qrserver.com"
            and partes.path == "/v1/create-qr-code/"
            and partes.port in (None, 443)
            and partes.username is None
            and partes.password is None
            and not partes.query
            and not partes.fragment
        )
        tiempos = (settings.QR_SERVER_CONNECT_TIMEOUT_SECONDS, settings.QR_SERVER_READ_TIMEOUT_SECONDS)
        valido = valido and all(type(v) in (int, float) and math.isfinite(v) and 0 < v <= 60 for v in tiempos)
        tamano = settings.QR_SERVER_SIZE
        valido = valido and type(tamano) is int and 10 <= tamano <= 1000
    except (TypeError, ValueError):
        valido = False
    if not valido:
        raise ErrorGeneracionQR("La configuración de QR Server no es válida.", codigo="configuracion_invalida")
    return url, tiempos, tamano


def _estilo_valido(texto: str) -> bool:
    for declaracion in texto.split(";"):
        if not declaracion.strip():
            continue
        clave, separador, valor = declaracion.partition(":")
        clave, valor = clave.strip(), valor.strip()
        if not separador:
            return False
        if clave == "fill":
            if re.fullmatch(r"(?:#[0-9a-fA-F]{3,8}|rgb\([0-9.,%\s]+\)|black|white|none)", valor) is None:
                return False
        elif clave == "fill-opacity":
            try:
                if not 0 <= float(valor) <= 1:
                    return False
            except ValueError:
                return False
        else:
            return False
    return True


def _validar_svg(contenido: bytes, tamano: int) -> bytes:
    try:
        texto = contenido.decode("utf-8-sig")
        if "<!DOCTYPE" in texto.upper() or "<!ENTITY" in texto.upper():
            raise ValueError
        raiz = ElementTree.fromstring(texto)
        if raiz.tag != f"{{{SVG_NAMESPACE}}}svg":
            raise ValueError
        etiquetas = {f"{{{SVG_NAMESPACE}}}{t}" for t in ("svg", "g", "path", "rect", "title", "desc")}
        atributos = {"version", "width", "height", "viewBox", "x", "y", "d", "id", "style", "fill", "fill-opacity"}
        for indice, elemento in enumerate(raiz.iter()):
            if indice >= 512:
                raise ValueError
            if elemento.tag not in etiquetas or set(elemento.attrib) - atributos:
                raise ValueError
            estilo = elemento.get("style")
            if estilo is not None and not _estilo_valido(estilo):
                raise ValueError
            for clave in ("fill", "fill-opacity"):
                if clave in elemento.attrib and not _estilo_valido(f"{clave}:{elemento.attrib[clave]}"):
                    raise ValueError
        ancho = float(raiz.attrib["width"])
        alto = float(raiz.attrib["height"])
        if not math.isfinite(ancho) or not 0 < ancho <= 1000000 or ancho != alto:
            raise ValueError
        if raiz.get("viewBox") not in (None, f"0 0 {ancho:g} {alto:g}"):
            raise ValueError
        if not any(n.tag == f"{{{SVG_NAMESPACE}}}path" and n.get("d", "").strip() for n in raiz.iter()):
            raise ValueError
        # Mantiene las coordenadas del proveedor al ajustar el tamaño de presentación.
        raiz.set("viewBox", f"0 0 {ancho:g} {alto:g}")
        raiz.set("width", str(tamano))
        raiz.set("height", str(tamano))
        return ElementTree.tostring(raiz, encoding="utf-8", xml_declaration=True)
    except (UnicodeError, ElementTree.ParseError, ValueError, KeyError, OverflowError, RecursionError):
        raise _error_proveedor("QR Server no devolvió una imagen SVG válida.", "respuesta_invalida") from None


def generar_qr(codigo_inventario: str) -> ImagenQR:
    """Obtiene un SVG que codifica únicamente el identificador del activo."""
    if not isinstance(codigo_inventario, str) or PATRON_CODIGO.fullmatch(codigo_inventario) is None:
        raise ErrorGeneracionQR("El código de inventario no es válido.", codigo="codigo_invalido")
    url, tiempos, tamano = _configuracion()
    parametros = {
        "data": codigo_inventario,
        "size": f"{tamano}x{tamano}",
        "format": "svg",
        "ecc": "M",
        "qzone": "4",
        "charset-source": "UTF-8",
        "charset-target": "UTF-8",
    }
    try:
        with requests.post(
            url,
            data=parametros,
            headers={"Accept": "image/svg+xml"},
            timeout=tiempos,
            allow_redirects=False,
            stream=True,
        ) as respuesta:
            if respuesta.status_code != 200:
                raise _error_proveedor(
                    f"QR Server respondió HTTP {respuesta.status_code}.",
                    "error_http",
                    respuesta.status_code == 429 or respuesta.status_code >= 500,
                )
            if respuesta.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "image/svg+xml":
                raise _error_proveedor("QR Server no devolvió una imagen SVG.", "respuesta_invalida")
            longitud = respuesta.headers.get("Content-Length")
            if longitud is not None:
                try:
                    valida = 0 < int(longitud) <= MAX_BYTES
                except ValueError:
                    valida = False
                if not valida:
                    raise _error_proveedor("El tamaño de la imagen QR no es válido.", "respuesta_invalida")
            contenido = bytearray()
            for bloque in respuesta.iter_content(chunk_size=8192):
                if not isinstance(bloque, bytes) or len(contenido) + len(bloque) > MAX_BYTES:
                    raise _error_proveedor("La imagen QR supera el tamaño permitido.", "respuesta_invalida")
                contenido.extend(bloque)
    except requests.Timeout:
        raise _error_proveedor("QR Server agotó el tiempo de espera.", "tiempo_agotado") from None
    except requests.ConnectionError:
        raise _error_proveedor("No se pudo establecer conexión con QR Server.", "sin_conexion") from None
    except requests.RequestException:
        raise _error_proveedor("No se pudo completar la generación QR.", "error_red") from None
    return ImagenQR(payload=codigo_inventario, contenido=_validar_svg(bytes(contenido), tamano))
