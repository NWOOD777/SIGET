# Órdenes de trabajo

Las rutas `/api/ordenes-trabajo/` requieren una cuenta activa con rol Técnico de
soporte. Admiten token Bearer del escritorio o sesión Web; las escrituras con
sesión requieren CSRF. El backend obtiene el usuario desde la sesión o el token.

Las operaciones se guardan en transacciones PostgreSQL y registran auditoría. Los
bloqueos impiden órdenes simultáneas para el mismo activo y protegen los cambios
de estado. Si una validación falla, la operación se revierte.

## Listar OT

`GET /api/ordenes-trabajo/`

Devuelve `200` con las órdenes ordenadas desde la fecha de inicio más reciente.
Cada registro incluye el código de la OT, ticket, activo, estado, diagnóstico,
procedimiento, fechas y técnico responsable. Si no hay órdenes, devuelve `[]`.

## Crear OT

`POST /api/ordenes-trabajo/`

```json
{
  "id_ticket": 1,
  "descripcion_falla": "El equipo no enciende",
  "procedimiento_inicial": "Revisar alimentación y conexiones",
  "es_reparable": true
}
```

El identificador corresponde a un ticket existente. Los textos son obligatorios;
`es_reparable` es un booleano opcional con valor inicial `true`.

El ticket debe estar activo y asociado a un equipo **En revisión**. Se rechaza
una segunda orden para el mismo ticket o una OT vigente del mismo activo.
Se consideran vigentes las órdenes **En Diagnóstico**, **En Reparación** y **Pausada**.

Una creación correcta devuelve `201`, registra el diagnóstico y deja la orden
**En Diagnóstico**, a cargo del técnico que realizó la operación.

## Consultar técnicos disponibles

`GET /api/ordenes-trabajo/tecnicos-disponibles/`

Devuelve `200` con los identificadores y nombres de las cuentas activas con rol
Técnico de soporte. Se utiliza para seleccionar al responsable de una reasignación.

## Consultar historial

`GET /api/ordenes-trabajo/{id}/historial/`

Devuelve `200` con los eventos de la orden: acción, fecha, usuario y detalle.
Una orden inexistente devuelve `404`.

## Iniciar reparación

`POST /api/ordenes-trabajo/{id}/iniciar-reparacion/`

Requiere una OT **En Diagnóstico**, un diagnóstico reparable y el equipo **En revisión**.
Devuelve `200`, cambia la orden a **En Reparación** y el activo a **En reparación**.
Registra el cambio de estado del equipo y la operación en auditoría.

## Pausar OT

`POST /api/ordenes-trabajo/{id}/pausar/`

```json
{"justificacion": "Esperando repuesto"}
```

La justificación es obligatoria. Admite órdenes **En Diagnóstico** o **En Reparación**.
Devuelve `200` y deja la orden **Pausada**, conservando el estado del equipo y
registrando el motivo y la fase anterior en auditoría.

## Reasignar OT

`POST /api/ordenes-trabajo/{id}/reasignar/`

```json
{"id_tecnico_responsable": 2, "observaciones": "Continuidad de atención"}
```

Ambos campos son obligatorios. El destino debe ser un Técnico de soporte activo
y la OT no puede estar **Completada**. Devuelve `200`, cambia su responsable y
registra la observación y el aviso. El responsable del ticket se conserva.

## Reanudar OT

`POST /api/ordenes-trabajo/{id}/reanudar/`

Requiere una OT **Pausada**. Devuelve `200` y restaura la fase registrada al pausar:
**En Diagnóstico** o **En Reparación**. Comprueba que el activo tenga el estado
correspondiente y registra la reanudación. Una auditoría de pausa incompleta o
inválida impide la operación.

## Respuestas de error

| Código | Motivo |
|---|---|
| `400` | Datos inválidos, identificador incorrecto o condición de negocio incumplida. |
| `401` | Token Bearer inválido o vencido. |
| `403` | Cuenta sin acceso, rol no autorizado o CSRF inválido. |
| `404` | Ruta o historial de una orden inexistente. |

Los errores de validación indican el campo y su mensaje. Los identificadores
deben ser enteros positivos del rango admitido por la base; los textos obligatorios
no pueden quedar vacíos y los booleanos deben enviarse como `true` o `false`.

```json
{"id_activo": ["El activo ya tiene una orden de trabajo vigente."]}
```

[Service Desk y Taller](../README.md)
