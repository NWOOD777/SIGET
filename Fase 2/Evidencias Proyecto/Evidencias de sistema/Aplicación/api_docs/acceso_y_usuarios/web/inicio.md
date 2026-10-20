# Acceder al portal

Ruta: `/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `GET` | Público para acceso; portal para Solicitante. | `200`, página de acceso o portal. |

Una cuenta autenticada sin rol de Usuario solicitante recibe `403` al intentar abrir el portal. Esta condición no impide el acceso del Técnico o Administrador a los endpoints REST autorizados. La preparación de las peticiones con sesión se explica en [uso general](../../uso_general.md#mecanismos-de-autenticación).

Consulta [autenticación y uso general](../../uso_general.md) y [respuestas y errores](../../respuestas_y_errores.md).

[Volver a acceso y usuarios](../README.md) · [Índice general](../../README.md)

El resumen utiliza las asignaciones vigentes, solicitudes pendientes o aprobadas y tickets activos del usuario conectado. Muestra sus registros recientes y estados vacíos cuando corresponde. Notificaciones permanece pendiente.
