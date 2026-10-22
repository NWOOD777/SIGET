# Consultar solicitudes y tickets propios

| Método | Ruta | Contenido |
|---|---|---|
| GET | `/solicitudes/{id}/` | Categoría, motivo, estado actual, fechas y motivo del rechazo cuando corresponda. |
| GET | `/tickets/{id}/` | Código, asunto, descripción, prioridad, estado actual, equipo, técnico y fechas disponibles. |

Estas vistas requieren sesión Web de un Usuario solicitante activo. Solo permiten consultar registros propios. Un registro ajeno o inexistente devuelve `404`; una cuenta sin acceso al portal recibe `403`. Las consultas no crean registros ni cambian estados.

El inicio del portal y los correos enlazan a estas páginas de detalle. La creación desde los formularios conduce primero a `/solicitudes/{id}/confirmacion/` o `/tickets/{id}/confirmacion/`. La confirmación se muestra una sola vez en la sesión que registró el caso; las visitas posteriores redirigen al detalle. Así, los enlaces anteriores conservan su utilidad sin mostrar nuevamente un mensaje de registro exitoso.

[Acceso y usuarios](../README.md) · [Índice general](../../README.md)
