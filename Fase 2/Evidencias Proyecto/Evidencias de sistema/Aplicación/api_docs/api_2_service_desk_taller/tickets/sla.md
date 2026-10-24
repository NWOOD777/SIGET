# Consultar tiempos de servicio

Ruta: `/api/tickets/sla/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `GET` | Cuenta SIGET activa. | `200`, lista del catálogo. |

Entrega `id_sla`, `id_prioridad`, `prioridad`, `tiempo_respuesta_horas`, `tiempo_resolucion_horas` y `descripcion`. `prioridad` es un objeto de catálogo. Los tiempos se expresan en horas. La consulta presenta políticas; no calcula un reporte de cumplimiento del SLA.

No recibe cuerpo.

Consultar [autenticación y uso general](../../uso_general.md) y [respuestas y errores](../../respuestas_y_errores.md).

[Volver a Service Desk y Taller/Reparaciones](../README.md) · [Índice general](../../README.md)
