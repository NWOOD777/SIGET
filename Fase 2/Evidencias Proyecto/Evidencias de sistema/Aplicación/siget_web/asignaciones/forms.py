"""Formulario web de E3-H7; la creación corresponde al servicio existente."""

from typing import cast

from django import forms

from activos.models import Activo, CategoriaActivo
from asignaciones.services import ESTADO_ACTIVO_DISPONIBLE


class SolicitudAsignacionForm(forms.Form):
    """Selecciona una categoría disponible y recoge el motivo, sin persistir."""

    id_categoria = forms.ModelChoiceField(
        label="Categoría de equipo",
        queryset=CategoriaActivo.objects.none(),
        empty_label="Seleccione una categoría",
        error_messages={
            "required": "Seleccione una categoría de equipo.",
            "invalid_choice": "Seleccione una categoría con equipos disponibles.",
        },
    )
    motivo = forms.CharField(
        label="Motivo de la solicitud",
        required=True,
        strip=True,
        widget=forms.Textarea(attrs={"rows": 4}),
        error_messages={"required": "El motivo de la solicitud es obligatorio."},
    )

    @property
    def campo_categoria(self) -> forms.ModelChoiceField:
        return cast(forms.ModelChoiceField, self.fields["id_categoria"])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        categorias_disponibles = Activo.objects.filter(
            id_estado_activo__nombre=ESTADO_ACTIVO_DISPONIBLE,
        ).values_list("id_modelo__id_categoria", flat=True)
        self.campo_categoria.queryset = CategoriaActivo.objects.filter(
            pk__in=categorias_disponibles,
        ).order_by("nombre")

    # ModelChoiceField devuelve CategoriaActivo en cleaned_data["id_categoria"].
    # La futura vista pasará su pk al servicio, que revalida stock y duplicados.
