# Calificación de servicio (CSAT) e indicadores por técnico

Rutas:

- `GET, POST /api/tickets/{id}/csat/`
- `GET /api/tickets/indicadores-csat/`
- `GET /api/tickets/indicadores-csat/{id_tecnico}/`

| Método | Ruta | Acceso | Respuesta correcta |
|---|---|---|---|
| `GET` | `/api/tickets/{id}/csat/` | Usuario solicitante activo titular del ticket. | `200`, evaluación CSAT registrada en modo lectura. |
| `POST` | `/api/tickets/{id}/csat/` | Usuario solicitante activo titular del ticket (con permiso `TICKET_CREAR` o rol efectivo `Usuario solicitante`). | `201`, evaluación CSAT creada. |
| `GET` | `/api/tickets/indicadores-csat/` | Administrador del sistema (todos o filtrado por `?tecnico={id}`) o Técnico de soporte (solo sus propios indicadores). | `200`, listado o detalle de indicadores CSAT. |
| `GET` | `/api/tickets/indicadores-csat/{id_tecnico}/` | Administrador del sistema (cualquier técnico) o Técnico de soporte (solo su propio `id_tecnico`). | `200`, indicadores CSAT del técnico. |

No se exponen métodos `PUT`, `PATCH` ni `DELETE` sobre `/api/tickets/{id}/csat/` (responden `405 Method Not Allowed`). Una vez registrada, la evaluación no puede editarse ni eliminarse.

---

## 1. Elegibilidad y reglas de negocio

- **Titularidad y rol**: únicamente un usuario autenticado, activo y con rol **Usuario solicitante** puede evaluar o consultar la evaluación CSAT de un ticket registrado a su propio nombre (`ticket.id_usuario_solicitante == usuario.id_usuario`). Ni un **Administrador del sistema** ni un **Técnico de soporte** pueden calificar en nombre del solicitante.
- **Estado del ticket**: el ticket debe haber completado su flujo de atención y encontrarse en estado **Cerrado** (alcanzado después de **Resuelto**). No se habilita la evaluación cuando el ticket está en **Abierto**, **En Proceso**, **En Espera** ni cuando únicamente está **Resuelto**.
- **Independencia de orden de trabajo (OT)**: la elegibilidad depende del cierre del ticket en Service Desk. También pueden evaluarse tickets de soporte que fueron resueltos y cerrados sin requerir una orden de trabajo física en taller.
- **Determinación por el servidor**: el backend determina exclusivamente `id_ticket`, `id_usuario` y `fecha_evaluacion`. Cualquier intento de enviar `id_usuario`, `id_ticket`, `fecha_evaluacion`, `id_tecnico_asignado` o roles en el cuerpo de la solicitud es ignorado.

---

## 2. Registrar evaluación CSAT

**POST `/api/tickets/{id}/csat/`**

### Cuerpo de solicitud

```json
{
  "calificacion_estrellas": 5,
  "comentario": "Atención oportuna y solución definitiva del incidente."
}
```

- `calificacion_estrellas` (obligatorio): entero estricto entre `1` y `5`. Se aceptan cadenas de dígitos provenientes de formularios HTML (`"1"` a `"5"`) mediante conversión validada. Se rechazan valores nulos, vacíos, booleanos (`true`/`false`), decimales (`3.0`, `3.5`, `"3.0"`) y enteros fuera del rango `1..5`.
- `comentario` (opcional): texto libre. Se recortan espacios exteriores; si se omite, se envía `null` o contiene solo espacios en blanco, se almacena como `null`.

### Respuesta `201 Created`

```text
{
  "id_evaluacion": <id_generado>,
  "id_ticket": <id_real_del_ticket>,
  "codigo_ticket": "<codigo_del_ticket>",
  "id_usuario": <id_del_solicitante_autenticado>,
  "calificacion_estrellas": 5,
  "comentario": "Atención oportuna y solución definitiva del incidente.",
  "fecha_evaluacion": "<fecha_hora_del_servidor_en_formato_ISO_8601>"
}
```

### Auditoría y atomicidad

La creación se ejecuta dentro de una transacción atómica que:

1. Bloquea la fila del ticket mediante `Ticket.objects.select_for_update(of=("self",))`.
2. Revalida titularidad, estado **Cerrado** y ausencia de evaluación previa bajo el bloqueo.
3. Inserta el registro en `evaluacion_csat` y registra el evento `TICKET_CSAT_REGISTRADO` en `bitacora_auditoria` (`modulo="SERVICE_DESK"`, `entidad_afectada="evaluacion_csat"`).

Si falla el registro en bitácora de auditoría, toda la transacción se revierte y no persiste la evaluación.

### Comportamiento ante duplicados y concurrencia

Cada ticket admite como máximo una evaluación (`UNIQUE (id_ticket)` en `evaluacion_csat` + bloqueo de fila en el servicio):

- Si el ticket ya fue evaluado, un segundo envío devuelve **400 Bad Request** sin modificar la evaluación existente ni generar nuevos eventos de auditoría:
  ```json
  {
    "detail": "Este ticket ya cuenta con una evaluación de satisfacción registrada."
  }
  ```
- Los envíos simultáneos se procesan por turnos mediante un bloqueo sobre el ticket. La restricción `UNIQUE` permite guardar una sola evaluación: el primer envío responde `201 Created` y el segundo, `400 Bad Request`.

---

## 3. Consultar evaluación CSAT

**GET `/api/tickets/{id}/csat/`**

Permite al **Usuario solicitante** dueño del ticket consultar en modo solo lectura la evaluación previamente registrada. La consulta no modifica registros ni genera eventos de auditoría.

- **Respuesta `200 OK`**: mismo esquema de `EvaluacionCSATReadSerializer` descrito arriba.
- **Respuesta `404 Not Found`**: cuando el ticket no existe o cuando aún no registra una evaluación CSAT.

---

## 4. Errores de `/api/tickets/{id}/csat/`

| Código HTTP | Caso | Cuerpo de respuesta |
|---|---|---|
| `400 Bad Request` | Puntuación ausente, nula, booleana, decimal o fuera del rango `1..5`, o comentario no textual. | `{"calificacion_estrellas": ["..."]}` o `{"comentario": ["..."]}` |
| `400 Bad Request` | Ticket en estado distinto de **Cerrado** (`Abierto`, `En Proceso`, `En Espera`, `Resuelto`). | `{"detail": "Solo se pueden evaluar tickets cuyo flujo haya finalizado en estado Cerrado."}` |
| `400 Bad Request` | Ticket previamente evaluado (envío duplicado o concurrente). | `{"detail": "Este ticket ya cuenta con una evaluación de satisfacción registrada."}` |
| `401 Unauthorized` | Token Bearer inválido o expirado. | `{"detail": "..."}` |
| `403 Forbidden` | Usuario anónimo, inactivo, con rol distinto de **Usuario solicitante** (p. ej. Administrador o Técnico), ticket perteneciente a otro solicitante, o fallo CSRF en sesión Web. | `{"detail": "..."}` |
| `404 Not Found` | El ticket no existe, o en `GET` el ticket aún no tiene evaluación CSAT. | `{"detail": "Ticket no encontrado."}` o `{"detail": "El ticket no registra una evaluación CSAT."}` |
| `405 Method Not Allowed` | Intento de usar `PUT`, `PATCH` o `DELETE`. | `{"detail": "Method \"...\" not allowed."}` |

---

## 5. Indicadores CSAT por técnico

Los indicadores resumen las calificaciones recibidas en los tickets asignados a cada técnico:

- Se calculan en tiempo real desde los registros persistidos siguiendo la relación `evaluacion_csat → ticket → id_tecnico_asignado`, sin añadir columnas ni contadores redundantes en la tabla `usuario`.
- Métricas expuestas por técnico:
  - `cantidad_evaluaciones`: total entero de evaluaciones CSAT asociadas a tickets asignados al técnico (`0` cuando no registra evaluaciones).
  - `promedio_estrellas`: promedio aritmético de `calificacion_estrellas` redondeado a 2 decimales, o `null` cuando `cantidad_evaluaciones == 0`.

### Endpoints de consulta de indicadores

1. **`GET /api/tickets/indicadores-csat/`**
   - **Administrador del sistema**: retorna la lista de todos los usuarios con rol **Técnico de soporte** y sus indicadores CSAT, o bien los indicadores de un técnico específico si se envía el parámetro `?tecnico=<id_tecnico>`.
   - **Técnico de soporte**: retorna exclusivamente el objeto con sus propios indicadores CSAT. Si solicita `?tecnico=<id_otro_tecnico>`, responde `403 Forbidden`.
2. **`GET /api/tickets/indicadores-csat/{id_tecnico}/`**
   - **Administrador del sistema**: retorna los indicadores del técnico `{id_tecnico}` (`404` si no existe o no posee rol de técnico).
   - **Técnico de soporte**: retorna `200 OK` únicamente cuando `{id_tecnico}` coincide con su propio `id_usuario`; en caso contrario responde `403 Forbidden`.
   - **Usuario solicitante / Anónimo**: responde `403 Forbidden`.

### Ejemplo de respuesta (`200 OK`)

```text
{
  "id_tecnico": <id_real_del_tecnico>,
  "nombres": "<nombres>",
  "apellidos": "<apellidos>",
  "correo": "<correo>",
  "cantidad_evaluaciones": 2,
  "promedio_estrellas": 4.5
}
```

Cuando el técnico aún no cuenta con evaluaciones registradas:

```text
{
  "id_tecnico": <id_real_del_tecnico>,
  "nombres": "<nombres>",
  "apellidos": "<apellidos>",
  "correo": "<correo>",
  "cantidad_evaluaciones": 0,
  "promedio_estrellas": null
}
```

[Volver a Service Desk y Taller/Reparaciones](../README.md) · [Índice general](../../README.md)

