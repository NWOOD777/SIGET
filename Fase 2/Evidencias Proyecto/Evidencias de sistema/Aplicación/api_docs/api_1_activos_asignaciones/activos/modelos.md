# Modelos de activos

Rutas:

- `/api/activos/modelos/`
- `/api/activos/modelos/{id}/`

| Método | Ruta | Acceso | Respuesta correcta |
|---|---|---|---|
| `GET` | `/api/activos/modelos/` | Administrador, Técnico o cuenta con permiso `CATALOGO_CONSULTAR`. | `200`, lista del catálogo (admite filtro opcional `?search=`). |
| `POST` | `/api/activos/modelos/` | Exclusivo `Administrador del sistema` activo. | `201`, modelo creado y auditado. |
| `GET` | `/api/activos/modelos/{id}/` | Administrador, Técnico o cuenta con permiso `CATALOGO_CONSULTAR`. | `200`, detalle del registro. |
| `PUT` / `PATCH` | `/api/activos/modelos/{id}/` | Exclusivo `Administrador del sistema` activo. | `200`, modelo actualizado y auditado. |
| `DELETE` | `/api/activos/modelos/{id}/` | Exclusivo `Administrador del sistema` activo. | `204` si no tiene referencias; `409` si existen activos asociados al modelo. |

## Campos y reglas de integridad

- `id_modelo` (solo lectura): identificador único.
- `nombre` (obligatorio, máx. 100 caracteres): nombre comercial o técnico del modelo.
- `id_marca` (obligatorio): clave foránea a `marca` existente.
- `id_categoria` (obligatorio): clave foránea a `categoria_activo` existente.
- `marca` y `categoria` (solo lectura): nombres legibles resueltos desde las relaciones.

### Reglas de negocio

- **Identidad compuesta:** no se permiten dos modelos con la misma combinación `(id_marca, id_categoria, nombre)` normalizada.
- **Protección del significado histórico:** cuando un modelo ya está asociado a activos registrados, se permite corregir su `nombre` con auditoría, pero se bloquea cambiar `id_marca` o `id_categoria` (`400 Bad Request`) para no alterar retroactivamente la categoría e interpretación histórica de los activos e inventario.

Todas las escrituras se ejecutan de forma atómica junto con `registrar_auditoria` (`MODELO_CREADO`, `MODELO_MODIFICADO`, `MODELO_ELIMINADO`).

Consultar [autenticación y uso general](../../uso_general.md) y [respuestas y errores](../../respuestas_y_errores.md).

[Volver a Gestión de Activos y Asignaciones](../README.md) · [Índice general](../../README.md)
