"""
Rutas URL para la API REST de administración RBAC y aprovisionamiento (E1-H3).
Consumidas por la aplicación PySide6 y clientes administrativos autorizados.
"""
from django.urls import path

from usuarios import api_views

app_name = "usuarios_api"

urlpatterns = [
    # Gestión de usuarios
    path("", api_views.UsuarioListAPIView.as_view(), name="usuario_list"),
    path("aprovisionar/", api_views.UsuarioAprovisionarAPIView.as_view(), name="usuario_aprovisionar"),
    path("<int:pk>/acceso/", api_views.UsuarioAccesoDetailAPIView.as_view(), name="usuario_acceso_detail"),
    path("<int:pk>/roles/", api_views.UsuarioRolesAPIView.as_view(), name="usuario_roles"),
    path("<int:pk>/roles/<int:id_rol>/", api_views.UsuarioRolDeleteAPIView.as_view(), name="usuario_rol_delete"),

    # Gestión de catálogo RBAC (Roles y Permisos)
    path("roles/", api_views.RolListAPIView.as_view(), name="rol_list"),
    path("roles/<int:id_rol>/permisos/", api_views.RolPermisoManageAPIView.as_view(), name="rol_permiso_add"),
    path("roles/<int:id_rol>/permisos/<int:id_permiso>/", api_views.RolPermisoManageAPIView.as_view(), name="rol_permiso_delete"),
]
