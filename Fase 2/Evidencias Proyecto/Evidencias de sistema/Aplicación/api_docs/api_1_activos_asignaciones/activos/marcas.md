# Marcas de activos

Rutas:

- `/api/activos/marcas/`
- `/api/activos/marcas/{id}/`

| Método | Ruta | Acceso | Respuesta correcta |
|---|---|---|---|
| `GET` | `/api/activos/marcas/` | Administrador, Técnico o cuenta con permiso `CATALOGO_CONSULTAR`. | `200`, lista del catálogo (admite filtro opcional `?search=`). |
| `POST` | `/api/activos/marcas/` | Exclusivo `Administrador del sistema` activo. | `201`, marca creada y auditada. |
| `GET` | `/api/activos/marcas/{id}/` | Administrador, Técnico o cuenta con permiso `CATALOGO_CONSULTAR`. | `200`, detalle del registro. |
| `PUT` / `PATCH` | `/api/activos/marcas/{id}/` | Exclusivo `Administrador del sistema` activo. | `200`, marca actualizada y auditada. |
| `DELETE` | `/api/activos/marcas/{id}/` | Exclusivo `Administrador del sistema` activo. | `204` si no tiene referencias; `409` si está asociada a modelos de activos. |

## Campos

- `id_marca` (solo lectura): identificador único.
- `nombre` (obligatorio, máx. 100 caracteres): se recortan espacios exteriores, se colapsan espacios múltiples y se valida unicidad insensible a mayúsculas/minúsculas.

Todas las escrituras se ejecutan de forma atómica junto con `registrar_auditoria` (`MARCA_CREADA`, `MARCA_MODIFICADA`, `MARCA_ELIMINADA`).

Consultar [autenticación y uso general](../../uso_general.md) y [respuestas y errores](../../respuestas_y_errores.md).

[Volver a Gestión de Activos y Asignaciones](../README.md) · [Índice general](../../README.md)
