# Alcance frente a la arquitectura preliminar

La organización sigue la sección 4.3 y el Anexo B del [Documento de Diseño y Arquitectura Preliminar SIGET](../../../Evidencias%20de%20documentaci%C3%B3n/Arquitectura/Documento%20de%20Dise%C3%B1o%20y%20Arquitectura%20Preliminar%20SIGET.docx). Sus contratos son preliminares; los documentos de endpoints de esta carpeta describen las rutas y permisos que implementa el backend.

| Grupo | Implementación disponible |
|---|---|
| API 1 — Gestión de Activos y Asignaciones | Activos, catálogos, solicitudes, decisiones, entrega, asignaciones y devolución con evaluación inicial. |
| API 2 — Service Desk y Taller/Reparaciones | Creación y consulta de tickets, catálogos y políticas de servicio. |
| Acceso y usuarios | Servicios compartidos de identidad y RBAC local para ambos canales. |
| APIs externas | Auth0 integrado. Correo transaccional y generación QR pendientes. |

Estas rutas del Anexo B todavía no están registradas en el backend:

| API | Método previsto | Ruta prevista | Función pendiente |
|---|---|---|---|
| Service Desk y Taller/Reparaciones | POST | `/api/tickets/{id}/asignar/` | Asignar o reasignar un Técnico. |
| Service Desk y Taller/Reparaciones | POST | `/api/ordenes-trabajo/` | Abrir orden de trabajo. |
| Service Desk y Taller/Reparaciones | POST | `/api/diagnosticos/` | Registrar diagnóstico. |
| Service Desk y Taller/Reparaciones | POST | `/api/repuestos/asignar/` | Registrar consumo de repuestos. |
| Service Desk y Taller/Reparaciones | GET | `/api/auditoria/` | Consultar bitácora de auditoría. |

El flujo que conecta ambas APIs se explica en [devolución y evaluación inicial](api_1_activos_asignaciones/asignaciones/devolucion.md). Los modelos de datos existentes no acreditan por sí solos endpoints de taller, reparación o reportería.

El correo de contraseña enviado por Auth0 pertenece a la integración de identidad y no corresponde al correo transaccional de notificaciones de negocio. La lectura de códigos con dispositivos USB HID es una integración local del escritorio y no se contabiliza como API externa.

El registro manual de tickets corresponde al Solicitante mediante la sesión Web. Administrador y Técnico consultan los tickets desde el escritorio para su gestión. La devolución con fallas puede generar un ticket automáticamente. Los servicios de usuarios y catálogos amplían el detalle de las operaciones del Anexo B.

[Índice general](README.md)
