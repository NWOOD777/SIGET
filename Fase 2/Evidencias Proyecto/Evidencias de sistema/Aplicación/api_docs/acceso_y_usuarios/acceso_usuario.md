# Consultar acceso de un usuario

Ruta: `/api/usuarios/{id}/acceso/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `GET` | Administrador del sistema. | `200`, ficha de acceso del usuario indicado. |

Entrega `id_usuario`, `rut`, `nombres`, `apellidos`, `correo`, `activo`, `fecha_creacion`, `roles` y `permisos_efectivos`.

Cada rol incluye identificador, nombre y descripción. Los permisos efectivos incluyen identificador, código y descripción. Un usuario inexistente responde `404`. Para consultar la identidad propia sin rol administrativo se utiliza [identidad actual](identidad_actual.md).

Consultar [autenticación y uso general](../uso_general.md) y [respuestas y errores](../respuestas_y_errores.md).

[Volver a acceso y usuarios](README.md) · [Índice general](../README.md)

El RUT se presenta en esta ficha administrativa, durante el aprovisionamiento y en «Mi perfil» al propio usuario autenticado. Las consultas operativas y el listado de usuarios no lo incluyen.

## Corregir el RUT

`PATCH /api/usuarios/{id}/identificacion/` recibe `{"rut": "12.345.678-5"}` y exige
un Administrador activo. Valida formato, dígito verificador y unicidad. Devuelve
`id_usuario` y el RUT normalizado, con `Cache-Control: no-store, private`. Los datos
inválidos responden `400`, un duplicado `409` y una cuenta inexistente `404`.
La corrección conserva el identificador interno y el historial. La operación queda
en auditoría sin copiar el RUT en el evento. Las sesiones Web requieren CSRF.
