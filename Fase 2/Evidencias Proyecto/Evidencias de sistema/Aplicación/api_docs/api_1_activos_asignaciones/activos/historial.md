# Historial y trazabilidad de un equipo

Ruta: `GET /api/activos/historial/?search={identificador}`

Disponible para las cuentas autorizadas a consultar activos. El parámetro `search`
es obligatorio y acepta un código de inventario, número de serie o ID exacto.

La respuesta `200` contiene `activo`, `movimientos`, `total_movimientos` y `mensaje`.
Los movimientos se ordenan cronológicamente e incluyen asignaciones, devoluciones
y cambios de estado con sus fechas y usuarios asociados. Los cambios de estado
realizados al editar un activo incluyen al administrador que los registró.

Un equipo sin movimientos devuelve una lista vacía y un mensaje informativo.
Registrar un activo por sí solo no representa una asignación o devolución.

En el escritorio, **Solicitudes y entregas → Historial y Trazabilidad** permite
elegir un equipo desde el inventario o buscar su identificador. **Actualizar equipos**
recarga el selector. Al seleccionar un equipo se consulta automáticamente su historial;
un doble clic en un movimiento abre sus detalles.

Errores: `400` si falta el identificador, `403` si no hay autorización, `404` si el
equipo no existe y `409` si el identificador coincide con más de un equipo.

[Volver a Gestión de Activos y Asignaciones](../README.md) · [Índice general](../../README.md)
