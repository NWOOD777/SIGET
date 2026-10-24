# Estados de activos

Ruta: `/api/activos/estados/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `GET` | Administrador, Técnico o cuenta con permiso `CATALOGO_CONSULTAR`. | `200`, lista del catálogo. |

Entrega `id_estado_activo`, `nombre` y `descripcion` por registro.

No recibe cuerpo.

Consultar [autenticación y uso general](../../uso_general.md) y [respuestas y errores](../../respuestas_y_errores.md).

[Volver a Gestión de Activos y Asignaciones](../README.md) · [Índice general](../../README.md)
