# Calificación del servicio

El solicitante puede evaluar una sola vez sus tickets **Cerrados**, hayan
requerido o no una orden de trabajo. La evaluación no puede editarse ni eliminarse.

## Registrar una evaluación

`POST /api/tickets/{id}/csat/`

Requiere una cuenta activa de **Usuario solicitante** y ser titular del ticket.
El Administrador y el Técnico no pueden evaluar en nombre del solicitante.

```json
{
  "calificacion_estrellas": 5,
  "comentario": "La atención resolvió el problema."
}
```

`calificacion_estrellas` es obligatorio y admite enteros de 1 a 5. Los formularios
también pueden enviar esos valores como texto. Se rechazan booleanos y decimales.
El comentario es opcional; si está vacío, se guarda como `null`.

El servidor determina el ticket, el usuario y la fecha. La evaluación y su
auditoría se guardan juntas. Ante dos envíos simultáneos solo se conserva uno.

Una operación correcta devuelve `201`:

```json
{
  "id_evaluacion": 1,
  "id_ticket": 8,
  "codigo_ticket": "TCK-0008",
  "id_usuario": 3,
  "calificacion_estrellas": 5,
  "comentario": "La atención resolvió el problema.",
  "fecha_evaluacion": "2026-10-29T14:00:00Z"
}
```

Los identificadores y la fecha son ilustrativos.

## Consultar la evaluación

`GET /api/tickets/{id}/csat/`

El titular recibe `200` con la evaluación registrada. Si el ticket no existe o
aún no está evaluado, devuelve `404`. La consulta no modifica datos.

## Indicadores por técnico

| Ruta | Resultado |
|---|---|
| `GET /api/tickets/indicadores-csat/` | Lista de indicadores para Administrador; indicadores propios para Técnico. |
| `GET /api/tickets/indicadores-csat/?tecnico={id}` | Indicadores de un técnico autorizado. |
| `GET /api/tickets/indicadores-csat/{id_tecnico}/` | Indicadores de un técnico autorizado. |

El Administrador puede consultar cualquier técnico. El Técnico solo puede
consultarse a sí mismo. Los indicadores se calculan a partir de las evaluaciones
de sus tickets y devuelven `200` con los datos del técnico, `cantidad_evaluaciones`
y `promedio_estrellas`. El promedio se redondea a dos decimales; sin evaluaciones,
la cantidad es 0 y el promedio `null`.

## Errores

| Código | Motivo |
|---|---|
| `400` | Calificación o comentario inválidos, ticket sin cerrar o evaluación duplicada. |
| `401` / `403` | Acceso inválido, falta de permisos o ticket de otro solicitante. |
| `404` | Ticket, evaluación o técnico inexistente. |
| `405` | Edición o eliminación no admitidas. |

Los errores de campo indican el dato que debe corregirse; los generales usan
`detail`. Las peticiones con sesión web requieren CSRF.

[Service Desk y Taller](../README.md) · [Respuestas comunes](../../respuestas_y_errores.md)
