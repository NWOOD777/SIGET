"""Perfiles locales para separar sesiones del escritorio en un mismo equipo."""

import re

_perfil_actual = ""


def validar_perfil(nombre: str) -> str:
    nombre = nombre.lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,39}", nombre, flags=re.ASCII):
        raise ValueError("Use entre 1 y 40 letras sin acentos, números, guiones o guiones bajos.")
    return nombre


def configurar_perfil(nombre: str = "") -> None:
    global _perfil_actual
    _perfil_actual = validar_perfil(nombre) if nombre else ""


def nombre_perfil() -> str:
    return _perfil_actual


def carpeta_perfil() -> str:
    return f"perfil-{_perfil_actual}" if _perfil_actual else ""


def titulo_con_perfil(titulo: str) -> str:
    return f"{titulo} [{_perfil_actual}]" if _perfil_actual else titulo
