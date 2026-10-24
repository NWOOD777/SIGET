# API 2 — Service Desk y Taller/Reparaciones

Expone creación, consulta y gestión de tickets, prioridades, estados y políticas SLA.

Consultar la [organización de las APIs](../organizacion.md) para conocer la relación de estos servicios con el resto del backend.

| Métodos | Ruta | Documento |
|---|---|---|
| GET, POST | `/api/tickets/` | [Consultar y crear tickets](tickets/listado_y_registro.md) |
| GET | `/api/tickets/{id}/` | [Consultar un ticket](tickets/detalle.md) |
| GET | `/api/tickets/prioridades/` | [Consultar prioridades de tickets](tickets/prioridades.md) |
| GET | `/api/tickets/estados/` | [Consultar estados de tickets](tickets/estados.md) |
| GET | `/api/tickets/sla/` | [Consultar tiempos de servicio](tickets/sla.md) |
| POST | `/api/tickets/{id}/asignar/` | [Asignar o reasignar](#asignar-o-reasignar-un-ticket) |
| POST | `/api/tickets/{id}/atenciones/` | [Registrar atención](#registrar-una-atención-técnica) |
| PATCH | `/api/tickets/{id}/estado/` | [Cambiar estado](#cambiar-el-estado-de-un-ticket) |
| POST | `/api/tickets/{id}/tomar/` | [Tomar un ticket disponible](#tomar-un-ticket-disponible) |
| GET, POST | `/api/tickets/{id}/csat/` | [Calificación de servicio (CSAT)](tickets/csat.md) |
| GET | `/api/tickets/indicadores-csat/` | [Indicadores CSAT por técnico](tickets/csat.md#5-indicadores-csat-por-técnico) |
| GET | `/api/tickets/indicadores-csat/{id_tecnico}/` | [Indicadores CSAT de un técnico](tickets/csat.md#5-indicadores-csat-por-técnico) |

## Gestión de tickets

Se reutiliza la autenticación Bearer para Escritorio y la sesión Web existente. Las peticiones con sesión requieren CSRF. La identidad, los roles y los permisos se obtienen del servidor y de PostgreSQL; no se aceptan actores, fechas ni estados implícitos enviados por el cliente.

Los ejemplos siguientes son **plantillas**: sustituir los marcadores `<...>` por los valores reales de la respuesta de consulta de tickets, los usuarios y el catálogo `GET /api/tickets/estados/`. Los marcadores numéricos se reemplazan por enteros, sin comillas. No representan IDs fijos ni respuestas capturadas de una base real.

### Asignar o reasignar un ticket

**POST `/api/tickets/{id}/asignar/`**. Establece o cambia el técnico responsable sin cambiar el estado del ticket.

Requiere usuario activo con rol **Administrador del sistema** y permiso **TICKET_ASIGNAR**.

Solicitud:

```text
{
  "id_tecnico_asignado": <id_real_del_tecnico>,
  "motivo": "Asignación por especialidad técnica."
}
```

Respuesta **200**: ticket completo mediante `TicketReadSerializer`, igual al contrato de [consulta de detalle](tickets/detalle.md). Ejemplo de los campos relevantes para una asignación en estado Abierto (extracto):

```text
{
  "id_ticket": <id_real_del_ticket>,
  "id_tecnico_asignado": <id_real_del_tecnico>,
  "id_estado_ticket": <id_real_de_Abierto>,
  "estado": {
    "id_estado_ticket": <id_real_de_Abierto>,
    "nombre": "Abierto",
    "descripcion": "<descripcion_del_catalogo>"
  }
}
```

El motivo es obligatorio y se recortan sus espacios exteriores. El técnico destino debe existir, estar activo y tener rol **Técnico de soporte** y permiso **TICKET_ATENDER**. Se rechaza asignar al mismo técnico y asignar o reasignar tickets Resueltos o Cerrados. La operación registra administrador, técnico anterior, técnico nuevo y motivo en auditoría y genera una notificación persistente al solicitante.

Errores: **400** por entrada inválida, técnico inexistente/no habilitado, mismo técnico o ticket Resuelto/Cerrado; **403** por falta de rol o permiso; **404** si el ticket no existe. Se aplican también los errores comunes de autenticación descritos abajo.

### Registrar una atención técnica

**POST `/api/tickets/{id}/atenciones/`**. Registra un `ComentarioTicket` sin cambiar automáticamente el estado.

Requiere usuario activo con rol **Técnico de soporte**, permiso **TICKET_ATENDER** y ser el técnico actualmente asignado al ticket.

Solicitud:

```json
{
  "mensaje": "Se revisó el equipo y se verificó su conectividad."
}
```

Respuesta **201**, con estos cinco campos:

```text
{
  "id_comentario": <id_generado>,
  "id_ticket": <id_real_del_ticket>,
  "id_usuario": <id_del_tecnico_autenticado>,
  "mensaje": "Se revisó el equipo y se verificó su conectividad.",
  "fecha_registro": "<fecha_hora_del_servidor_en_formato_ISO_8601>"
}
```

El mensaje es obligatorio y no admite solo espacios. El servidor determina autor y fecha. Solo se admiten atenciones en Abierto, En Proceso y En Espera. No se admiten en Resuelto ni Cerrado. La atención genera auditoría y notificación persistente al solicitante.

Errores: **400** por mensaje inválido o estado no permitido; **403** por falta de rol/permiso o por no ser el técnico asignado; **404** si el ticket no existe. Se aplican los errores comunes de autenticación.

### Cambiar el estado de un ticket

**PATCH `/api/tickets/{id}/estado/`**. Cambia el estado y registra el motivo como `ComentarioTicket`.

Requiere usuario activo con rol **Técnico de soporte**, permiso **TICKET_ATENDER** y ser el técnico actualmente asignado.

Solicitud para un ticket Abierto:

```text
{
  "id_estado_ticket": <id_real_de_En_Proceso>,
  "mensaje": "Se inició la revisión del equipo."
}
```

Respuesta **200**: ticket completo mediante `TicketReadSerializer`. Ejemplo de los campos relevantes tras esa transición (extracto):

```text
{
  "id_ticket": <id_real_del_ticket>,
  "id_estado_ticket": <id_real_de_En_Proceso>,
  "estado": {
    "id_estado_ticket": <id_real_de_En_Proceso>,
    "nombre": "En Proceso",
    "descripcion": "<descripcion_del_catalogo>"
  },
  "fecha_resolucion": null
}
```

El estado destino debe existir y el mensaje es obligatorio, sin admitir solo espacios. El cambio guarda estado, comentario, auditoría con estados anterior/nuevo, actor y motivo, y notificación al solicitante.

Errores: **400** por entrada inválida, estado inexistente, transición no permitida, ticket Cerrado o existencia de OT vigente al resolver/cerrar; **403** por falta de rol/permiso o técnico no asignado; **404** si el ticket no existe. Se aplican los errores comunes de autenticación.

### Tomar un ticket disponible

**POST `/api/tickets/{id}/tomar/`**. Permite la autoasignación sin sustituir la asignación o reasignación administrativa de `/asignar/`.

Requiere usuario autenticado y activo con rol real **Técnico de soporte** y permiso efectivo **TICKET_ATENDER**. Un administrador sin esos requisitos no puede tomar tickets. La identidad se obtiene exclusivamente del servidor.

Solicitud **sin cuerpo**, por ejemplo `POST /api/tickets/<id_real_del_ticket>/tomar/`. También se admite `{}`. No se admiten campos en el cuerpo: enviar `id_tecnico_asignado`, un actor u otros datos genera **400**.

Respuesta **200**, mediante `TicketReadSerializer`, con el mismo ticket completo que `/asignar/`. El campo `id_tecnico_asignado` corresponde al técnico autenticado; `id_estado_ticket` y `estado` permanecen en Abierto. No se crean comentarios ni se modifica `fecha_resolucion`.

Ejemplo de campos relevantes de la respuesta (extracto; marcadores de valores reales):

```text
{
  "id_ticket": <id_real_del_ticket>,
  "id_tecnico_asignado": <id_del_tecnico_autenticado>,
  "id_estado_ticket": <id_real_de_Abierto>,
  "estado": {
    "id_estado_ticket": <id_real_de_Abierto>,
    "nombre": "Abierto",
    "descripcion": "<descripcion_del_catalogo>"
  }
}
```

Solo se puede tomar un ticket **Abierto y sin técnico asignado**. Un ticket ya asignado no está disponible, aunque pertenezca al mismo técnico. No se permite tomar tickets En Proceso, En Espera, Resueltos o Cerrados, ni quitar tickets a otro técnico.

Errores: **400** por cuerpo no vacío o ticket no disponible; **403** por falta de acceso, rol o permiso; **404** si el ticket no existe. Se aplican los errores comunes de autenticación y CSRF. Un ticket Cerrado devuelve el mensaje explícito documentado abajo; los demás casos de indisponibilidad devuelven:

```json
{
  "detail": "El ticket no está disponible: debe estar Abierto y sin técnico asignado."
}
```

La operación abre una transacción y bloquea únicamente la fila del ticket mediante `select_for_update(of=("self",))`; comprueba disponibilidad después de adquirir el bloqueo. Si dos técnicos intentan tomar el mismo ticket, solo uno puede conseguirlo. Guarda responsable, auditoría `TICKET_TOMADO` (actor, ticket, fecha/hora y acción) y notificación al solicitante atómicamente, utilizando el ID real de auditoría como `id_evento`. No envía correo desde el endpoint. Un fallo al registrar auditoría o notificación revierte la asignación.

Los GET existentes permiten consultar `/api/tickets/?estado=Abierto&sin_asignar=true` para obtener tickets Abiertos sin técnico, dentro de la visibilidad existente. El parámetro admite `true` o `false`; omitido o en `false` no añade restricciones, y otros valores devuelven 400. Se combina con los demás filtros y conserva el orden del listado. Consultar no reserva disponibilidad y `/tomar/` siempre vuelve a validarla. Véase [bandeja de tickets disponibles](tickets/listado_y_registro.md#bandeja-de-tickets-disponibles).

### Ciclo de vida e integración con órdenes de trabajo

| Estado actual | Destinos permitidos |
|---|---|
| Abierto | En Proceso |
| En Proceso | En Espera, Resuelto |
| En Espera | En Proceso |
| Resuelto | Cerrado |
| Cerrado | Ninguno |

No se permiten otras transiciones ni repetir el mismo estado. Los tickets Resueltos no pueden reabrirse ni recibir atenciones o reasignaciones; si el problema vuelve a ocurrir, corresponde crear otro ticket. Únicamente pueden pasar a Cerrado.

Al pasar a Resuelto se establece `fecha_resolucion` con la hora del servidor; al cerrar se conserva esa fecha. Los tickets Cerrados no admiten modificaciones. Para solicitudes válidas de un actor autorizado, los cuatro endpoints de gestión rechazan su modificación con **400** y:

```json
{
  "detail": "El ticket está Cerrado y no puede ser modificado."
}
```

Las OT en **En Diagnóstico**, **En Reparación** o **Pausada** son vigentes e impiden resolver o cerrar el ticket. Una OT **Completada** no lo impide. No se crean nuevas OT sobre tickets Resueltos o Cerrados. La gestión de estado del ticket no modifica automáticamente órdenes, diagnósticos ni activos.

La creación de OT y la gestión del ticket comparten su bloqueo de fila. Cada operación conserva sus escrituras, auditoría y notificación en una misma transacción; si falla la auditoría o el registro del aviso, se revierten sus efectos. Las notificaciones usan el ID real de auditoría para identificar el evento y no se envía correo directamente desde estos endpoints. El envío posterior y los reintentos utilizan la infraestructura persistente existente; no convierten el POST de atenciones en una operación idempotente ante reenvíos del cliente.

### Errores comunes de autenticación y autorización

- **401**: credencial Bearer inválida, conforme al autenticador existente.
- **403**: ausencia de sesión sin cabecera Bearer, usuario sin acceso, falta de rol/permiso o fallo CSRF en peticiones de sesión. Un rol almacenado en sesión o enviado en el cuerpo no amplía permisos.
- Las validaciones de entrada se ejecutan antes de llamar al servicio. Un cuerpo inválido puede devolver **400** antes de comprobar la existencia o el estado del ticket.

Los mecanismos de autenticación se detallan en [uso general](../uso_general.md).

## Calificación de servicio (CSAT)

Permite al **Usuario solicitante** activo y titular de un ticket evaluar por única vez la atención recibida cuando el ticket ha finalizado su ciclo de vida y se encuentra en estado **Cerrado** (tanto si requirió una orden de trabajo como si se resolvió directamente en Service Desk).

- **`GET, POST /api/tickets/{id}/csat/`**: consulta en solo lectura (`GET`) y registro único (`POST`) de puntuación entera de `1` a `5` estrellas y comentario opcional, con bloqueo transaccional sobre el ticket y auditoría `TICKET_CSAT_REGISTRADO`.
- **`GET /api/tickets/indicadores-csat/`** y **`GET /api/tickets/indicadores-csat/{id_tecnico}/`**: consulta de `cantidad_evaluaciones` y `promedio_estrellas` calculados dinámicamente por técnico asignado (disponible para **Administrador del sistema** sobre todos los técnicos y para **Técnico de soporte** sobre sus propios indicadores).

Véase el detalle de contratos, validaciones, concurrencia e indicadores en [Calificación de servicio (CSAT)](tickets/csat.md).

[Índice general](../README.md)
