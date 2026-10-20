# API 1 — Gestión de Activos y Asignaciones

Comprende inventario, catálogos, solicitudes por categoría, aprobación o rechazo, entregas, asignaciones y devoluciones con evaluación inicial. Corresponde a la primera API propia definida en la sección 4.3 de la arquitectura preliminar.

Los permisos y el alcance de consulta se indican en cada endpoint.

| Métodos | Ruta | Documento |
|---|---|---|
| GET, POST | `/api/activos/` | [Consultar y registrar activos](activos/listado_y_registro.md) |
| GET, PUT, PATCH | `/api/activos/{id}/` | [Consultar y modificar un activo](activos/detalle_y_modificacion.md) |
| GET | `/api/activos/categorias/` | [Categorías de activos](activos/categorias.md) |
| GET | `/api/activos/marcas/` | [Marcas de activos](activos/marcas.md) |
| GET | `/api/activos/modelos/` | [Modelos de activos](activos/modelos.md) |
| GET | `/api/activos/ubicaciones/` | [Ubicaciones de activos](activos/ubicaciones.md) |
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
