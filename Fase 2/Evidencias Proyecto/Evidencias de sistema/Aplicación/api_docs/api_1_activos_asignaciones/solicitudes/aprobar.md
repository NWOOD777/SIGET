# Aprobar una solicitud

Ruta: `/api/solicitudes-asignacion/{id}/aprobar/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `POST` | Administrador del sistema. | `200`, solicitud actualizada. |

Recibe un objeto vacío:

```json
{}
```

La solicitud debe estar `Pendiente` y existir disponibilidad de la categoría requerida. Pasa a `Aprobada`, con responsable, fecha y auditoría de la decisión. La selección y asignación de un equipo físico se realizan en la entrega.

Una solicitud inexistente responde `404`. Una solicitud ya resuelta o sin disponibilidad responde `400`.

Consultar [autenticación y uso general](../../uso_general.md) y [respuestas y errores](../../respuestas_y_errores.md).

[Volver a Gestión de Activos y Asignaciones](../README.md) · [Índice general](../../README.md)
