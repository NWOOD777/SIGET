# Ubicaciones de activos

Ruta: `/api/activos/ubicaciones/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `GET` | Administrador, Técnico o cuenta con permiso `CATALOGO_CONSULTAR`. | `200`, lista del catálogo. |

Entrega `id_ubicacion`, `nombre_area`, `edificio` y `piso` por registro.

No recibe cuerpo.

Consulta [autenticación y uso general](../../uso_general.md) y [respuestas y errores](../../respuestas_y_errores.md).

[Volver a Gestión de Activos y Asignaciones](../README.md) · [Índice general](../../README.md)
