# Ubicaciones de activos

Rutas:

- `/api/activos/ubicaciones/`
- `/api/activos/ubicaciones/{id}/`

| Método | Ruta | Acceso | Respuesta correcta |
|---|---|---|---|
| `GET` | `/api/activos/ubicaciones/` | Administrador, Técnico o cuenta con permiso `CATALOGO_CONSULTAR`. | `200`, lista del catálogo (admite filtro opcional `?search=`). |
| `POST` | `/api/activos/ubicaciones/` | Exclusivo `Administrador del sistema` activo. | `201`, ubicación creada y auditada. |
| `GET` | `/api/activos/ubicaciones/{id}/` | Administrador, Técnico o cuenta con permiso `CATALOGO_CONSULTAR`. | `200`, detalle del registro. |
| `PUT` / `PATCH` | `/api/activos/ubicaciones/{id}/` | Exclusivo `Administrador del sistema` activo. | `200`, ubicación actualizada y auditada. |
| `DELETE` | `/api/activos/ubicaciones/{id}/` | Exclusivo `Administrador del sistema` activo. | `204` si no tiene referencias; `409` si existen activos registrados en la ubicación. |

## Campos y reglas de identidad

- `id_ubicacion` (solo lectura): identificador único.
- `nombre_area` (obligatorio, máx. 100 caracteres): área, dependencia o sala.
- `edificio` (opcional, máx. 50 caracteres): edificio o bloque físico.
- `piso` (opcional, máx. 20 caracteres): piso o nivel.

### Identidad funcional
La unicidad de una ubicación se evalúa sobre la combinación normalizada `(nombre_area, edificio, piso)`. Se permite registrar la misma área en edificios o pisos distintos (por ejemplo, `Laboratorio` en `Edificio A` y `Laboratorio` en `Edificio B`), pero se rechazan duplicados equivalentes con la misma área, edificio y piso.

Todas las escrituras se ejecutan de forma atómica junto con `registrar_auditoria` (`UBICACION_CREADA`, `UBICACION_MODIFICADA`, `UBICACION_ELIMINADA`).

Consultar [autenticación y uso general](../../uso_general.md) y [respuestas y errores](../../respuestas_y_errores.md).

[Volver a Gestión de Activos y Asignaciones](../README.md) · [Índice general](../../README.md)
