# API 2 — Service Desk y Taller

Gestiona tickets, atención técnica, órdenes de trabajo, reparaciones y repuestos.
El acceso y las validaciones de cada operación se describen en sus guías.

| Métodos | Ruta | Guía |
|---|---|---|
| GET, POST | `/api/tickets/` | [Consultar y crear tickets](tickets/listado_y_registro.md) |
| GET | `/api/tickets/{id}/` | [Detalle del ticket](tickets/detalle.md) |
| POST | `/api/tickets/{id}/asignar/` | [Asignar o reasignar](tickets/gestion.md#asignar-o-reasignar) |
| POST | `/api/tickets/{id}/tomar/` | [Tomar un ticket](tickets/gestion.md#tomar-un-ticket-disponible) |
| POST | `/api/tickets/{id}/atenciones/` | [Registrar atención](tickets/gestion.md#registrar-una-atención) |
| PATCH | `/api/tickets/{id}/estado/` | [Cambiar estado](tickets/gestion.md#cambiar-estado) |
| GET | `/api/tickets/prioridades/` | [Prioridades](tickets/prioridades.md) |
| GET | `/api/tickets/estados/` | [Estados](tickets/estados.md) |
| GET | `/api/tickets/sla/` | [Plazos de atención](tickets/sla.md) |
| GET, POST | `/api/tickets/{id}/csat/` | [Calificación del servicio](tickets/csat.md) |
| GET | `/api/tickets/indicadores-csat/` | [Indicadores por técnico](tickets/csat.md#indicadores-por-técnico) |
| GET | `/api/tickets/indicadores-csat/{id_tecnico}/` | [Indicadores por técnico](tickets/csat.md#indicadores-por-técnico) |
| GET, POST | `/api/ordenes-trabajo/` | [Consultar y crear OT](ordenes_trabajo/gestion.md) |
| GET | `/api/ordenes-trabajo/tecnicos-disponibles/` | [Técnicos disponibles](ordenes_trabajo/gestion.md#consultar-técnicos-disponibles) |
| GET | `/api/ordenes-trabajo/{id}/historial/` | [Historial de la OT](ordenes_trabajo/gestion.md#consultar-historial) |
| POST | `/api/ordenes-trabajo/{id}/iniciar-reparacion/` | [Iniciar reparación](ordenes_trabajo/gestion.md#iniciar-reparación) |
| POST | `/api/ordenes-trabajo/{id}/pausar/` | [Pausar OT](ordenes_trabajo/gestion.md#pausar-ot) |
| POST | `/api/ordenes-trabajo/{id}/reasignar/` | [Reasignar OT](ordenes_trabajo/gestion.md#reasignar-ot) |
| POST | `/api/ordenes-trabajo/{id}/reanudar/` | [Reanudar OT](ordenes_trabajo/gestion.md#reanudar-ot) |
| POST | `/api/ordenes-trabajo/{id}/completar/` | [Cierre técnico](ordenes_trabajo/cierre_tecnico_api.md) |
| GET, POST | `/api/ordenes-trabajo/{id_orden}/repuestos/` | [Consumos de repuestos](ordenes_trabajo/repuestos.md) |
| POST | `/api/ordenes-trabajo/{id_orden}/repuestos/{id_orden_repuesto}/anular/` | [Anular un consumo](ordenes_trabajo/repuestos.md#anular-una-imputación) |

## Uso desde el escritorio

- **Administrador:** asigna responsables y consulta la información de soporte.
- **Técnico:** toma y atiende sus tickets, registra diagnósticos, gestiona las OT
  y utiliza repuestos durante la reparación.
- **Solicitante, en el portal:** revisa sus tickets y califica el servicio cuando
  están cerrados.

El [cierre técnico en el escritorio](ordenes_trabajo/cierre_tecnico_escritorio.md)
permite completar una reparación o registrar el descarte de un equipo. El historial
conserva diagnósticos, cambios de estado y consumos anteriores.

[Índice de APIs](../README.md) · [Gestión de tickets](tickets/gestion.md)
