# Rechazar una solicitud

Ruta: `/api/solicitudes-asignacion/{id}/rechazar/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `POST` | Administrador del sistema. | `200`, solicitud actualizada. |

Recibe el motivo obligatorio:

```json
{"motivo_rechazo": "No corresponde a la necesidad informada"}
```

La solicitud debe estar `Pendiente`. Se registra el estado `Rechazada`, motivo, responsable, fecha y auditoría. No admite una segunda resolución.

Una solicitud inexistente responde `404`. Un motivo vacío o una solicitud ya resuelta responde `400`.

Consultar [autenticación y uso general](../../uso_general.md) y [respuestas y errores](../../respuestas_y_errores.md).

[Volver a Gestión de Activos y Asignaciones](../README.md) · [Índice general](../../README.md)
