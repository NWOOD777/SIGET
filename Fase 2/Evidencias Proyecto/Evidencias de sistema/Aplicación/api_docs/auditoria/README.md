# Bitácora de auditoría

La bitácora permite consultar quién realizó una operación, cuándo ocurrió y qué
registro afectó. Requiere una cuenta activa de **Administrador del sistema** y
el permiso `AUDITORIA_CONSULTAR`.

| Método | Ruta | Función |
|---|---|---|
| GET | `/api/auditoria/` | Consultar eventos con filtros y paginación. |
| GET | `/api/auditoria/{id}/` | Ver el detalle de un evento. |
| GET | `/api/auditoria/opciones/` | Buscar actores o equipos para aplicar un filtro. |

## Filtros del listado

| Parámetro | Uso |
|---|---|
| `usuario` | ID del actor si es numérico; nombre o correo si es texto. |
| `id_usuario` | ID exacto del actor: entero positivo de hasta 2147483647. |
| `activo` o `codigo_inventario` | Código de inventario exacto. |
| `modulo` | Módulo, como `ACTIVOS`, `ASIGNACIONES` o `SERVICE_DESK`. |
| `accion` | Código de acción, como `ACTIVO_MODIFICADO`. |
| `page` | Página desde 1; valor inicial 1. |
| `page_size` o `limite` | Entre 1 y 100 registros; valor inicial 25. |

Los filtros se combinan. El actor es quien ejecutó la acción, no necesariamente
el solicitante o custodio del equipo. Los eventos automáticos pueden tener
`id_usuario: null`.

El filtro de equipo incluye sus movimientos relacionados: asignaciones,
devoluciones, solicitudes entregadas, tickets, atenciones, evaluaciones,
diagnósticos e intervenciones. Los resultados se ordenan del más reciente al
más antiguo, usando el ID para desempatar fechas iguales.

## Respuesta del listado

```json
{
  "count": 1,
  "page": 1,
  "page_size": 25,
  "total_pages": 1,
  "results": [{
    "id_auditoria": 158,
    "fecha_evento": "2026-10-23T19:40:12+00:00",
    "id_usuario": 1,
    "usuario": "Administrador Principal",
    "usuario_correo": "admin@example.org",
    "modulo": "ACTIVOS",
    "accion": "ACTIVO_MODIFICADO",
    "entidad_afectada": "activo",
    "id_registro_afectado": 12,
    "recurso": "activo #12",
    "detalle_evento": "Estado del activo actualizado.",
    "direccion_ip": "192.168.1.150"
  }]
}
```

Sin coincidencias devuelve `200` con `results: []`, `count: 0` y `total_pages: 0`.
El detalle devuelve `200` con un evento o `404` si no existe.

## Opciones para seleccionar filtros

`GET /api/auditoria/opciones/?tipo=usuario|activo&search=texto`

Devuelve `results` y `has_more`, con hasta 20 opciones por consulta. La búsqueda
admite hasta 120 caracteres. Los actores incluyen `id` y `etiqueta`; los equipos,
`codigo` y `etiqueta`. Si hay más resultados, se debe acotar la búsqueda.

## Uso desde el escritorio

En **Auditoría interna**, usar **Elegir actor** o **Elegir equipo**, o escribir un
filtro y pulsar **Buscar**. Seleccionar una fila y abrir **Ver detalle**, o hacer
doble clic sobre ella. Los controles de página permiten recorrer los resultados;
**Limpiar filtros** vuelve a la consulta general.

Las fechas se muestran en la hora local del computador, con su desfase UTC.
La vista no permite editar ni borrar eventos. La API rechaza los métodos de
escritura con `405` y las consultas no generan eventos nuevos.

Las respuestas no muestran RUT, contraseñas ni tokens. Los textos de eventos
antiguos ocultan identificadores con formato de RUT. La IP corresponde a la
conexión que recibe el backend; con Docker puede ser la dirección de su red interna.

[Respuestas y errores](../respuestas_y_errores.md) · [Índice de APIs](../README.md)
