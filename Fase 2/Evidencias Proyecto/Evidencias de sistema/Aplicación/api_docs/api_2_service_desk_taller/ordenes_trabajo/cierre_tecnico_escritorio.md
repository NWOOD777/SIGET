# E6-H17 — Cierre técnico desde PySide6

En Órdenes de trabajo, seleccionar una OT y pulsar **Cierre técnico**.
La acción aparece con sesión autenticada, acceso de escritorio, rol Técnico de
soporte y permisos OT_GESTIONAR y TICKET_ATENDER, para OT En Diagnóstico o En
Reparación. No exige ser el responsable original. La sesión usa el perfil efectivo
del servidor; no guarda un indicador activo separado. El backend vuelve a verificar
actividad, roles, permisos, estados y relaciones al ejecutar.

## Formulario

- Reparación exitosa: disponible solo En Reparación. Exige solución y pruebas.
- Equipo no reparable: disponible En Diagnóstico y En Reparación. Exige informe
  técnico y advierte que el activo será Dado de baja.
- No hay campos de actor, fecha ni estados finales.
- Los textos obligatorios rechazan vacío y los mismos 29 caracteres Unicode de
  espacio del backend. La prueba de contrato compara ambas constantes sin cargar
  Django en el escritorio. La validación local no reemplaza la del servidor.

Antes del envío se confirma resultado, OT Completada, activo Disponible/Dado de baja
y ticket Resuelto. Cancelar conserva los datos. El cliente solo envía resultado y
los textos pertinentes a POST /api/ordenes-trabajo/{id}/completar/ con Bearer.

## Operación y errores

SessionDialog y ApiWorker ejecutan la solicitud fuera del hilo gráfico. Mientras
se procesa se deshabilitan cambios y envío, y se impide cerrar voluntariamente
el diálogo para evitar un resultado ambiguo. La finalización/cambio de sesión sí
cierra el diálogo y descarta respuestas tardías por privacidad.

No se reintenta el POST automáticamente. Los errores 400, 401, 403, 404, 405 y 500
tienen mensajes comprensibles sin imprimir payloads, SQL ni detalles internos.
Los errores que mantienen la sesión conservan datos y formulario. Si el cliente
central invalida la sesión por 401, prevalece el cierre por privacidad y se debe
iniciar sesión de nuevo. Ante timeout o respuesta incompleta, consultar el estado
de la OT antes de repetir: un error de comunicación no garantiza que no se guardó.

Solo tras una respuesta exitosa válida se cierra el diálogo y actualiza la fila,
su detalle y la caché con el estado confirmado. Se recarga OT y se emite una señal
para recargar tickets, activos y dashboard conectados en MainWindow.

Gestionar repuestos permanece accesible como consulta de OT Completada; su diálogo
existente oculta consumo y anulación. No se modificó su implementación ni su API.

## Demostración e instalación pendiente

**La tabla cierre_tecnico todavía no está instalada en siget_db.** No probar un cierre
real hasta autorizar la sincronización aditiva revisada de PostgreSQL, verificar
E7-H18 y disponer de respaldo verificable. La UI no detecta ni instala tablas.

Las pruebas del escritorio usan offscreen, workers y HTTP simulados. No utilizan
el backend real, PostgreSQL ni correo. Pendiente una demostración extremo a extremo
autorizada tras instalación, con datos y notificaciones controlados.
