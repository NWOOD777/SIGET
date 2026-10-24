# Consultar prioridades de tickets

Ruta: `/api/tickets/prioridades/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `GET` | Cuenta SIGET activa. | `200`, lista del catálogo. |

Entrega `id_prioridad`, `nombre`, `nivel_urgencia` y `descripcion` por registro.

No recibe cuerpo.

Consultar [autenticación y uso general](../../uso_general.md) y [respuestas y errores](../../respuestas_y_errores.md).

[Volver a Service Desk y Taller/Reparaciones](../README.md) · [Índice general](../../README.md)
