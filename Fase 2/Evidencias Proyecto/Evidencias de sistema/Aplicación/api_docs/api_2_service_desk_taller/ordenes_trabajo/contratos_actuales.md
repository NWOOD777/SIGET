# Contratos actuales de órdenes de trabajo

Referencia base: `e2abc9e`, más las correcciones locales de concurrencia,
integridad, validación tipada y recuperación de fase al reanudar. Describe código existente, no reglas
propuestas. Fuentes: `siget_web/ordenes_trabajo/{urls,views,serializers,permissions,services}.py`.

## Convenciones comunes

- Prefijo: `/api/ordenes-trabajo/`. JSON de entrada y salida.
- Autenticación: Bearer existente para escritorio o sesión Django; las escrituras
  con sesión requieren CSRF. No enviar roles ni el identificador del actor.
- Autorización actual de todas las operaciones: usuario SIGET activo con rol
  **Técnico de soporte**, consultado en el servidor. No se exige explícitamente
  `OT_GESTIONAR` ni ser responsable de la OT. Administrador sin rol técnico: 403.
- Política confirmada para esta entrega: gestión colaborativa. Cualquier técnico
  activo puede pausar, reanudar y reasignar OT ajenas, respetando estados y demás
  validaciones. La ausencia de restricción por responsable es intencional.
  Evaluar `OT_GESTIONAR` como control explícito es una decisión futura sobre
  granularidad de permisos, no un defecto que esta consolidación deba corregir.
- Bearer inválido: 401; acceso denegado y CSRF: 403. El acceso anónimo por sesión
  puede responder 403 por las convenciones de autenticación DRF existentes.
- Validaciones de negocio: 400, normalmente objeto de campos con listas de errores.
  Historial inexistente: 404. Las mutaciones con OT inexistente devuelven 400.
- Validación de entrada: 400 con errores por campo y listas de mensajes. Ante
  varios campos inválidos se pueden informar varios errores en la misma respuesta.
  PySide6 admite ese formato mediante su recolector recursivo de errores.
- Los identificadores aceptan enteros JSON o cadenas ASCII de dígitos, incluidos
  ceros iniciales. Deben estar entre 1 y 2147483647, conforme al AutoField actual;
  el código obtiene el límite del modelo/backend. No acepta booleanos, flotantes,
  negativos, espacios, dígitos Unicode ni valores fuera de rango. La existencia
  y autorización se comprueban por separado, como antes.
- En las rutas existentes, segmentos no admitidos por `<int:pk>` continúan dando
  404. Un segmento numérico convertible pero igual a cero o fuera del rango del
  modelo devuelve ahora 400 con `id_orden`; no se consulta PostgreSQL con ese ID.
  IDs positivos dentro del rango que no existen mantienen 400 en mutaciones y
  404 en historial. Los parámetros de consulta del listado siguen sin usarse.
- Crear/pausar/reasignar exigen un objeto JSON con sus campos. Inicio/reanudación
  admiten ausencia de cuerpo u objeto vacío. Los campos extra continúan ignorados.
  Un cuerpo JSON no objeto (incluido `null`) devuelve 400, también en operaciones
  sin campos. No se confunde con la ausencia de cuerpo. JSON malformado: 400 del parser.
- Ejemplos **ilustrativos**, no datos reales: sustituir `<id_ticket>`, `<id_ot>` y
  `<id_tecnico>` por enteros existentes sin comillas. Los códigos y fechas de la
  respuesta ilustrativa no son constantes. El token se representa por un marcador.
- Cada escritura usa `transaccion_operacion` y auditoría persistente. No envía
  correo HTTP directamente. Reasignar también registra una notificación al nuevo
  responsable; las demás operaciones OT descritas no crean ese aviso.

Solicitud autenticada de ejemplo:

```http
GET /api/ordenes-trabajo/
Authorization: Bearer <token>
Accept: application/json
```

### Representación común de OT

Creación y mutaciones devuelven un objeto; el listado devuelve una lista de estos
objetos, sin envoltorio paginado. `estado` es texto, no el objeto anidado de tickets.
Los campos de diagnóstico corresponden al último diagnóstico por fecha.

```json
{
  "id_orden": 123,
  "codigo_ot": "OT-0123",
  "id_ticket": 456,
  "codigo_ticket": "TCK-0456",
  "id_activo": 789,
  "codigo_inventario": "ACT-EJEMPLO",
  "estado": "En Diagnóstico",
  "falla_reportada": "No inicia",
  "diagnostico": "No inicia",
  "procedimiento_inicial": "Comprobar alimentación",
  "es_reparable": true,
  "fecha_inicio": "2026-10-25T12:00:00Z",
  "fecha_termino": null,
  "justificacion_pausa": null,
  "id_tecnico_responsable": 321,
  "tecnico_responsable": "Nombre Apellido"
}
```

Los campos de activo, responsable y diagnóstico pueden ser `null` cuando la
relación o diagnóstico no esté disponible; `fecha_termino` y justificación pueden
ser `null`. Las fechas son determinadas por el servidor.

## Listar OT

**GET `/api/ordenes-trabajo/`**. Sin cuerpo. Autorización común.

- 200: lista de representaciones comunes; `[]` si no existen OT.
- Orden: `fecha_inicio` descendente. No hay filtros ni paginación implementados
  en esta vista. No se limita a las OT del técnico autenticado.
- No restringe por estado del ticket, activo u OT; no modifica datos.
- Errores de autenticación/autorización comunes.

## Crear OT

**POST `/api/ordenes-trabajo/`** → `crear_orden_trabajo`.

```json
{
  "id_ticket": <id_ticket>,
  "descripcion_falla": "No inicia",
  "procedimiento_inicial": "Comprobar alimentación",
  "es_reparable": true
}
```

- Obligatorios: `id_ticket`, `descripcion_falla`, `procedimiento_inicial`.
  Los textos deben ser cadenas JSON y no pueden quedar vacíos tras recortar espacios;
  `null`, números, booleanos, listas y objetos se rechazan, sin coerción a texto.
- `es_reparable`: booleano JSON opcional; predeterminado `true`.
- Ticket existente, no Resuelto ni Cerrado, con activo **En revisión**.
- No puede existir otra OT del mismo ticket, incluso si está Completada.
- No puede existir otra OT vigente del activo, aunque corresponda a otro ticket.
  Vigentes: En Diagnóstico, En Reparación y Pausada. Una OT Completada de otro
  ticket no bloquea esta comprobación; las demás precondiciones siguen aplicando.
- 201: representación común, `estado: "En Diagnóstico"`; crea diagnóstico y
  auditoría `OT_CREADA`. El responsable es el técnico autenticado.
- Mantiene el activo En revisión; no cambia estado ni responsable del ticket.
- 400: campos inválidos (incluidos tipos y límites), ticket inexistente, terminal, sin activo, activo fuera
  de En revisión, OT duplicada del ticket o catálogos necesarios ausentes.
- Ejemplo de error: `{"id_ticket":["El ticket indicado no existe."]}`.
- La comprobación por activo ocurre después de bloquear su fila, dentro de la
  transacción. El rechazo devuelve 400:
  `{"id_activo":["El activo ya tiene una orden de trabajo vigente."]}`.
  La validación tipada se realiza antes de invocar el servicio.

## Consultar técnicos disponibles

**GET `/api/ordenes-trabajo/tecnicos-disponibles/`**. Sin cuerpo.

```http
GET /api/ordenes-trabajo/tecnicos-disponibles/
Authorization: Bearer <token>
```

200, lista ordenada por nombres/apellidos, sin usuarios repetidos:

```json
[{"id_usuario":321,"nombre":"Nombre Apellido","correo":"tecnico@example.invalid"}]
```

Solo usuarios activos con rol técnico. No comprueba disponibilidad horaria,
carga de trabajo ni `OT_GESTIONAR`. `[]` si no hay resultados. Sin restricciones
por estado de tickets/activos. Errores comunes de acceso.

## Consultar historial

**GET `/api/ordenes-trabajo/{id}/historial/`**. Sin cuerpo.

```http
GET /api/ordenes-trabajo/<id_ot>/historial/
Authorization: Bearer <token>
```

200: auditorías de módulo `ORDENES_TRABAJO`, entidad `orden_trabajo`, de esa OT,
ordenadas por fecha descendente. Puede devolver `[]`. No filtra por estado.

```json
[{
  "id_auditoria":987,
  "fecha":"2026-10-25T12:00:00Z",
  "accion":"OT_CREADA",
  "usuario":"Nombre Apellido",
  "detalles":"Detalle registrado por el servicio"
}]
```

404: `{"detail":"La orden de trabajo no existe."}`. No cambia ticket ni activo.
Errores comunes de acceso. No existe desempate explícito para fechas iguales.

## Iniciar reparación

**POST `/api/ordenes-trabajo/{id}/iniciar-reparacion/`** → `iniciar_reparacion`.

```http
POST /api/ordenes-trabajo/<id_ot>/iniciar-reparacion/
Content-Type: application/json
Authorization: Bearer <token>

{}
```

- Sin campos de entrada consumidos; acepta sin cuerpo u objeto JSON. Actor determinado por el servidor.
- Exige OT En Diagnóstico, último diagnóstico existente y reparable, ticket con
  activo En revisión y catálogos de destino disponibles.
- 200: representación común con `estado: "En Reparación"`.
- Actualiza el activo a **En reparación**, registra historial del activo y
  auditoría `REPARACION_INICIADA`. No cambia estado ni responsable del ticket.
- 400: OT inexistente (`id_orden`), precondiciones incumplidas o catálogo ausente.
  Ejemplo: `{"id_orden":["La orden de trabajo no existe."]}`.
- Bloquea primero la fila OT y lee su estado después de adquirir el bloqueo;
  después bloquea el activo. Si una pausa confirmó antes, rechaza el inicio con
  400 en lugar de sobrescribirla. Si inicio confirma primero, una pausa posterior
  puede confirmar sobre En Reparación conforme a las reglas existentes.

## Pausar OT

**POST `/api/ordenes-trabajo/{id}/pausar/`** → `pausar_orden_trabajo`.

```json
{"justificacion":"Esperando repuesto"}
```

- Justificación obligatoria de tipo cadena, no nula, no vacía ni solo espacios.
- Estados de origen: **En Diagnóstico** o **En Reparación**.
- 200: representación común con `estado: "Pausada"` y justificación recortada.
- Registra `OT_PAUSADA`. Conserva estados del activo y ticket y sus responsables.
- Conserva la fase de origen en el mismo evento de auditoría, con el texto legible
  anterior y una última línea `SIGET_OT_FASE_V1:` seguida de JSON generado por el
  servidor. Incluye versión, ID de OT, acción, estado anterior/nuevo y motivo.
  Los saltos del motivo se escapan dentro del JSON. No requiere nuevos campos.
- 400: justificación inválida, OT inexistente, estado no permitido o catálogo ausente.
- Ejemplo: `{"justificacion":["Debe indicar el motivo de la pausa."]}`.
- Errores comunes de acceso; no se valida propiedad de la OT.

## Reasignar OT

**POST `/api/ordenes-trabajo/{id}/reasignar/`** → `reasignar_orden_trabajo`.

```json
{"id_tecnico_responsable":<id_tecnico>,"observaciones":"Cambio de turno"}
```

- Ambos campos obligatorios. ID sujeto al rango/tipos indicados arriba;
  observaciones de tipo cadena, no nulas ni vacías tras recortar espacios.
- Destino: usuario activo con rol Técnico de soporte. No exige explícitamente
  `OT_GESTIONAR`. Rechaza OT Completada; admite los otros estados existentes.
- 200: representación común con nuevo `id_tecnico_responsable` y nombre.
- Conserva estado de OT, activo y ticket; no reasigna al responsable del ticket.
- Registra auditoría `OT_REASIGNADA` y notificación persistente al nuevo técnico,
  usando el ID de auditoría en la identidad del evento. Envío de correo posterior,
  mediante la infraestructura existente.
- No existe rechazo explícito de reasignación al mismo técnico.
- 400: identificador inválido, destino inexistente/inactivo/sin rol técnico,
  observaciones vacías, OT inexistente o Completada.
- Ejemplo: `{"id_tecnico_responsable":["El técnico no existe o está inactivo."]}`.
- Errores comunes de acceso. El actor no tiene que ser el responsable actual.

## Reanudar OT

**POST `/api/ordenes-trabajo/{id}/reanudar/`** → `reanudar_orden_trabajo`.

```http
POST /api/ordenes-trabajo/<id_ot>/reanudar/
Content-Type: application/json
Authorization: Bearer <token>

{}
```

- Sin campos consumidos; acepta sin cuerpo u objeto JSON. Exige OT **Pausada**.
- 200: representación común con la fase anterior restaurada y
  `justificacion_pausa: null`; registra `OT_REANUDADA` con origen/destino explícitos.
  En Diagnóstico → Pausada → En Diagnóstico;
  En Reparación → Pausada → En Reparación. Nunca inicia reparación implícitamente.
- Bloquea OT → activo y exige activo En revisión para restaurar diagnóstico, o
  En reparación para restaurar reparación. No modifica el activo para ocultar
  inconsistencias; ticket y responsables permanecen iguales.
- Recupera la fase del registro estructurado de la última pausa: valida versión,
  ID de OT, acción, origen permitido, destino Pausada y motivo igual al persistido.
  No usa un estado por defecto ni interpreta frases libres. Un registro inválido
  no se degrada a reconstrucción histórica.
- Legado sin registro explícito: solo admite la secuencia completa del primer ciclo
  `OT_CREADA → OT_PAUSADA` (diagnóstico) o
  `OT_CREADA → REPARACION_INICIADA → OT_PAUSADA` (reparación), ignorando únicamente
  `OT_REASIGNADA`, que no cambia fase. Se ordena por `id_auditoria`: los escritores
  de la misma OT están serializados por su bloqueo y no dependen de empates de fecha.
  Reanudaciones antiguas, acciones desconocidas o historia insuficiente se rechazan.
  No se modifican ni migran datos históricos.
- 400: OT inexistente, no Pausada, catálogo ausente, fase no recuperable o activo
  incompatible. Errores comunes de acceso.
- Ejemplo: `{"estado":["Solo se puede reanudar una orden pausada."]}`.
- Auditoría insuficiente/inválida:
  `{"estado":["No se puede recuperar con certeza la fase anterior de la OT. Revise su auditoría."]}`.
- Activo incompatible, por ejemplo:
  `{"id_activo":["El activo debe estar en 'En revisión' para reanudar esta fase."]}`.
- Todo se confirma en una transacción: los errores conservan pausa, justificación,
  activo y auditoría sin efectos parciales. El cálculo de pausas conserva los nombres
  `OT_PAUSADA`/`OT_REANUDADA`; el formato del historial sigue siendo texto.
- PySide6 mantiene la misma solicitud y representación de salida. Al refrescar,
  una OT devuelta a diagnóstico ofrece la operación Iniciar reparación existente.

## Integración y límites

- Tickets: Abierto → En Proceso; En Proceso → En Espera/Resuelto;
  En Espera → En Proceso; Resuelto → Cerrado. Sin reapertura.
- En Diagnóstico, En Reparación y Pausada son OT vigentes: impiden resolver/cerrar
  el ticket mediante `cambiar_estado_ticket`. Completada no lo impide.
- Crear OT bloquea el ticket y rechaza Resuelto/Cerrado. La resolución también
  bloquea el ticket. Esta exclusión no equivale a sincronizar responsables.
- Las consultas de bloqueo usan `FOR UPDATE OF` sobre OT o activo según corresponda,
  sin bloquear sus catálogos. Las relaciones de OT se leen después del bloqueo.
  Pausa y reasignación bloquean la OT; iniciar y reanudar bloquean OT → activo.
  Crear conserva bloqueo global de numeración → ticket → activo → nueva OT.
  La validación por activo no añade un bloqueo global; el existente de numeración
  continúa serializando las creaciones, incluso para activos distintos.
- No existe endpoint de cierre técnico E6-H17 en estas rutas. Tampoco GET de
  detalle individual, catálogo de estados OT ni consulta del cálculo de SLA efectivo.
- Identificadores se consultan en la base; no se documentan números fijos de estados.
- La validación tipada de los campos consumidos impide las excepciones internas
  reproducidas por textos no textuales y dígitos Unicode no convertibles. No cambia
  la serialización de salida. La reanudación aplica la alternativa A aprobada por
  el equipo; no crea el estado «En Proceso» mencionado ambiguamente en E6-H24.
  La gestión colaborativa está confirmada. La granularidad futura de OT_GESTIONAR
  y la eventual unificación de inexistencia 400/404 quedan fuera de esta entrega.
