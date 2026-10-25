# Acceso, usuarios, roles y permisos

Servicios compartidos del backend para identificar cuentas y administrar sus permisos. Se documentan en forma transversal a las dos APIs propias. El Administrador gestiona usuarios y RBAC; cada cuenta activa puede consultar su identidad y permisos propios.

Las rutas de acceso Web devuelven páginas o redirecciones. `/admin/` es el panel técnico de Django y requiere una cuenta administrativa Django independiente de los roles SIGET.

| Métodos | Ruta | Documento |
|---|---|---|
| GET | `/api/usuarios/me/` | [Consultar identidad y acceso propios](identidad_actual.md) |
| GET | `/api/usuarios/` | [Consultar usuarios](listado_usuarios.md) |
| POST | `/api/usuarios/aprovisionar/` | [Aprovisionar un usuario](aprovisionar.md) |
| PATCH, DELETE | `/api/usuarios/{id}/` | [Administrar estado y eliminación de cuentas](administracion_cuentas.md) |
| PATCH | `/api/usuarios/{id}/identificacion/` | [Corregir identificación institucional](acceso_usuario.md) |
| GET | `/api/usuarios/{id}/acceso/` | [Consultar acceso de un usuario](acceso_usuario.md) |
| POST | `/api/usuarios/{id}/roles/` | [Actualizar roles de un usuario](asignar_roles.md) |
| DELETE | `/api/usuarios/{id}/roles/{id_rol}/` | [Retirar un rol de un usuario](retirar_rol.md) |
| GET | `/api/usuarios/roles/` | [Consultar roles y sus permisos](catalogo_roles.md) |
| POST | `/api/usuarios/roles/{id_rol}/permisos/` | [Asociar un permiso a un rol](asignar_permiso.md) |
| DELETE | `/api/usuarios/roles/{id_rol}/permisos/{id_permiso}/` | [Retirar un permiso de un rol](retirar_permiso.md) |
| GET | `/` | [Acceder al portal](web/inicio.md) |
| GET | `/mis-equipos/` y `/mis-equipos/{id_asignacion}/` | [Mis equipos y su detalle](web/mis_equipos.md) |
| GET, POST | `/notificaciones/`, `/notificaciones/{id}/`, `/notificaciones/{id}/leer/` y `/notificaciones/{id}/abrir/` | [Centro de notificaciones en plataforma](web/notificaciones.md) |
| GET | `/perfil/` | [Mi perfil](web/perfil.md) |
| GET | `/solicitudes/{id}/` y `/tickets/{id}/` | [Detalles de solicitudes y tickets](web/detalles.md) |
| GET | `/auth/login/` | [Iniciar sesión Web](web/login.md) |
| GET | `/auth/callback/` | [Completar el acceso Web](web/callback.md) |
| GET | `/auth/logout/` | [Cerrar sesión Web](web/logout.md) |
| GET, POST | `/auth/recover/` | [Recuperar acceso](web/recuperar_acceso.md) |

[Índice general](../README.md)
