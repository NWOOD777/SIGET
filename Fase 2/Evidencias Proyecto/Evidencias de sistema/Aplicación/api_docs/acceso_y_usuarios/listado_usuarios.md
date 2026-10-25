# Consultar usuarios

Ruta: `/api/usuarios/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `GET` | Administrador del sistema. | `200`, lista de usuarios. |

No recibe cuerpo ni filtros de búsqueda específicos. Entrega `id_usuario`, `nombres`, `apellidos`, `correo`, `activo`, `fecha_creacion` y `roles`. `roles` contiene los nombres asignados.

El detalle de permisos se obtiene en la [consulta de acceso](acceso_usuario.md).

Consultar [autenticación y uso general](../uso_general.md) y [respuestas y errores](../respuestas_y_errores.md).

[Volver a acceso y usuarios](README.md) · [Índice general](../README.md)
