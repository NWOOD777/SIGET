# Categorías de activos

Rutas:

- `/api/activos/categorias/`
- `/api/activos/categorias/{id}/`

| Método | Ruta | Acceso | Respuesta correcta |
|---|---|---|---|
| `GET` | `/api/activos/categorias/` | Administrador, Técnico o cuenta con permiso `CATALOGO_CONSULTAR`. | `200`, lista del catálogo (admite filtro opcional `?search=`). |
| `POST` | `/api/activos/categorias/` | Exclusivo `Administrador del sistema` activo. | `201`, categoría creada y auditada. |
| `GET` | `/api/activos/categorias/{id}/` | Administrador, Técnico o cuenta con permiso `CATALOGO_CONSULTAR`. | `200`, detalle del registro. |
| `PUT` / `PATCH` | `/api/activos/categorias/{id}/` | Exclusivo `Administrador del sistema` activo. | `200`, categoría actualizada y auditada. |
| `DELETE` | `/api/activos/categorias/{id}/` | Exclusivo `Administrador del sistema` activo. | `204` si no tiene referencias; `409` si está asociada a modelos o solicitudes de asignación. |

## Campos

- `id_categoria` (solo lectura): identificador único.
- `nombre` (obligatorio, máx. 100 caracteres): se recortan espacios exteriores, se colapsan espacios múltiples y se valida unicidad insensible a mayúsculas/minúsculas.
- `descripcion` (opcional, máx. 255 caracteres): texto descriptivo.

Todas las escrituras se ejecutan de forma atómica junto con `registrar_auditoria` (`CATEGORIA_CREADA`, `CATEGORIA_MODIFICADA`, `CATEGORIA_ELIMINADA`).

Consultar [autenticación y uso general](../../uso_general.md) y [respuestas y errores](../../respuestas_y_errores.md).

[Volver a Gestión de Activos y Asignaciones](../README.md) · [Índice general](../../README.md)
