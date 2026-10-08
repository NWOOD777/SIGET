"""
Serializadores DRF para aprovisionamiento, consulta y gestión RBAC de usuarios.
"""

from rest_framework import serializers

from usuarios.models import Usuario, UsuarioRol
from usuarios.services import (
    ROL_ADMINISTRADOR,
    ROL_TECNICO,
    ROL_USUARIO_SOLICITANTE,
)


class UsuarioListItemSerializer(serializers.ModelSerializer):
    """
    Serializador para listar usuarios del sistema con sus roles asociados.
    """

    roles = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = [
            "id_usuario",
            "identificador_externo",
            "proveedor_identidad",
            "rut",
            "nombres",
            "apellidos",
            "correo",
            "activo",
            "fecha_creacion",
            "roles",
        ]

    def get_roles(self, obj: Usuario) -> list[str]:
        return list(
            UsuarioRol.objects.filter(usuario=obj).values_list("rol__nombre", flat=True)
        )


class UsuarioAprovisionarSerializer(serializers.Serializer):
    """
    Serializador de entrada para el aprovisionamiento administrativo de nuevos usuarios.
    """

    nombres = serializers.CharField(max_length=100)
    apellidos = serializers.CharField(max_length=100)
    correo = serializers.EmailField(max_length=150)
    rut = serializers.CharField(max_length=12)
    rol = serializers.ChoiceField(
        choices=[
            (ROL_USUARIO_SOLICITANTE, ROL_USUARIO_SOLICITANTE),
            (ROL_TECNICO, ROL_TECNICO),
            (ROL_ADMINISTRADOR, ROL_ADMINISTRADOR),
        ]
    )


class AsignarRolesSerializer(serializers.Serializer):
    """
    Serializador para asignar o reemplazar la lista de roles de un usuario.
    """

    roles = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=False,
    )


class AsignarPermisoSerializer(serializers.Serializer):
    """
    Serializador para asignar un permiso a un rol.
    """

    id_permiso = serializers.IntegerField(required=False)
    codigo = serializers.CharField(required=False)

    def validate(self, attrs):
        if not attrs.get("id_permiso") and not attrs.get("codigo"):
            raise serializers.ValidationError(
                "Debe especificar 'id_permiso' o 'codigo'."
            )
        return attrs
