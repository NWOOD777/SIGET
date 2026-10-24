# Consultar acceso de un usuario

Ruta: `/api/usuarios/{id}/acceso/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `GET` | Administrador del sistema. | `200`, ficha de acceso del usuario indicado. |

Entrega `id_usuario`, `identificador_externo`, `proveedor_identidad`, `rut`, `nombres`, `apellidos`, `correo`, `activo`, `fecha_creacion`, `roles` y `permisos_efectivos`.

Cada rol incluye identificador, nombre y descripción. Los permisos efectivos incluyen identificador, código y descripción. Un usuario inexistente responde `404`. Para consultar la identidad propia sin rol administrativo se utiliza [identidad actual](identidad_actual.md).

Consultar [autenticación y uso general](../uso_general.md) y [respuestas y errores](../respuestas_y_errores.md).

[Volver a acceso y usuarios](README.md) · [Índice general](../README.md)
