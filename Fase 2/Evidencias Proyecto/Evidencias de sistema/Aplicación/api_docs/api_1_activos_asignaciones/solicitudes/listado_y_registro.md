# Consultar y crear solicitudes de asignación

Ruta: `/api/solicitudes-asignacion/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `GET` | Cuenta activa: registros propios; Administrador y Técnico: listado general. | `200`, lista de solicitudes. |
| `POST` | Usuario solicitante. | `201`, solicitud creada. |

## Consultar

`GET /api/solicitudes-asignacion/` admite `estado` y `categoria` por identificador o nombre; `search` busca en motivo, categoría o identificador de solicitud. El Administrador y el Técnico también pueden filtrar por `usuario`, usando identificador, correo, nombres o apellidos. El alcance del Solicitante siempre se limita a sus registros. Para revisar las solicitudes pendientes se utiliza `/api/solicitudes-asignacion/?estado=Pendiente`.

## Crear

`POST /api/solicitudes-asignacion/`

```json
{"id_categoria": 1, "motivo": "Equipo requerido para actividades de trabajo"}
```

Ambos campos son obligatorios. Debe existir una categoría con equipos disponibles. Se impide otra solicitud Pendiente o Aprobada de la misma categoría para el mismo usuario. El estado inicial es `Pendiente`.

La consulta y el registro devuelven la estructura descrita en [detalle de una solicitud](detalle.md).

Datos incompletos, falta de disponibilidad o solicitud activa duplicada responden `400`.

Consultar [autenticación y uso general](../../uso_general.md) y [respuestas y errores](../../respuestas_y_errores.md).

[Volver a Gestión de Activos y Asignaciones](../README.md) · [Índice general](../../README.md)
