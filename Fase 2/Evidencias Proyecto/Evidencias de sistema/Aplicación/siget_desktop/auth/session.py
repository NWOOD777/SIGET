"""
Gestión de sesión del usuario en memoria para el cliente PySide6.
Garantiza que los tokens y datos de autorización se almacenen de forma controlada
y se eliminen limpiamente al cerrar sesión.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class UserSession:
    """Representa la sesión activa del usuario autenticado."""

    access_token: str | None = None
    id_token: str | None = None
    token_type: str = "Bearer"
    expires_at: float = 0.0
    generation: int = 0

    # Ficha del usuario obtenida desde el backend Django (/api/usuarios/me/)
    id_usuario: int | None = None
    nombres: str = ""
    apellidos: str = ""
    nombre_completo: str = ""
    correo: str = ""
    roles: list[str] = field(default_factory=list)
    permisos: list[str] = field(default_factory=list)
    acceso_escritorio: bool = False

    def is_authenticated(self) -> bool:
        """Determina si existe una sesión válida y con token no expirado."""
        return bool(self.access_token) and not self.is_expired()

    def is_expired(self, leeway_seconds: int = 30) -> bool:
        """
        Verifica si el token expiró o está dentro del margen de expiración inminente.
        """
        if not self.expires_at:
            return False
        return time.time() >= (self.expires_at - leeway_seconds)

    def set_tokens(self, access_token: str, expires_in: int, id_token: str | None = None):
        """Registra los tokens devueltos por el proveedor."""
        self.generation += 1
        self.access_token = access_token
        self.id_token = id_token
        self.expires_at = time.time() + max(0, float(expires_in))

    def update_user_info(self, data: dict[str, Any]):
        """Actualiza la identidad y permisos efectivos recibidos desde /api/usuarios/me/."""
        self.id_usuario = data.get("id_usuario")
        self.nombres = data.get("nombres", "")
        self.apellidos = data.get("apellidos", "")
        self.nombre_completo = data.get("nombre_completo", "")
        self.correo = data.get("correo", "")
        self.roles = list(data.get("roles", []))
        self.permisos = list(data.get("permisos", []))
        self.acceso_escritorio = bool(data.get("acceso_escritorio", False))

    def has_role(self, nombre_rol: str) -> bool:
        """Verifica si el usuario posee un rol específico."""
        return nombre_rol in self.roles

    def is_admin(self) -> bool:
        return "Administrador del sistema" in self.roles

    def is_tecnico(self) -> bool:
        return "Técnico de soporte" in self.roles

    def has_permission(self, codigo_permiso: str) -> bool:
        """Verifica si el usuario posee un permiso efectivo específico."""
        return codigo_permiso in self.permisos

    def clear(self):
        """Limpia completamente el estado de la sesión en memoria."""
        from siget_desktop.auth.cache import eliminar_cache
        eliminar_cache()
        self.generation += 1
        self.access_token = None
        self.id_token = None
        self.expires_at = 0.0
        self.id_usuario = None
        self.nombres = ""
        self.apellidos = ""
        self.nombre_completo = ""
        self.correo = ""
        self.roles.clear()
        self.permisos.clear()
        self.acceso_escritorio = False


# Instancia singleton para la sesión de la aplicación de escritorio
current_session = UserSession()
