# API 2 — Service Desk y Taller/Reparaciones

Corresponde a la segunda API propia de la sección 4.3 y del Anexo B de la arquitectura preliminar. Actualmente expone creación y consulta de tickets, prioridades, estados y políticas SLA.

Las operaciones previstas por la arquitectura que aún no están disponibles se detallan en [alcance y pendientes](../alcance_y_pendientes.md).

| Métodos | Ruta | Documento |
|---|---|---|
| GET, POST | `/api/tickets/` | [Consultar y crear tickets](tickets/listado_y_registro.md) |
| GET | `/api/tickets/{id}/` | [Consultar un ticket](tickets/detalle.md) |
| GET | `/api/tickets/prioridades/` | [Consultar prioridades de tickets](tickets/prioridades.md) |
| GET | `/api/tickets/estados/` | [Consultar estados de tickets](tickets/estados.md) |
| GET | `/api/tickets/sla/` | [Consultar tiempos de servicio](tickets/sla.md) |

[Índice general](../README.md)
