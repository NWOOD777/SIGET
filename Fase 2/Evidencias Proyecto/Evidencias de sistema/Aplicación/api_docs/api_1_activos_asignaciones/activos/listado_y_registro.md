# Consultar y registrar activos

Ruta: `/api/activos/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `GET` | Administrador, Técnico o cuenta con permiso `CATALOGO_CONSULTAR`. | `200`, lista de activos. |
| `POST` | Administrador del sistema. | `201`, activo registrado. |

## Consultar

`GET /api/activos/` admite los siguientes filtros, combinables entre sí:

| Parámetro | Búsqueda |
| --- | --- |
| `search` | Identificador, código de inventario, serie, modelo o marca. |
| `tipo` | Nombre de la categoría, por ejemplo `Notebook`. |
| `ubicacion` | Identificador o nombre del área. |
| `estado` | Nombre del estado, por ejemplo `Disponible`. |

Ejemplo: `/api/activos/?tipo=Notebook&estado=Disponible`.

Cada registro utiliza la estructura de la [consulta de detalle del activo](detalle_y_modificacion.md).

## Registrar

`POST /api/activos/`

```json
{
  "numero_serie": "SN-NOTEBOOK-001",
  "id_modelo": 1,
  "id_ubicacion": 1,
  "valor_adquisicion": "650000.00",
  "fecha_compra": "2026-10-01",
  "fecha_garantia": "2027-10-01"
}
```

| Campo de entrada | Condición |
| --- | --- |
| `numero_serie` | Obligatorio y único; máximo 100 caracteres. |
| `id_modelo` | Obligatorio; debe existir en el catálogo de modelos. |
| `id_ubicacion` | Obligatorio; debe existir en el catálogo de ubicaciones. |
| `valor_adquisicion` | Opcional; valor inicial `0`. No admite montos negativos. |
| `fecha_compra`, `fecha_garantia` | Opcionales; admiten `null`. La garantía no puede terminar antes de la compra. |
| `id_estado_activo` | Opcional en edición. Al registrar, el estado inicial siempre es `Disponible`. |

El identificador, el código de inventario y la fecha de registro son asignados por el sistema. La respuesta sigue la misma estructura de la consulta de detalle.

Una serie repetida o datos inválidos responden `400`. Los catálogos relacionados se consultan antes de registrar el activo.

Consultar [autenticación y uso general](../../uso_general.md) y [respuestas y errores](../../respuestas_y_errores.md).

[Volver a Gestión de Activos y Asignaciones](../README.md) · [Índice general](../../README.md)
