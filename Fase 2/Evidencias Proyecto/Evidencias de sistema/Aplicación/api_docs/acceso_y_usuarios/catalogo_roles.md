# Consultar roles y sus permisos

Ruta: `/api/usuarios/roles/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `GET` | Administrador del sistema. | `200`, lista de roles. |

No recibe cuerpo. Cada registro incluye `id_rol`, `nombre`, `descripcion` y `permisos`. Los permisos se muestran con identificador, código y descripción.

Esta ruta consulta el catálogo; no crea roles nuevos.

Consulta [autenticación y uso general](../uso_general.md) y [respuestas y errores](../respuestas_y_errores.md).

[Volver a acceso y usuarios](README.md) · [Índice general](../README.md)
