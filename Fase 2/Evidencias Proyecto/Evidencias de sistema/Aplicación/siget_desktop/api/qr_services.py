"""Solicitudes de etiquetas QR al backend de SIGET."""

from threading import Event
from typing import Any

from siget_desktop.api.client import ApiError, ForbiddenApiError, ServerApiError, TokenExpiredApiError, api_client
from siget_desktop.auth.session import current_session

MAX_ETIQUETAS_LOTE = 50


def obtener_estado_qr(id_activo: int) -> dict[str, Any]:
    resultado = api_client.get(f"/api/activos/{id_activo}/qr/")
    if not isinstance(resultado, dict) or resultado.get("id_activo") != id_activo or type(resultado.get("generado")) is not bool:
        raise ServerApiError("El servidor devolvió un estado QR inválido.")
    return resultado


def generar_etiqueta_qr(id_activo: int, *, reimprimir: bool = False) -> dict[str, Any]:
    resultado = api_client.request("POST", f"/api/activos/{id_activo}/qr/", json={"reimprimir": reimprimir}, timeout=max(api_client.timeout, 130))
    if (
        not isinstance(resultado, dict)
        or resultado.get("id_activo") != id_activo
        or not isinstance(resultado.get("svg"), str)
        or not 0 < len(resultado["svg"].encode("utf-8")) <= 1024 * 1024
        or resultado.get("formato_imagen") != "SVG"
        or not resultado.get("payload_qr")
        or resultado.get("payload_qr") != resultado.get("codigo_inventario")
    ):
        raise ServerApiError("El servidor devolvió una etiqueta QR incompleta o inválida.")
    return resultado


def generar_etiquetas_qr(ids: list[int], *, reimprimir: bool = False, cancelacion: Event | None = None) -> dict[str, list[dict[str, Any]]]:
    if not 1 <= len(ids) <= MAX_ETIQUETAS_LOTE or any(type(pk) is not int or pk <= 0 for pk in ids) or len(set(ids)) != len(ids):
        raise ValueError(f"Seleccione entre 1 y {MAX_ETIQUETAS_LOTE} activos diferentes.")
    generation = current_session.generation
    etiquetas = []
    errores = []
    for pk in ids:
        if cancelacion is not None and cancelacion.is_set():
            break
        if generation != current_session.generation or not current_session.is_authenticated():
            raise TokenExpiredApiError("La sesión terminó durante la generación del lote.")
        if not current_session.is_admin():
            raise ForbiddenApiError("La generación QR requiere acceso de Administrador.")
        try:
            etiquetas.append(generar_etiqueta_qr(pk, reimprimir=reimprimir))
        except (TokenExpiredApiError, ForbiddenApiError):
            raise
        except ApiError as exc:
            errores.append({"id_activo": pk, "detail": str(exc)})
    return {"etiquetas": etiquetas, "errores": errores}
