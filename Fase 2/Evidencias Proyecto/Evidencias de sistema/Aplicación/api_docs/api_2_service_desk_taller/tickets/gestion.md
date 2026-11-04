# Gestión de tickets

Las operaciones requieren una cuenta activa. El backend obtiene el usuario y sus
permisos de PostgreSQL. Las peticiones con sesión web requieren CSRF; el escritorio
utiliza un token Bearer.

## Asignar o reasignar

`POST /api/tickets/{id}/asignar/`

Requiere **Administrador del sistema** y `TICKET_ASIGNAR`:

```json
{"id_tecnico_asignado": 2, "motivo": "Asignación por especialidad técnica."}
```

El técnico debe estar activo y habilitado para atender tickets. El motivo es
obligatorio. Se rechaza elegir al mismo responsable o modificar un ticket
resuelto o cerrado. Devuelve `200` con el ticket actualizado y conserva su estado.

## Tomar un ticket disponible

`POST /api/tickets/{id}/tomar/`

Requiere **Técnico de soporte** y `TICKET_ATENDER`. Se envía sin cuerpo o con `{}`.
Solo se puede tomar un ticket **Abierto y sin responsable**. El servidor asigna
al técnico autenticado y devuelve `200` con el ticket, todavía **Abierto**.
Si dos técnicos intentan tomarlo, solo uno puede completar la asignación.

Los tickets disponibles se consultan con
`GET /api/tickets/?estado=Abierto&sin_asignar=true`. El filtro `sin_asignar`
admite `true` o `false`; otros valores devuelven `400`.

## Registrar una atención

`POST /api/tickets/{id}/atenciones/`

Requiere ser el Técnico responsable y contar con `TICKET_ATENDER`:

```json
{"mensaje": "Se revisó la alimentación del equipo."}
```

El mensaje es obligatorio. Se admiten atenciones en **Abierto**, **En Proceso**
y **En Espera**. Devuelve `201` con `id_comentario`, `id_ticket`, `id_usuario`,
`mensaje` y `fecha_registro`. Registrar una atención notifica al solicitante y mantiene el estado del ticket.

## Consultar mis mensajes enviados

`GET /api/tickets/{id}/atenciones/`

Requiere **Técnico de soporte** y `TICKET_ATENDER`. Devuelve `200` con los
mensajes enviados por el técnico autenticado en ese ticket, del más reciente
al más antiguo. Cada elemento tiene los mismos campos que la respuesta del
`POST`. Un ticket sin mensajes propios devuelve una lista vacía. La consulta
también funciona después de una reasignación o del cierre del ticket.

## Cambiar estado

`PATCH /api/tickets/{id}/estado/`

Requiere ser el Técnico responsable y contar con `TICKET_ATENDER`:

```json
{"id_estado_ticket": 2, "mensaje": "Se inició la revisión del equipo."}
```

El estado debe existir y el mensaje es obligatorio. Los IDs del ejemplo se
consultan en el catálogo de [estados](estados.md). Devuelve `200` con el ticket actualizado.

| Estado actual | Destinos permitidos |
|---|---|
| Abierto | En Proceso |
| En Proceso | En Espera, Resuelto |
| En Espera | En Proceso |
| Resuelto | Cerrado |
| Cerrado | Ninguno |

Al resolver se guarda `fecha_resolucion`; al cerrar se conserva. Un ticket resuelto
no recibe nuevas atenciones ni reasignaciones. Un ticket cerrado solo se consulta.

Una OT **En Diagnóstico**, **En Reparación** o **Pausada** impide resolver o cerrar
el ticket por esta ruta. El [cierre técnico](../ordenes_trabajo/cierre_tecnico_api.md)
resuelve el ticket al completar la reparación o el descarte del activo.

## Registros y avisos

Las asignaciones, atenciones y cambios de estado registran auditoría y avisos al
solicitante junto con la operación. El servicio de correo procesa esos avisos
por separado. Repetir un envío de atención puede crear otro comentario.

## Errores

| Código | Motivo |
|---|---|
| `400` | Datos inválidos, ticket no disponible o cambio de estado no permitido. |
| `401` / `403` | Acceso inválido, falta de rol o permiso, técnico no responsable o fallo CSRF. |
| `404` | Ticket inexistente. |

Los errores generales usan `detail`; los errores de campos indican el dato que
se debe corregir. Las respuestas completas del ticket siguen el
[contrato de detalle](detalle.md).

## Uso desde el escritorio

En **Mesa de ayuda**, el Administrador utiliza **Asignar técnico**. El Técnico
puede **Tomar ticket** si está disponible y **Atender Ticket** cuando es su
responsable. **Enviar mensaje al solicitante** registra una actualización visible
para el solicitante. **Cambiar estado** pide un motivo aparte. Desde la gestión
del ticket o **Ver detalle**, el técnico puede abrir **Ver mis mensajes enviados**.

[Service Desk y Taller](../README.md) · [Autenticación](../../uso_general.md)
