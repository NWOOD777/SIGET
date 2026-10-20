# Consultar una solicitud

Ruta: `/api/solicitudes-asignacion/{id}/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `GET` | Cuenta activa: registros propios; Administrador y Técnico: listado general. | `200`, detalle de la solicitud. |

`id` identifica la solicitud. La respuesta contiene `id_solicitud`, `id_usuario`, `solicitante`, `id_categoria`, `categoria`, `id_estado_solicitud`, `estado`, `id_administrador_resolutor`, `resolutor`, `fecha_solicitud`, `fecha_resolucion`, `motivo` y `motivo_rechazo`. Antes de su resolución, los datos del resolutor y la fecha de resolución son `null`.

Un registro inexistente responde `404`. Una cuenta sin rol interno no puede consultar solicitudes de otras personas.

Consulta [autenticación y uso general](../../uso_general.md) y [respuestas y errores](../../respuestas_y_errores.md).

[Volver a Gestión de Activos y Asignaciones](../README.md) · [Índice general](../../README.md)
