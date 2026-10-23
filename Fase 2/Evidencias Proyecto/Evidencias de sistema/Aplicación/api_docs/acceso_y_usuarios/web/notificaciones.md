# Centro de notificaciones en plataforma

| Método | Ruta | Acceso |
|---|---|---|
| GET | `/notificaciones/` | Usuario solicitante activo. |
| GET | `/notificaciones/{id_notificacion}/` | Dueño del aviso (`PLATAFORMA` o `AMBOS`). |
| POST | `/notificaciones/{id_notificacion}/leer/` | Dueño del aviso (`PLATAFORMA` o `AMBOS`), protegido con CSRF. |
| POST | `/notificaciones/{id_notificacion}/abrir/` | Dueño del aviso (`PLATAFORMA` o `AMBOS`), protegido con CSRF. |

El centro de avisos en plataforma (E10-H29) permite al Usuario solicitante consultar los avisos generados por cambios en sus solicitudes de asignación, entregas y devoluciones de equipos, y actualizaciones de tickets de soporte:

- **Indicador en barra superior**: todas las páginas del portal calculan `notificaciones_pendientes` a partir de las filas propias con `leida = FALSE` y canal `PLATAFORMA` o `AMBOS`, mostrando el contador numérico en el icono de notificaciones de la barra superior.
- **Listado (`GET /notificaciones/`)**: muestra los avisos propios de canal `PLATAFORMA` o `AMBOS` ordenados desde el más reciente. Permite filtrar pendientes mediante `?filtro=pendientes`. Cuando no existen avisos pendientes de lectura, informa `No tienes notificaciones pendientes en este momento`.
- **Detalle (`GET /notificaciones/{id_notificacion}/`)**: presenta el título, módulo de origen, fecha de emisión, estado de lectura y mensaje completo. Las consultas `GET` de listado o detalle no modifican `leida`.
- **Lectura (`POST /notificaciones/{id_notificacion}/leer/`)**: marca el aviso como leído (`leida = TRUE`) de forma idempotente en PostgreSQL y redirige a `/notificaciones/{id_notificacion}/`, sin alterar el estado ni la cola de envío de correo.
- **Acceso al recurso (`POST /notificaciones/{id_notificacion}/abrir/`)**: marca el aviso como leído y redirige directamente a la ruta interna verificada del recurso propio (`/solicitudes/{id}/`, `/tickets/{id}/` o `/mis-equipos/{id}/`). Si el recurso ya no está disponible, redirige al detalle del aviso sin producir error.

Los avisos de canal exclusivo `CORREO_API` (como recordatorios programados de devolución) y los avisos de otros usuarios no se listan ni pueden consultarse (responden `404`). No se exponen `datos_envio`, destinatarios ni errores internos del proveedor.

[Volver a acceso y usuarios](../README.md)

