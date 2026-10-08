"""
Comando de gestión Django para el bootstrap inicial del primer Administrador de SIGET.

Uso:
    python manage.py primer_admin --email admin@ejemplo.cl --rut 12.345.678-9 [--nombres ...] [--apellidos ...]
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from usuarios.services import (
    ROL_ADMINISTRADOR,
    AprovisionamientoError,
    Auth0ManagementError,
    BootstrapAdminError,
    DuplicadoUsuarioError,
    ErrorAprovisionamientoPostgreSQLError,
    RolNoEncontradoError,
    bootstrap_primer_admin,
)


class Command(BaseCommand):
    help = (
        "Crea de forma controlada el primer Administrador del sistema en SIGET "
        "mediante Auth0 Management API y vinculación RBAC en PostgreSQL."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            "-e",
            required=True,
            dest="email",
            help="Correo electrónico institucional del Administrador (obligatorio).",
        )
        parser.add_argument(
            "--rut",
            "-r",
            required=True,
            dest="rut",
            help="RUT chileno del Administrador (ej: 12.345.678-9 o 12345678-9, obligatorio).",
        )
        parser.add_argument(
            "--nombres",
            "--nombre",
            default="Administrador",
            dest="nombres",
            help="Nombres del Administrador (opcional, por defecto 'Administrador').",
        )
        parser.add_argument(
            "--apellidos",
            "--apellido",
            default="del Sistema",
            dest="apellidos",
            help="Apellidos del Administrador (opcional, por defecto 'del Sistema').",
        )

    def handle(self, *args: Any, **options: Any):
        email = options.get("email")
        rut = options.get("rut")
        nombres = options.get("nombres") or "Administrador"
        apellidos = options.get("apellidos") or "del Sistema"

        datos = {
            "email": email,
            "rut": rut,
            "nombres": nombres,
            "apellidos": apellidos,
        }

        try:
            admin_usuario, correo_enviado = bootstrap_primer_admin(datos)
        except BootstrapAdminError as exc:
            raise CommandError(str(exc)) from exc
        except RolNoEncontradoError as exc:
            raise CommandError(str(exc)) from exc
        except DuplicadoUsuarioError as exc:
            raise CommandError(str(exc)) from exc
        except ErrorAprovisionamientoPostgreSQLError as exc:
            raise CommandError(str(exc)) from exc
        except AprovisionamientoError as exc:
            raise CommandError(str(exc)) from exc
        except Auth0ManagementError as exc:
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            raise CommandError(
                f"Error inesperado durante el bootstrap del Administrador: {exc}"
            ) from exc

        self.stdout.write(
            self.style.SUCCESS("Primer Administrador creado correctamente.")
        )
        self.stdout.write(f"ID Usuario: {admin_usuario.id_usuario}")
        self.stdout.write(f"Correo: {admin_usuario.correo}")
        self.stdout.write(f"RUT: {admin_usuario.rut}")
        self.stdout.write(f"Rol: {ROL_ADMINISTRADOR}")
        self.stdout.write(f"Identificador Auth0: {admin_usuario.identificador_externo}")

        if correo_enviado:
            self.stdout.write(
                self.style.SUCCESS(
                    "Se solicitó el envío del correo para configurar la contraseña."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "Advertencia: No se pudo solicitar el correo de configuración de contraseña. "
                    "La cuenta fue creada de forma consistente en Auth0 y PostgreSQL. "
                    "El Administrador puede solicitar recuperación de acceso posteriormente."
                )
            )
