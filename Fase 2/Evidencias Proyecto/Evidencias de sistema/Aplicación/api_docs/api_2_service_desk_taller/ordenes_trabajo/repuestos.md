# Repuestos de una orden de trabajo

Estas operaciones requieren una cuenta activa con el rol **Técnico de soporte**. La autorización se comprueba en PostgreSQL. Las peticiones con sesión Web también requieren protección CSRF.

## Consultar imputaciones

`GET /api/ordenes-trabajo/{id_orden}/repuestos/`

Devuelve el código y estado de la OT, sus imputaciones vigentes y anuladas, y un resumen de unidades y costos vigentes. El detalle y el resumen corresponden a las mismas imputaciones. Las anuladas conservan su costo histórico y sus datos de anulación, pero se excluyen del total vigente.

## Asignar un repuesto

`POST /api/ordenes-trabajo/{id_orden}/repuestos/`

```json
{"id_repuesto": 4, "cantidad": 2}
```

La OT debe estar **En Reparación** y el repuesto debe estar activo y tener existencias suficientes. La cantidad debe ser un entero positivo. Una operación válida devuelve `201`, registra la imputación y una salida de inventario, descuenta el stock y registra auditoría en una misma transacción.

El costo unitario queda fijado al valor del repuesto al momento de la imputación. Las compras posteriores no modifican el costo histórico de la reparación.

## Anular una imputación

`POST /api/ordenes-trabajo/{id_orden}/repuestos/{id_orden_repuesto}/anular/`

```json
{"motivo": "La pieza no fue utilizada en la reparación"}
```

Requiere una imputación vigente de esa OT y un motivo de entre 1 y 255 caracteres. La OT debe permanecer **En Reparación**. Devuelve `200`, reintegra las unidades, recalcula el costo promedio del inventario y registra el movimiento y la auditoría. Conserva la imputación original con fecha, motivo y usuario de anulación. Una segunda anulación se rechaza sin volver a reintegrar unidades.

Los errores de validación devuelven `400`. Una OT inexistente en la consulta devuelve `404`. Los rechazos de acceso siguen el [contrato general de respuestas](../../respuestas_y_errores.md).

## Uso desde el escritorio

En **Órdenes de Trabajo**, seleccionar una OT y abrir **Gestionar repuestos**. Las órdenes en reparación permiten buscar piezas, revisar el costo y confirmar el consumo o la anulación. Las demás muestran el historial de imputaciones. Después de cada operación se actualizan las imputaciones, el total y el catálogo de existencias.
