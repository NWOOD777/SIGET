"""Generación y asociación de etiquetas QR a los activos del inventario."""

from django.db import transaction
from rest_framework.exceptions import APIException, NotFound

from .models import Activo, CodigoQR
from .qr_client import ErrorGeneracionQR, ImagenQR, generar_qr
from .serializers import auditar_evento_activos


class ConflictoEtiquetaQR(APIException):
    status_code = 409
    default_detail = "La etiqueta no coincide con el identificador actual del activo."


def generar_qr_activo(activo: Activo) -> ImagenQR:
    """Obtiene la imagen sin modificar el activo ni su información persistida."""
    if activo.pk is None or activo._state.adding:
        raise ErrorGeneracionQR("El activo debe estar registrado en el inventario.", codigo="activo_no_registrado")
    return generar_qr(activo.codigo_inventario)


def datos_etiqueta(qr: CodigoQR) -> dict:
    return {
        "id_qr": qr.pk,
        "payload_qr": qr.payload_qr,
        "formato_imagen": qr.formato_imagen,
        "fecha_generacion": qr.fecha_generacion.isoformat(),
        "veces_reimpreso": qr.veces_reimpreso,
    }


def obtener_activo_qr(pk: int) -> Activo:
    try:
        return Activo.objects.get(pk=pk)
    except Activo.DoesNotExist:
        raise NotFound("Activo no encontrado.") from None


def preparar_etiqueta(pk: int, request, *, reimprimir: bool = False) -> dict:
    activo = obtener_activo_qr(pk)
    anterior = CodigoQR.objects.filter(id_activo=activo).first()
    if reimprimir and anterior is None:
        raise NotFound("El activo todavía no tiene una etiqueta QR. Genérela primero.")
    payload = anterior.payload_qr if anterior else activo.codigo_inventario
    if payload != activo.codigo_inventario:
        raise ConflictoEtiquetaQR()

    # La llamada externa termina antes de abrir la transacción de persistencia.
    imagen = generar_qr_activo(activo) if anterior is None else generar_qr(payload)
    with transaction.atomic():
        try:
            actual = Activo.objects.select_for_update().get(pk=pk)
        except Activo.DoesNotExist:
            raise NotFound("El activo ya no existe.") from None
        if actual.codigo_inventario != imagen.payload:
            raise ConflictoEtiquetaQR()
        qr = CodigoQR.objects.filter(id_activo=actual).first()
        if qr is not None and qr.payload_qr != imagen.payload:
            raise ConflictoEtiquetaQR()
        creado = qr is None
        if creado:
            if reimprimir:
                raise NotFound("La etiqueta QR ya no existe. Genérela primero.")
            qr = CodigoQR.objects.create(id_activo=actual, payload_qr=imagen.payload, formato_imagen=imagen.formato)
        if qr.formato_imagen != imagen.formato:
            qr.formato_imagen = imagen.formato
            qr.save(update_fields=["formato_imagen"])
        if reimprimir:
            if qr.veces_reimpreso >= 2147483647:
                raise ConflictoEtiquetaQR("Se alcanzó el límite del contador de reimpresiones.")
            qr.veces_reimpreso += 1
            qr.save(update_fields=["veces_reimpreso"])
        if creado or reimprimir:
            auditar_evento_activos(
                request,
                "REIMPRIMIR_QR" if reimprimir else "GENERAR_QR",
                "codigo_qr",
                qr.pk,
                f"Etiqueta del activo #{actual.pk}; identificador {qr.payload_qr}.",
            )
        resultado = {
            "id_activo": actual.pk,
            "codigo_inventario": actual.codigo_inventario,
            "numero_serie": actual.numero_serie,
            "marca": actual.id_modelo.id_marca.nombre,
            "modelo": actual.id_modelo.nombre,
            **datos_etiqueta(qr),
            "svg": imagen.contenido.decode("utf-8"),
        }
    return resultado
