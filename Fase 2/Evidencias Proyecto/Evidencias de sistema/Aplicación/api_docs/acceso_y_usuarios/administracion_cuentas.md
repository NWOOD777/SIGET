# Administrar estado y eliminación de cuentas

Ruta: `/api/usuarios/{id}/`

Exclusiva para el Administrador del sistema activo, validado contra PostgreSQL.
Las operaciones requieren confirmación en el escritorio y se registran en auditoría.

| Método | Datos | Respuesta correcta |
|---|---|---|
| `PATCH` | `{"activo": false}` para desactivar; `true` para reactivar. | `200`, cuenta y acceso actualizado. |
| `DELETE` | Sin cuerpo. | `204`, sin cuerpo de respuesta. |

Desactivar bloquea el acceso a SIGET, incluidas sesiones y tokens existentes en las
siguientes peticiones al backend. Conserva la identidad externa, los roles y todos
los registros asociados. Reactivar vuelve a habilitar el acceso local con los roles
vigentes; no modifica credenciales ni recupera una identidad eliminada del proveedor.

La eliminación definitiva se admite solamente si la cuenta no tiene actividad ni
referencias de negocio o auditoría. Se eliminan la cuenta local, sus asociaciones de
roles y su identidad en Auth0. Un usuario con solicitudes, entregas, tickets u otra
actividad responde `409`; se puede desactivar su acceso conservando el historial.
El Administrador no puede eliminar ni desactivar su propia cuenta.

Si Auth0 informa un error de eliminación, se revierte la transacción local y se
responde `502`. Si la identidad externa ya no existe (`404` del proveedor), se admite
completar la eliminación local. La comunicación con el proveedor tiene un tiempo
límite; ante una respuesta incierta se conserva la cuenta local y se puede reintentar.
La transacción de PostgreSQL no incluye la infraestructura externa de Auth0.

Errores: `400` para estado inválido, `403` para falta de autorización o CSRF en sesión
Web, `404` para cuenta inexistente y `409` para una cuenta protegida.

[Volver a acceso y usuarios](README.md) · [Índice general](../README.md)
