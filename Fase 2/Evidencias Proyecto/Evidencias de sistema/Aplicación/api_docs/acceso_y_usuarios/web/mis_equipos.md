# Consultar Mis equipos

| Método | Ruta | Acceso |
|---|---|---|
| GET | `/mis-equipos/` | Usuario solicitante activo. |
| GET | `/mis-equipos/{id_asignacion}/` | Dueño de la asignación. |

El listado muestra los equipos con asignación vigente a nombre del usuario conectado, su modelo y las fechas de entrega y devolución prevista. `?historial=1` incluye las asignaciones finalizadas. El detalle agrega la serie y los estados del equipo y de su asignación. Un detalle inexistente o perteneciente a otra persona responde `404`. No se modifican las asignaciones desde estas páginas.

[Volver a acceso y usuarios](../README.md)
