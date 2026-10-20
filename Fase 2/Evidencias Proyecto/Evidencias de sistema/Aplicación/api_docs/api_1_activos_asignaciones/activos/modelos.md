# Modelos de activos

Ruta: `/api/activos/modelos/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `GET` | Administrador, Técnico o cuenta con permiso `CATALOGO_CONSULTAR`. | `200`, lista del catálogo. |

Entrega `id_modelo`, `nombre`, `id_marca`, `id_categoria`, `marca` y `categoria` por registro.

No recibe cuerpo.

Consulta [autenticación y uso general](../../uso_general.md) y [respuestas y errores](../../respuestas_y_errores.md).

[Volver a Gestión de Activos y Asignaciones](../README.md) · [Índice general](../../README.md)
