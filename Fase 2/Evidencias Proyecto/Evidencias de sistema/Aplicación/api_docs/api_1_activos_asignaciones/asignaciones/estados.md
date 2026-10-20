# Consultar estados de asignación

Ruta: `/api/asignaciones/estados/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `GET` | Administrador, Técnico, Solicitante o cuenta con `CATALOGO_CONSULTAR`. | `200`, lista de estados. |

Entrega `id_estado_asignacion`, `nombre` y `descripcion` por registro. Las asignaciones del flujo vigente utilizan los estados `Activa` y `Finalizada`. No recibe cuerpo.

Consulta [autenticación y uso general](../../uso_general.md) y [respuestas y errores](../../respuestas_y_errores.md).

[Volver a Gestión de Activos y Asignaciones](../README.md) · [Índice general](../../README.md)
