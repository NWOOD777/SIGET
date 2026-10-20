# Consultar asignaciones y registrar entrega

Ruta: `/api/asignaciones/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `GET` | Solicitante o cuenta con `CATALOGO_CONSULTAR`: propios; Administrador y Técnico: listado general. | `200`, lista de asignaciones. |
| `POST` | Técnico de soporte. | `201`, asignación creada. |

## Consultar

`GET /api/asignaciones/` admite `usuario`, `equipo`, `estado` y `search`. `activo` se admite como alternativa a `equipo`.

- `usuario`: identificador, correo, RUT, nombres o apellidos; disponible para Administrador y Técnico.
- `equipo`: identificador, código de inventario, serie o modelo.
- `estado`: identificador o nombre del estado de asignación.
- `search`: identificador de asignación, datos del equipo o del solicitante.

## Registrar entrega

Recibe la solicitud aprobada y el activo físico seleccionado:

```json
{"id_solicitud": 1, "id_activo": 1}
```

`id_solicitud` e `id_activo` son obligatorios. El campo opcional `fecha_devolucion_prevista`, las validaciones y los cambios de estado son los de [entregar equipo para una solicitud](../solicitudes/entregar.md). Aquí la solicitud se informa en el cuerpo en lugar de la ruta.

Los registros del listado y la respuesta de creación utilizan la estructura del [detalle de una asignación](detalle.md).

Una solicitud inexistente responde `404`. Un activo inexistente responde `400`. Incompatibilidad de categoría, falta de disponibilidad o entrega duplicada responde `400`. También puede usarse [la entrega por solicitud](../solicitudes/entregar.md).

Consulta [autenticación y uso general](../../uso_general.md) y [respuestas y errores](../../respuestas_y_errores.md).

[Volver a Gestión de Activos y Asignaciones](../README.md) · [Índice general](../../README.md)
