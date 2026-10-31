# Cierre técnico desde el escritorio

En **Órdenes de trabajo**, seleccionar una OT y pulsar **Cierre técnico**.
La acción está disponible para un Técnico de soporte con los permisos de gestión,
cuando la orden está **En Diagnóstico** o **En Reparación**.

1. Elegir el resultado: **Reparación exitosa** o **Equipo no reparable**.
2. Para una reparación exitosa, describir la solución y las pruebas realizadas.
   Esta opción requiere una orden **En Reparación**.
3. Para un equipo no reparable, completar el informe de descarte.
4. Revisar los estados finales indicados y confirmar.

Ambos resultados completan la OT y resuelven el ticket. Una reparación exitosa
deja el activo **Disponible**; el descarte lo deja **Dado de baja**.

Mientras se guarda, se bloquea el envío para evitar duplicados. Los errores de
validación permiten corregir el formulario. Si se pierde la conexión durante
el envío, consultar el estado de la OT antes de repetir la operación.

Después del cierre se actualizan los listados y se conserva el historial de
diagnósticos y repuestos. Las órdenes completadas permiten consultar sus consumos,
pero no registrar consumos nuevos ni anularlos.

[Contrato de la API](cierre_tecnico_api.md) · [Órdenes de trabajo](gestion.md)
