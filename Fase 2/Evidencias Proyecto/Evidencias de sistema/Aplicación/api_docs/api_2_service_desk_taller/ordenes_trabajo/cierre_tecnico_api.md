# Cierre técnico de una orden de trabajo

`POST /api/ordenes-trabajo/{id}/completar/`

Requiere una cuenta activa de Técnico de soporte con los permisos `OT_GESTIONAR`
y `TICKET_ATENDER`. La identidad se obtiene del acceso autenticado. Las peticiones
con sesión web requieren CSRF; el escritorio utiliza un token Bearer.

## Reparación exitosa

La orden debe estar **En Reparación**. Son obligatorios la solución y las pruebas realizadas:

```json
{
  "resultado": "REPARACION_EXITOSA",
  "solucion_aplicada": "Se reemplazó el componente defectuoso.",
  "pruebas_realizadas": "Encendido y conectividad verificados."
}
```

La OT queda **Completada**, el activo **Disponible** y el ticket **Resuelto**.

## Equipo no reparable

Se admite desde **En Diagnóstico** o **En Reparación** y exige un informe de descarte:

```json
{
  "resultado": "NO_REPARABLE",
  "informe_descarte": "Daño irreversible en la placa principal."
}
```

La OT queda **Completada**, el activo **Dado de baja** y el ticket **Resuelto**.
Se registra un aviso por correo para los administradores activos con dirección válida.

## Validaciones

Los textos obligatorios deben contener información, no solo espacios. El cuerpo
admite únicamente el resultado y los textos del cierre; el servidor determina
el técnico, la fecha y los estados finales.

Se rechazan órdenes pausadas o completadas, tickets resueltos o cerrados,
un segundo cierre y relaciones incompatibles entre ticket, OT y activo. El equipo
no debe tener una asignación sin finalizar ni otra OT vigente.

El cierre, los estados, el historial, la auditoría y los avisos se guardan juntos.
Si falla una escritura, se revierte la operación. Se conservan los diagnósticos,
responsables y movimientos de repuestos anteriores.

## Respuesta

Una operación correcta devuelve `200`:

```json
{
  "id_orden": 123,
  "estado": "Completada",
  "resultado": "REPARACION_EXITOSA",
  "id_cierre_tecnico": 45,
  "fecha_cierre": "2026-10-29T14:00:00Z",
  "id_activo": 67,
  "estado_activo": "Disponible",
  "id_ticket": 89,
  "estado_ticket": "Resuelto"
}
```

Para un equipo no reparable cambia `resultado` a `NO_REPARABLE` y
`estado_activo` a `Dado de baja`. Los identificadores y la fecha del ejemplo
se sustituyen por los registros de cada operación.

| Código | Motivo |
|---|---|
| `400` | Datos inválidos, cierre duplicado o estado incompatible. |
| `401` / `403` | Acceso inválido, permisos insuficientes o fallo CSRF. |
| `404` | Orden inexistente. |
| `405` | Método no admitido. |
| `500` | Fallo interno al completar el cierre. |

La tabla `cierre_tecnico` está incluida en `init_siget_bd.sql`.
Consultar [uso desde el escritorio](cierre_tecnico_escritorio.md) y
[respuestas comunes](../../respuestas_y_errores.md).
