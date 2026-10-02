from django.db import models
from django.utils import timezone


class Rol(models.Model):
    id_rol = models.AutoField(primary_key=True)

    nombre = models.CharField(
        unique=True,
        max_length=50,
        db_comment=(
            "Roles canónicos: Usuario solicitante, "
            "Técnico de soporte, Administrador del sistema."
        ),
    )

    descripcion = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    class Meta:
        managed = False
        db_table = "rol"
        db_table_comment = "Catálogo de roles oficiales para control de acceso RBAC."

    def __str__(self):
        return self.nombre


class Permiso(models.Model):
    id_permiso = models.AutoField(primary_key=True)

    codigo = models.CharField(
        unique=True,
        max_length=50,
    )

    descripcion = models.CharField(
        max_length=255,
    )

    class Meta:
        managed = False
        db_table = "permiso"
        db_table_comment = (
            "Catálogo de permisos granulares sobre módulos, "
            "operaciones y endpoints de SIGET."
        )

    def __str__(self):
        return self.codigo


class Usuario(models.Model):
    id_usuario = models.AutoField(primary_key=True)

    identificador_externo = models.CharField(
        unique=True,
        max_length=255,
        db_comment=(
            "Identificador único entregado por el proveedor externo de identidad."
        ),
    )

    proveedor_identidad = models.CharField(
        max_length=100,
        db_comment="Nombre lógico del proveedor de identidad integrado.",
    )

    rut = models.CharField(
        unique=True,
        max_length=12,
        db_comment=(
            "Identificador institucional utilizado para trazabilidad y documentación."
        ),
    )

    nombres = models.CharField(
        max_length=100,
    )

    apellidos = models.CharField(
        max_length=100,
    )

    correo = models.EmailField(
        unique=True,
        max_length=150,
        db_comment=(
            "Correo del usuario; no constituye una contraseña ni "
            "una credencial almacenada por SIGET."
        ),
    )

    activo = models.BooleanField(
        default=True,
        db_comment=("Indica si el perfil local está habilitado para operar en SIGET."),
    )

    fecha_creacion = models.DateTimeField(
        default=timezone.now,
    )

    class Meta:
        managed = False
        db_table = "usuario"
        db_table_comment = (
            "Directorio local de usuarios de SIGET vinculado "
            "a un proveedor externo de identidad."
        )

    def __str__(self):
        return f"{self.nombres} {self.apellidos}"

    @property
    def is_active(self):
        return self.activo

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_username(self):
        return self.correo


class UsuarioRol(models.Model):
    id_usuario_rol = models.AutoField(primary_key=True)

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        db_column="id_usuario",
        related_name="asignaciones_rol",
    )

    rol = models.ForeignKey(
        Rol,
        on_delete=models.RESTRICT,
        db_column="id_rol",
        related_name="usuarios_asignados",
    )

    fecha_asignacion = models.DateTimeField(
        default=timezone.now,
    )

    class Meta:
        managed = False
        db_table = "usuario_rol"
        unique_together = (("usuario", "rol"),)
        db_table_comment = "Relación N:M entre usuarios y roles RBAC."

    def __str__(self):
        return f"{self.usuario} - {self.rol}"


class RolPermiso(models.Model):
    id_rol_permiso = models.AutoField(primary_key=True)

    rol = models.ForeignKey(
        Rol,
        on_delete=models.CASCADE,
        db_column="id_rol",
        related_name="asignaciones_permiso",
    )

    permiso = models.ForeignKey(
        Permiso,
        on_delete=models.RESTRICT,
        db_column="id_permiso",
        related_name="asignaciones_rol",
    )

    class Meta:
        managed = False
        db_table = "rol_permiso"
        unique_together = (("rol", "permiso"),)
        db_table_comment = "Relación N:M entre roles y permisos."

    def __str__(self):
        return f"{self.rol} - {self.permiso}"
