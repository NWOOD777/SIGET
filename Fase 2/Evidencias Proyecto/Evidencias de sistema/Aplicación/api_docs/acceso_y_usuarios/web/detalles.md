# Consultar solicitudes y tickets propios

| Método | Ruta | Contenido |
|---|---|---|
| GET | `/solicitudes/{id}/` | Categoría, motivo, estado actual, fechas y motivo del rechazo cuando corresponda. |
| GET, POST | `/tickets/{id}/` | Código, asunto, descripción, prioridad, estado actual, equipo, técnico, fechas disponibles y sección de calificación CSAT. |
| POST | `/tickets/{id}/csat/` | Ruta auxiliar de envío del formulario CSAT integrada con el detalle del ticket. |

Estas vistas requieren sesión Web de un Usuario solicitante activo. Solo permiten consultar registros propios. Un registro ajeno o inexistente devuelve `404`; una cuenta sin acceso al portal recibe `403`. Las consultas `GET` no crean registros ni cambian estados.

En `/tickets/{id}/`, la sección de **Calificación de servicio (CSAT)** adapta su comportamiento según el estado del ticket:

- **Ticket propio en estado `Cerrado` sin evaluación**: presenta el formulario protegido con CSRF para calificar de 1 a 5 estrellas con comentario opcional. Tras un envío válido aplica el patrón `POST/Redirect/GET` hacia `/tickets/{id}/`, mostrando por única vez un mensaje de confirmación y agradecimiento.
- **Ticket ya evaluado**: muestra la puntuación otorgada, el comentario (escapado como texto seguro) y la fecha de evaluación en modo de solo lectura, sin habilitar edición ni reenvío.
- **Ticket aún no cerrado (`Abierto`, `En Proceso`, `En Espera` o `Resuelto`)**: informa que la calificación estará disponible únicamente cuando el ticket alcance el estado `Cerrado`.

El inicio del portal y los correos enlazan a estas páginas de detalle. La creación desde los formularios conduce primero a `/solicitudes/{id}/confirmacion/` o `/tickets/{id}/confirmacion/`. La confirmación se muestra una sola vez en la sesión que registró el caso; las visitas posteriores redirigen al detalle. Así, los enlaces anteriores conservan su utilidad sin mostrar nuevamente un mensaje de registro exitoso.

[Acceso y usuarios](../README.md) · [Índice general](../../README.md)
