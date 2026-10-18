"""Formulario de entrada del portal para E5-H13."""

from typing import cast

from django import forms

from activos.models import Activo
from tickets.selectors import activos_reportables_por_usuario


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
