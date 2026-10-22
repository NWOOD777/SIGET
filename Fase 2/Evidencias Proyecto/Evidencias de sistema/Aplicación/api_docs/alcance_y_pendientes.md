# Organización de las APIs

La documentación agrupa los servicios del backend y las integraciones externas según su función.

| Grupo | Contenido | Documentación |
|---|---|---|
| Gestión de Activos y Asignaciones | Inventario, catálogos, solicitudes, aprobación o rechazo, entregas y devoluciones. | [API 1](api_1_activos_asignaciones/README.md) |
| Service Desk y Taller/Reparaciones | Tickets de soporte, prioridades, estados y políticas de servicio. | [API 2](api_2_service_desk_taller/README.md) |
| Acceso y usuarios | Identidad, sesión, aprovisionamiento, roles y permisos. | [Acceso y usuarios](acceso_y_usuarios/README.md) |
| Integraciones externas | Autenticación con Auth0 y correo transaccional con Resend. | [APIs externas](externas/README.md) |

Cada documento de endpoint describe los métodos, permisos, entradas y respuestas de su operación. Los mecanismos de autenticación se explican en [uso general](uso_general.md).

La [devolución y evaluación de equipos](api_1_activos_asignaciones/asignaciones/devolucion.md) puede generar un ticket de soporte asociado al activo. Las operaciones de negocio se ejecutan en el backend y sus permisos se validan con los roles de PostgreSQL.

El correo de recuperación de acceso pertenece al flujo de identidad de Auth0. Las notificaciones de solicitudes y devoluciones utilizan el servicio de correo transaccional. La lectura de códigos mediante dispositivos USB HID corresponde al cliente de escritorio.

[Índice general](README.md)
