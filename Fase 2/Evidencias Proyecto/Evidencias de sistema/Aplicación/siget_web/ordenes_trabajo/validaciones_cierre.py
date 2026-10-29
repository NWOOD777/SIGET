"""Validación de contenido; no persiste ni cambia estados de dominio."""

from django.core.exceptions import ValidationError

REPARACION_EXITOSA = "REPARACION_EXITOSA"
NO_REPARABLE = "NO_REPARABLE"
RESULTADOS_CIERRE = ((REPARACION_EXITOSA, "Reparación exitosa"), (NO_REPARABLE, "No reparable"))

# Conjunto explícito de 29 caracteres: equivalente a str.isspace() en Python 3.12.
# El CHECK SQL usa exactamente este conjunto, sin depender de lc_ctype.
ESPACIOS_CIERRE = "\u0009\u000a\u000b\u000c\u000d\u001c\u001d\u001e\u001f\u0020\u0085\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000"


def validar_contenido_cierre(*, resultado, solucion_aplicada=None, pruebas_realizadas=None, informe_descarte=None):
    errores = {}
    if not isinstance(resultado, str) or resultado not in dict(RESULTADOS_CIERRE):
        errores["resultado"] = "El resultado de cierre no es válido."
    textos = {
        "solucion_aplicada": solucion_aplicada,
        "pruebas_realizadas": pruebas_realizadas,
        "informe_descarte": informe_descarte,
    }
    obligatorios = {
        REPARACION_EXITOSA: ("solucion_aplicada", "pruebas_realizadas"),
        NO_REPARABLE: ("informe_descarte",),
    }.get(resultado if isinstance(resultado, str) else "", ())
    for campo, valor in textos.items():
        if valor is not None and not isinstance(valor, str):
            errores[campo] = "Debe ingresar un texto."
        elif campo in obligatorios and (valor is None or not valor.strip(ESPACIOS_CIERRE)):
            errores[campo] = "Este campo es obligatorio para el resultado seleccionado."
    if errores:
        raise ValidationError(errores)
