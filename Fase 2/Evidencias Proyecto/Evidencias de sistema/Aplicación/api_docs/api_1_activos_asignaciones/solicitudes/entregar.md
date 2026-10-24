# Entregar equipo para una solicitud

Ruta: `/api/solicitudes-asignacion/{id}/entregar/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `POST` | Técnico de soporte. | `201`, asignación creada. |

`POST /api/solicitudes-asignacion/{id}/entregar/`

```json
{"id_activo": 1, "fecha_devolucion_prevista": "2026-10-30T18:00:00Z"}
```

`id_activo` es obligatorio; `fecha_devolucion_prevista` es opcional y admite `null`. Si se informa una fecha, debe ser igual o posterior al momento de la entrega.

La solicitud debe estar Aprobada y sin entrega anterior. El activo debe estar Disponible y corresponder a la categoría solicitada. Al completar la operación, la asignación queda `Activa`, el activo `Asignado` y la solicitud `Atendida`.

La respuesta utiliza la estructura del [detalle de una asignación](../asignaciones/detalle.md).

Una solicitud inexistente responde `404`. Estados incompatibles, activo no disponible o entrega duplicada responden `400`. Existe una alternativa en [registro de asignaciones](../asignaciones/listado_y_entrega.md).

Consultar [autenticación y uso general](../../uso_general.md) y [respuestas y errores](../../respuestas_y_errores.md).

[Volver a Gestión de Activos y Asignaciones](../README.md) · [Índice general](../../README.md)
