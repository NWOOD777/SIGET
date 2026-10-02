"""
Formularios para el módulo de usuarios en SIGET.
Define los formularios de interacción no acoplados a modelos locales (E1-H2).
"""
from django import forms


class RecuperarAccesoForm(forms.Form):
    """
    Formulario sencillo para solicitar recuperación de acceso institucional.
    Valida el formato básico del correo electrónico sin interactuar con la base de datos local.
    """
    correo = forms.EmailField(
        label="Correo electrónico",
        max_length=254,
        widget=forms.EmailInput(
            attrs={
                "class": "form-input",
                "placeholder": "ejemplo@duocuc.cl",
                "autocomplete": "email",
                "required": "required",
                "id": "id_correo",
            }
        ),
        error_messages={
            "required": "Por favor, ingresa tu correo electrónico institucional.",
            "invalid": "Ingresa una dirección de correo electrónico válida.",
        },
    )


