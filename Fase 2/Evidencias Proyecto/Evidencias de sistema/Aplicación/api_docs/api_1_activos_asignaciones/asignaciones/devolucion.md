# Registrar devolución y evaluación inicial

Ruta: `/api/asignaciones/{id}/devolucion/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `POST` | Técnico de soporte. | `201`, devolución registrada. |

`POST /api/asignaciones/{id}/devolucion/`

```json
{
  "condicion_fisica": "Con falla técnica",
  "motivo_devolucion": "Falla durante el uso",
  "observaciones": "El equipo no enciende"
}
```

| Campo | Condición |
| --- | --- |
| `condicion_fisica` | Obligatorio: `Buen estado`, `Con falla técnica` o `Con daño físico`. |
| `motivo_devolucion` | Opcional; máximo 100 caracteres. |
| `observaciones` | Opcional; descripción de la condición recibida. |
| `id_ticket_asociado` | Opcional; ticket activo del mismo equipo y solicitante, cuando existe falla o daño. |

La recepción y la evaluación inicial se completan en la misma operación. Una devolución ya registrada no admite una segunda evaluación mediante esta ruta. La devolución cierra la asignación y registra el resultado:

| Condición recibida | Estado del activo | Soporte |
| --- | --- | --- |
| Buen estado | Disponible | Queda habilitado para otra asignación. |
| Con falla técnica | En revisión | Se genera o asocia un ticket. |
| Con daño físico | En revisión | Se genera o asocia un ticket y se conservan las observaciones. |

Si ya existe un ticket activo del mismo equipo y solicitante, se reutiliza. Un ticket cerrado, resuelto o ajeno se rechaza. En una devolución en buen estado no corresponde enviar `id_ticket_asociado`.

La respuesta incluye `id_devolucion`, `id_asignacion`, `id_tecnico_receptor`, `tecnico_receptor`, `id_estado_activo_resultante`, `estado_activo_resultante`, `fecha_devolucion`, `condicion_fisica`, `motivo_devolucion` y `observaciones`. Se registra el historial del estado y la auditoría de la operación.

Una asignación inexistente responde `404`. Una asignación finalizada, una devolución duplicada o una condición inválida responde `400`.

Consultar [autenticación y uso general](../../uso_general.md) y [respuestas y errores](../../respuestas_y_errores.md).

[Volver a Gestión de Activos y Asignaciones](../README.md) · [Índice general](../../README.md)
