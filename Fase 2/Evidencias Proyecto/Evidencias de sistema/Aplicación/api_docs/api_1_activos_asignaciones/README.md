# API 1 — Gestión de Activos y Asignaciones

Comprende inventario, catálogos, solicitudes por categoría, aprobación o rechazo, entregas, asignaciones y devoluciones con evaluación inicial.

Los permisos y el alcance de consulta se indican en cada endpoint.

| Métodos | Ruta | Documento |
|---|---|---|
| GET, POST | `/api/activos/` | [Consultar y registrar activos](activos/listado_y_registro.md) |
| GET, PUT, PATCH, DELETE | `/api/activos/{id}/` | [Consultar, modificar y eliminar un activo](activos/detalle_y_modificacion.md) |
| GET, POST | `/api/activos/{id}/qr/` | [Generar, consultar e imprimir etiquetas QR](activos/qr.md) |
| GET | `/api/activos/historial/` | [Historial y trazabilidad del equipo](activos/historial.md) |
| GET, POST | `/api/activos/categorias/` | [Categorías de activos](activos/categorias.md) |
| GET, PUT, PATCH, DELETE | `/api/activos/categorias/{id}/` | [Categorías de activos](activos/categorias.md) |
| GET, POST | `/api/activos/marcas/` | [Marcas de activos](activos/marcas.md) |
| GET, PUT, PATCH, DELETE | `/api/activos/marcas/{id}/` | [Marcas de activos](activos/marcas.md) |
| GET, POST | `/api/activos/modelos/` | [Modelos de activos](activos/modelos.md) |
| GET, PUT, PATCH, DELETE | `/api/activos/modelos/{id}/` | [Modelos de activos](activos/modelos.md) |
| GET, POST | `/api/activos/ubicaciones/` | [Ubicaciones de activos](activos/ubicaciones.md) |
| GET, PUT, PATCH, DELETE | `/api/activos/ubicaciones/{id}/` | [Ubicaciones de activos](activos/ubicaciones.md) |
| GET | `/api/activos/estados/` | [Estados de activos](activos/estados.md) |
| GET, POST | `/api/solicitudes-asignacion/` | [Consultar y crear solicitudes de asignación](solicitudes/listado_y_registro.md) |
| GET | `/api/solicitudes-asignacion/{id}/` | [Consultar una solicitud](solicitudes/detalle.md) |
| POST | `/api/solicitudes-asignacion/{id}/aprobar/` | [Aprobar una solicitud](solicitudes/aprobar.md) |
| POST | `/api/solicitudes-asignacion/{id}/rechazar/` | [Rechazar una solicitud](solicitudes/rechazar.md) |
| POST | `/api/solicitudes-asignacion/{id}/entregar/` | [Entregar equipo para una solicitud](solicitudes/entregar.md) |
| GET | `/api/solicitudes-asignacion/estados/` | [Consultar estados de solicitud](solicitudes/estados.md) |
| GET, POST | `/api/asignaciones/` | [Consultar asignaciones y registrar entrega](asignaciones/listado_y_entrega.md) |
| GET | `/api/asignaciones/{id}/` | [Consultar una asignación](asignaciones/detalle.md) |
| POST | `/api/asignaciones/{id}/devolucion/` | [Registrar devolución y evaluación inicial](asignaciones/devolucion.md) |
| GET | `/api/asignaciones/estados/` | [Consultar estados de asignación](asignaciones/estados.md) |

[Índice general](../README.md)
