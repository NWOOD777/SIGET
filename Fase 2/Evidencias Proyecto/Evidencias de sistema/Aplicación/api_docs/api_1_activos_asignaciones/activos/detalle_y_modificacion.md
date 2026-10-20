# Consultar y modificar un activo

Ruta: `/api/activos/{id}/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `GET` | Administrador, Técnico o cuenta con permiso `CATALOGO_CONSULTAR`. | `200`, detalle del activo. |
| `PUT` | Administrador del sistema. | `200`, activo actualizado. |
| `PATCH` | Administrador del sistema. | `200`, activo actualizado. |

`id` es el identificador del activo. La consulta devuelve `id_activo`, `codigo_inventario`, `numero_serie`, `id_modelo`, `id_ubicacion`, `id_estado_activo`, `valor_adquisicion`, `fecha_compra`, `fecha_garantia`, `fecha_registro`, `modelo`, `marca`, `categoria`, `ubicacion` y `estado`.

`PUT` recibe al menos `numero_serie`, `id_modelo` e `id_ubicacion`. `PATCH` recibe únicamente los campos a modificar:

```json
{"id_ubicacion": 2}
```

Los campos, formatos y catálogos corresponden a los del [registro de activos](listado_y_registro.md). El identificador, el código de inventario y la fecha de registro permanecen protegidos.

Con una asignación abierta no puede cambiarse el modelo ni el estado del activo. El estado `Asignado` se establece mediante una entrega.

Un activo inexistente responde `404`; datos inválidos o cambios no permitidos, `400`.

Consulta [autenticación y uso general](../../uso_general.md) y [respuestas y errores](../../respuestas_y_errores.md).

[Volver a Gestión de Activos y Asignaciones](../README.md) · [Índice general](../../README.md)
