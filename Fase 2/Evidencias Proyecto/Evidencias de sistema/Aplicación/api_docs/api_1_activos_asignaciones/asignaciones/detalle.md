# Consultar una asignación

Ruta: `/api/asignaciones/{id}/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `GET` | Solicitante o cuenta con `CATALOGO_CONSULTAR`: propios; Administrador y Técnico: listado general. | `200`, detalle de la asignación. |

La consulta identifica al solicitante, el equipo entregado, el Técnico y las fechas del proceso. La respuesta contiene `id_asignacion`, `id_solicitud`, `solicitud`, `id_activo`, `activo`, `id_tecnico_entrega`, `tecnico_entrega`, `id_estado_asignacion`, `estado`, `fecha_entrega`, `fecha_devolucion_prevista` y `fecha_finalizacion`. Los objetos relacionados muestran los datos del solicitante, equipo y técnico. La fecha de finalización permanece `null` mientras la asignación está abierta.

Una asignación inexistente responde `404`. Una cuenta sin acceso a la asignación recibe `403`. Esta ruta es de consulta.

Consulta [autenticación y uso general](../../uso_general.md) y [respuestas y errores](../../respuestas_y_errores.md).

[Volver a Gestión de Activos y Asignaciones](../README.md) · [Índice general](../../README.md)
