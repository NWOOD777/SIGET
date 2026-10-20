# Consultar y crear tickets

Ruta: `/api/tickets/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `GET` | Cuenta activa: registros propios; Administrador y Técnico: listado general. | `200`, lista de tickets. |
| `POST` | Los tres roles oficiales o cuenta con permiso `TICKET_CREAR`. | `201`, ticket creado. |

## Consultar

`GET /api/tickets/` admite `search` para código, asunto o descripción; `estado` y `prioridad` por identificador o nombre; y `activo` por identificador, código o serie. Para Administrador y Técnico, `usuario` permite filtrar por identificador, correo, RUT, nombres o apellidos del solicitante.

## Registrar

`POST /api/tickets/`

```json
{
  "asunto": "El equipo no enciende",
  "descripcion": "Al presionar el botón de encendido no hay respuesta",
  "id_activo": 1,
  "id_prioridad": 2
}
```

`asunto` es obligatorio y admite hasta 200 caracteres. `descripcion` es obligatoria. `id_activo` e `id_prioridad` son opcionales y admiten `null`; si se informan, deben corresponder a registros existentes. La prioridad predeterminada es `Medio` en el catálogo inicial.

Si se informa `id_activo`, el Usuario solicitante solo puede asociar un activo que tenga mediante una asignación en estado `Activa` y con `fecha_finalizacion` en `null`. El permiso `TICKET_CREAR` permite crear tickets, pero no concede acceso global a los activos: sin rol interno se aplica la misma restricción. El Administrador del sistema y el Técnico de soporte mantienen su alcance por rol y pueden asociar cualquier activo existente, sin exigir una asignación propia activa.

Para un usuario sin rol interno, un activo no autorizado devuelve HTTP `403` con el mensaje genérico `No tiene autorización para reportar ese activo.`, sin crear el ticket ni registrar auditoría de creación. Omitir `id_activo` o enviarlo como `null` permite registrar un ticket sin equipo específico.

La autorización sobre el activo se verifica al registrar el ticket para mantenerla consistente con las devoluciones concurrentes.

La creación automática durante una [devolución con falla o daño](../../api_1_activos_asignaciones/asignaciones/devolucion.md) puede asociar el activo con la asignación ya finalizada; no exige una asignación activa como el registro manual.

El ticket se crea `Abierto`, con código asignado por el sistema y sin técnico asignado. Se impide un ticket activo con el mismo asunto, activo y solicitante. El registro de un ticket por sí solo no cambia el estado del equipo.

Los registros del listado y la respuesta de creación utilizan la estructura del [detalle de un ticket](detalle.md).

Los identificadores opcionales deben ser enteros entre 1 y 2147483647. Datos inválidos o ticket activo duplicado responden `400`.

Consulta [autenticación y uso general](../../uso_general.md) y [respuestas y errores](../../respuestas_y_errores.md).

[Volver a Service Desk y Taller/Reparaciones](../README.md) · [Índice general](../../README.md)
