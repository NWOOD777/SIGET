# Consultar estados de solicitud

Ruta: `/api/solicitudes-asignacion/estados/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `GET` | Cuenta SIGET activa. | `200`, lista de estados. |

Entrega `id_estado_solicitud`, `nombre` y `descripcion` por registro. Los nombres y los identificadores se consultan desde el catálogo del entorno. No recibe cuerpo.

Consulta [autenticación y uso general](../../uso_general.md) y [respuestas y errores](../../respuestas_y_errores.md).

[Volver a Gestión de Activos y Asignaciones](../README.md) · [Índice general](../../README.md)
