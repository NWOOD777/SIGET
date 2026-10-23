"""Formularios de entrada del portal para E5-H13 y E5-H30."""

from typing import cast

from django import forms
from rest_framework import exceptions

from activos.models import Activo
from tickets.selectors import activos_reportables_por_usuario
from tickets.services import limpiar_comentario_csat, validar_calificacion_csat

OPCIONES_CALIFICACION_CSAT = [
    ("", "Seleccione una calificación (1 a 5 estrellas)"),
    (1, "1 estrella — Muy insatisfecho"),
    (2, "2 estrellas — Insatisfecho"),
    (3, "3 estrellas — Neutral"),
    (4, "4 estrellas — Satisfecho"),
    (5, "5 estrellas — Muy satisfecho"),
]


class CalificacionEstrellasField(forms.Field):
    """Campo de formulario que valida estrictamente enteros de 1 a 5 sin truncar decimales."""

    default_error_messages = {
        "required": "La calificación en estrellas es obligatoria.",
        "invalid": "Ingrese un número entero válido entre 1 y 5.",
        "invalid_choice": "La calificación debe estar entre 1 y 5 estrellas.",
    }

    def clean(self, value) -> int:
        if value is None or (isinstance(value, str) and not value.strip()):
            raise forms.ValidationError(self.error_messages["required"], code="required")
        try:
            return validar_calificacion_csat(value)
        except exceptions.ValidationError as exc:
            codigos = exc.get_codes()
            codigo = (
                codigos.get("calificacion_estrellas", ["invalid"])[0]
                if isinstance(codigos, dict)
                else "invalid"
            )
            if codigo == "out_of_range":
                raise forms.ValidationError(
                    self.error_messages["invalid_choice"], code="invalid_choice"
                ) from exc
            if codigo == "required":
                raise forms.ValidationError(
                    self.error_messages["required"], code="required"
                ) from exc
            raise forms.ValidationError(self.error_messages["invalid"], code="invalid") from exc


class EvaluacionCSATForm(forms.Form):
    """Formulario de calificación CSAT (E5-H30) para un ticket Cerrado propio."""

    calificacion_estrellas = CalificacionEstrellasField(
        label="Calificación del servicio (1 a 5 estrellas)",
        required=True,
        widget=forms.Select(
            choices=OPCIONES_CALIFICACION_CSAT,
            attrs={"class": "form-input"},
        ),
    )
    comentario = forms.CharField(
        label="Comentario adicional (opcional)",
        required=False,
        strip=True,
        widget=forms.Textarea(
            attrs={
                "class": "form-input",
                "rows": 3,
                "placeholder": "Comparte tu opinión sobre la atención recibida (opcional).",
            }
        ),
    )

    def clean_comentario(self) -> str | None:
        return limpiar_comentario_csat(self.cleaned_data.get("comentario"))



class ActivoTicketChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.codigo_inventario} — {obj.id_modelo.nombre}"


class TicketCreateForm(forms.Form):
    """Recoge el incidente y un activo opcional autorizado para el solicitante."""

    asunto = forms.CharField(
        label="Asunto",
        required=True,
        max_length=200,
        strip=True,
        widget=forms.TextInput(attrs={"class": "form-input"}),
        error_messages={
            "required": "El asunto del ticket es obligatorio.",
            "max_length": "El asunto no puede superar los 200 caracteres.",
        },
    )
    descripcion = forms.CharField(
        label="Descripción",
        required=True,
        strip=True,
        widget=forms.Textarea(attrs={"class": "form-input", "rows": 4}),
        error_messages={"required": "La descripción del ticket es obligatoria."},
    )
    id_activo = ActivoTicketChoiceField(
        label="Equipo relacionado (opcional)",
        queryset=Activo.objects.none(),
        required=False,
        empty_label="Sin equipo específico",
        widget=forms.Select(attrs={"class": "form-input"}),
        error_messages={
            "invalid_choice": "Seleccione un equipo con asignación Activa a su nombre o deje la opción sin equipo específico.",
        },
    )

    @property
    def campo_activo(self) -> ActivoTicketChoiceField:
        return cast(ActivoTicketChoiceField, self.fields["id_activo"])

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Sin identidad explícita no se ofrecen activos. ModelChoiceField
        # consulta este queryset al validar el ID recibido en cada POST.
        self.campo_activo.queryset = activos_reportables_por_usuario(usuario)
