# E6-H17 — Servicio interno de cierre técnico

`ordenes_trabajo.cierre.cerrar_orden_trabajo` recibe argumentos nombrados:
id_orden, tecnico (actor autenticado proporcionado por el llamador), resultado,
solucion_aplicada, pruebas_realizadas, informe_descarte e ip_origen opcional.
Devuelve CierreTecnico. No existe endpoint ni modificación del cliente PySide6.

## Autorización y estados

Recarga al actor desde PostgreSQL: activo, Técnico de soporte, OT_GESTIONAR y
TICKET_ATENDER. La gestión es colaborativa; no cambia responsables de OT ni ticket.
El futuro endpoint deberá obtener el actor de autenticación, nunca del JSON.

- REPARACION_EXITOSA: OT En Reparación → Completada; activo → Disponible.
- NO_REPARABLE: OT En Diagnóstico o En Reparación → Completada; activo → Dado de baja.
- Ticket Abierto, En Proceso o En Espera → Resuelto, sin cierre automático.
- Se rechazan OT Pausada/Completada, cierre previo y ticket Resuelto/Cerrado.
- El activo debe estar En revisión durante diagnóstico o En reparación durante
  reparación. Se rechazan asignaciones sin finalizar y otras OT vigentes del activo.
  No se corrigen inconsistencias ni se modifican diagnósticos o stock.

## Atomicidad y bloqueos

Transacción única: lectura inicial de referencia → fila ticket → fila OT → bloqueo
asesor 70403 del activo → fila activo. Las relaciones y estados se revalidan bajo
bloqueo. No adquiere 70621: E7-H18 lo toma antes de bloquear OT; invertir ese orden
introduciría una dependencia incompatible. Ambos flujos se coordinan por la fila OT.

Se guardan cierre, fecha de término, estado activo, historial, auditorías,
resolución del ticket, comentario y notificaciones. Un fallo de persistencia
revierte todo. UNIQUE por OT complementa el bloqueo de fila contra dobles cierres.
La excepción de resolución vive en una función privada de este módulo, sin flags
de omisión de reglas ni cambios en el contrato público de E5-H14.

## Notificaciones

El solicitante recibe el evento de resolución identificado por la auditoría real.
Por descarte se registra un correo por administrador activo con email válido,
con clave única por cierre y destinatario. La ausencia de destinatarios válidos
produce auditoría CIERRE_SIN_DESTINATARIOS y advertencia posterior al commit;
no bloquea el cierre. Un fallo al persistir esa auditoría sí revierte la operación.

Se reutilizan la cola persistente y on_commit robusto existentes. No se llama a
Resend dentro del servicio. Un fallo posterior de señal/despacho no revierte el
cierre; el aviso pendiente permite recuperación por el consumidor habitual.

## Instalación y pruebas

La tabla sigue sin instalarse en desarrollo. El SQL aditivo no fue ejecutado.
El runner instala el esquema de referencia únicamente en test_siget_db para las
pruebas. Se completó su lista de recreación con cierre_tecnico, necesaria porque
las fixtures recargan el DDL entre pruebas. No se ejecuta ese esquema en desarrollo.

Las pruebas incluyen persistencia, autorización, rollback, deduplicación y carreras
con conexiones independientes y límites de espera. Las llamadas HTTP/SMTP se
bloquean durante ejecución. No se comprueba entregabilidad real de correo.

Las etapas posteriores incorporaron el endpoint, sus pruebas de autenticación/CSRF
y la equivalencia Unicode en PostgreSQL. Pendientes: instalación aditiva autorizada,
interfaz y regresión general.
