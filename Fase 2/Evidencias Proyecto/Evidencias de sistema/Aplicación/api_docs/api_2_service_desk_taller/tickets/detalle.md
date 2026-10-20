# Consultar un ticket

Ruta: `/api/tickets/{id}/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `GET` | Cuenta activa: registros propios; Administrador y Técnico: listado general. | `200`, detalle del ticket. |

El Solicitante consulta sus tickets. Administrador y Técnico pueden consultar cualquier ticket existente.

La respuesta contiene `id_ticket`, `codigo_ticket`, `id_usuario_solicitante`, `solicitante`, `id_tecnico_asignado`, `tecnico_asignado`, `id_activo`, `activo`, `id_estado_ticket`, `estado`, `id_prioridad`, `prioridad`, `asunto`, `descripcion`, `fecha_creacion` y `fecha_resolucion`. Los datos de técnico y resolución son inicialmente `null`; los del activo también pueden ser `null` si el ticket no está asociado a un equipo.

`estado` y `prioridad` son objetos con sus datos de catálogo. `solicitante`, `tecnico_asignado` y `activo` contienen información del registro relacionado; los dos últimos pueden ser `null`.

Un ticket inexistente responde `404` y un ticket de otra persona fuera del alcance permitido, `403`. Esta ruta ofrece consulta; no incluye asignación de Técnico ni resolución.

Consulta [autenticación y uso general](../../uso_general.md) y [respuestas y errores](../../respuestas_y_errores.md).

[Volver a Service Desk y Taller/Reparaciones](../README.md) · [Índice general](../../README.md)
