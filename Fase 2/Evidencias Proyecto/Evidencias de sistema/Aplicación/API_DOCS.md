# API de SIGET

Sistema Integral de Gestión de Equipos y Soporte Tecnológico  
Actualización: 16 de octubre de 2026

Esta guía reúne los endpoints disponibles para acceso, usuarios y permisos, activos TI, solicitudes de asignación, entregas, devoluciones y tickets de soporte.

## Uso general

La dirección local es `http://localhost:8000`. Las rutas conservan la barra final `/`. Las peticiones a `/api/` reciben y devuelven datos en formato JSON; se recomienda indicar `Accept: application/json` y, al enviar datos, `Content-Type: application/json`.

Para utilizar la API se debe iniciar sesión con Auth0 y contar con una cuenta SIGET activa. Los permisos corresponden a los roles asignados en el sistema:

- **Usuario solicitante:** solicita equipos y registra tickets; consulta sus propias solicitudes, asignaciones y tickets.
- **Técnico de soporte:** consulta información operativa y registra entregas, devoluciones y la evaluación inicial del equipo.
- **Administrador del sistema:** administra usuarios, roles, permisos y activos; aprueba o rechaza solicitudes y consulta la información de gestión.

En las tablas se utilizan los nombres abreviados **Solicitante**, **Técnico** y **Administrador**. Una cuenta puede tener más de un rol. El rol Administrador por sí solo no permite entregar ni recibir equipos.

Las peticiones que registran, modifican o retiran información requieren la cookie de sesión y el encabezado `X-CSRFToken`, con el valor vigente de la cookie `csrftoken`. Esta cookie se obtiene al visitar `/` y debe leerse nuevamente después del inicio de sesión. En Postman u otro cliente se deben conservar las cookies de la sesión.

Los valores entre llaves, como `{id}`, se reemplazan por el identificador del registro. Los identificadores de los ejemplos son ilustrativos: deben consultarse los registros y catálogos del entorno utilizado. Las fechas simples usan `AAAA-MM-DD`; las fechas con hora usan el formato ISO 8601, por ejemplo `2026-10-20T15:00:00Z`.

Las consultas de listado responden con una lista. Si no hay coincidencias, devuelven `[]` y código `200`. Actualmente los listados no tienen paginación. Las rutas de API admiten `OPTIONS` para consultar sus métodos disponibles; las rutas con consulta `GET` también admiten `HEAD`.

## Acceso y sesión

Estas rutas se utilizan desde el navegador y devuelven páginas o redirecciones.

| Método | Ruta | Función y respuesta |
| --- | --- | --- |
| GET | `/` | Muestra el acceso o el portal del Solicitante (`200`). Una sesión sin acceso al portal recibe `403`. |
| GET | `/auth/login/` | Redirige a Auth0 para iniciar sesión (`302`). Si el servicio no está disponible, responde `502`. |
| GET | `/auth/callback/` | Recibe la respuesta de Auth0 y, si el acceso es válido, redirige al inicio (`302`). Puede responder `400` por una respuesta inválida o `403` por acceso rechazado, cuenta inactiva o correo no verificado. |
| GET | `/auth/logout/` | Cierra la sesión de SIGET y redirige al cierre de sesión de Auth0 (`302`). |
| GET | `/auth/recover/` | Presenta el formulario de recuperación de acceso (`200`). |
| POST | `/auth/recover/` | Recibe el campo de formulario `correo` y muestra la confirmación o los errores (`200`). Requiere protección CSRF. |

La recuperación solicita a Auth0 el envío de instrucciones. El mensaje de confirmación no revela si el correo está registrado. El callback se completa como parte del inicio de sesión; sus parámetros `code` y `state` son enviados por el proveedor.

La ruta `/admin/` corresponde al panel técnico de Django y requiere una cuenta administrativa de Django. Las operaciones de administración de SIGET se exponen mediante los endpoints siguientes.

## Usuarios, roles y permisos

Todas estas operaciones requieren el rol **Administrador**.

| Método | Ruta | Operación | Respuesta correcta |
| --- | --- | --- | --- |
| GET | `/api/usuarios/` | Consultar los usuarios registrados y sus roles. | `200`, lista de usuarios. |
| POST | `/api/usuarios/aprovisionar/` | Crear una cuenta vinculada con Auth0 y asignar su rol inicial. | `201`, ficha de acceso del usuario creado. |
| GET | `/api/usuarios/{id}/acceso/` | Consultar la identidad, roles y permisos efectivos de un usuario. | `200`, ficha de acceso. |
| POST | `/api/usuarios/{id}/roles/` | Actualizar la colección completa de roles del usuario. | `200`, ficha de acceso actualizada. |
| DELETE | `/api/usuarios/{id}/roles/{id_rol}/` | Retirar un rol del usuario. | `200`, mensaje de confirmación. |
| GET | `/api/usuarios/roles/` | Consultar los roles oficiales y sus permisos. | `200`, lista de roles con permisos. |
| POST | `/api/usuarios/roles/{id_rol}/permisos/` | Asociar un permiso existente a un rol. | `201`, mensaje de confirmación. |
| DELETE | `/api/usuarios/roles/{id_rol}/permisos/{id_permiso}/` | Retirar un permiso de un rol. | `200`, mensaje de confirmación. |

### Crear un usuario

`POST /api/usuarios/aprovisionar/`

```json
{
  "nombres": "Camila",
  "apellidos": "Rojas",
  "correo": "camila.rojas@example.com",
  "rut": "12.345.678-5",
  "rol": "Usuario solicitante"
}
```

Todos los campos son obligatorios. El rol debe ser `Usuario solicitante`, `Técnico de soporte` o `Administrador del sistema`. Se validan el correo, el RUT y los duplicados antes de completar el registro. Al crear la cuenta se solicita a Auth0 el envío de instrucciones para configurar la contraseña inicial.

La respuesta incluye `id_usuario`, `identificador_externo`, `proveedor_identidad`, `rut`, `nombres`, `apellidos`, `correo`, `activo`, `fecha_creacion`, `roles` y `permisos_efectivos`. Cada rol contiene su identificador, nombre y descripción; cada permiso, su identificador, código y descripción.

Un usuario duplicado produce `409`; los datos inválidos, `400`; un fallo de comunicación con Auth0, `502`; y un error de persistencia, `500`.

### Modificar accesos

`POST /api/usuarios/{id}/roles/` recibe la selección completa que debe conservar el usuario:

```json
{"roles": ["Técnico de soporte", "Usuario solicitante"]}
```

Se admiten nombres o identificadores de roles existentes. Debe quedar al menos un rol asignado. El retiro mediante `DELETE` tampoco permite eliminar el único rol de una cuenta.

`POST /api/usuarios/roles/{id_rol}/permisos/` recibe el identificador o el código de un permiso existente:

```json
{"codigo": "CATALOGO_CONSULTAR"}
```

También se admite `{"id_permiso": 1}`. Retirar un rol o un permiso elimina su asociación; el catálogo sigue disponible. Si la asociación indicada no existe, la respuesta es `404`.

El listado de usuarios devuelve los datos de identificación y una lista de nombres de roles. La consulta `/acceso/` agrega el detalle de roles y permisos efectivos. El listado `/roles/` incluye `id_rol`, `nombre`, `descripcion` y `permisos` para cada rol.

## Activos TI

Las consultas están disponibles para el Administrador, el Técnico y las cuentas con el permiso `CATALOGO_CONSULTAR`. Los tres roles oficiales cuentan inicialmente con ese permiso. El registro y la modificación requieren el rol **Administrador**.

| Método | Ruta | Operación | Respuesta correcta |
| --- | --- | --- | --- |
| GET | `/api/activos/` | Consultar activos y aplicar filtros. | `200`, lista de activos. |
| POST | `/api/activos/` | Registrar un activo TI. | `201`, activo registrado. |
| GET | `/api/activos/{id}/` | Consultar un activo. | `200`, detalle del activo. |
| PUT | `/api/activos/{id}/` | Actualizar los datos del activo, enviando los campos obligatorios. | `200`, activo actualizado. |
| PATCH | `/api/activos/{id}/` | Modificar únicamente los campos enviados. | `200`, activo actualizado. |
| GET | `/api/activos/categorias/` | Consultar tipos o categorías de equipos. | `200`, lista de categorías. |
| GET | `/api/activos/marcas/` | Consultar marcas. | `200`, lista de marcas. |
| GET | `/api/activos/modelos/` | Consultar modelos, con marca y categoría. | `200`, lista de modelos. |
| GET | `/api/activos/ubicaciones/` | Consultar áreas, edificios y pisos. | `200`, lista de ubicaciones. |
| GET | `/api/activos/estados/` | Consultar estados de los activos. | `200`, lista de estados. |

### Registro y modificación

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

El identificador, el código de inventario y la fecha de registro son asignados por el sistema. La respuesta incluye esos datos, los campos del activo y los nombres de `modelo`, `marca`, `categoria`, `ubicacion` y `estado`.

Ejemplo de modificación: `PATCH /api/activos/{id}/` con `{"id_ubicacion": 2}`. Para `PUT` deben enviarse al menos `numero_serie`, `id_modelo` e `id_ubicacion`.

Un activo con asignación abierta no permite cambiar su modelo ni su estado. El estado `Asignado` se establece al registrar una entrega. Los datos inválidos o una serie repetida se informan con `400`; un activo inexistente, con `404`.

### Búsqueda y catálogos

`GET /api/activos/` admite los siguientes filtros, combinables entre sí:

| Parámetro | Búsqueda |
| --- | --- |
| `search` | Identificador, código de inventario, serie, modelo o marca. |
| `tipo` | Nombre de la categoría, por ejemplo `Notebook`. |
| `ubicacion` | Identificador o nombre del área. |
| `estado` | Nombre del estado, por ejemplo `Disponible`. |

Ejemplo: `/api/activos/?tipo=Notebook&estado=Disponible`.

Los catálogos entregan identificadores y nombres para completar los registros. Categorías y estados incluyen descripción; modelos incluyen `id_marca`, `id_categoria`, `marca` y `categoria`; ubicaciones incluyen `nombre_area`, `edificio` y `piso`.

## Solicitudes de asignación

El Solicitante consulta sus propias solicitudes. El Administrador y el Técnico pueden consultar el listado general. La aprobación y el rechazo corresponden al **Administrador**; la entrega física, al **Técnico**.

| Método | Ruta | Operación y acceso | Respuesta correcta |
| --- | --- | --- | --- |
| GET | `/api/solicitudes-asignacion/` | Consultar solicitudes dentro del alcance del usuario. | `200`, lista de solicitudes. |
| POST | `/api/solicitudes-asignacion/` | Registrar una solicitud; Solicitante. | `201`, solicitud creada. |
| GET | `/api/solicitudes-asignacion/{id}/` | Consultar una solicitud propia o, con rol interno, cualquier solicitud. | `200`, detalle de la solicitud. |
| POST | `/api/solicitudes-asignacion/{id}/aprobar/` | Aprobar una solicitud pendiente; Administrador. | `200`, solicitud actualizada. |
| POST | `/api/solicitudes-asignacion/{id}/rechazar/` | Rechazar una solicitud pendiente; Administrador. | `200`, solicitud actualizada. |
| POST | `/api/solicitudes-asignacion/{id}/entregar/` | Registrar la entrega para una solicitud aprobada; Técnico. | `201`, asignación creada. |
| GET | `/api/solicitudes-asignacion/estados/` | Consultar estados de solicitud; usuario autenticado. | `200`, lista de estados. |

### Crear y resolver solicitudes

`POST /api/solicitudes-asignacion/`

```json
{"id_categoria": 1, "motivo": "Equipo requerido para actividades de trabajo"}
```

Ambos campos son obligatorios. Debe existir una categoría con equipos disponibles. Se impide otra solicitud Pendiente o Aprobada de la misma categoría para el mismo usuario. El estado inicial es `Pendiente`.

La solicitud devuelta contiene `id_solicitud`, `id_usuario`, `solicitante`, `id_categoria`, `categoria`, `id_estado_solicitud`, `estado`, `id_administrador_resolutor`, `resolutor`, `fecha_solicitud`, `fecha_resolucion`, `motivo` y `motivo_rechazo`. Antes de su resolución, los datos del resolutor y la fecha de resolución son `null`.

Para aprobar se envía `{}` a `POST /api/solicitudes-asignacion/{id}/aprobar/`. El sistema comprueba que siga pendiente y exista disponibilidad. La aprobación no selecciona ni reserva todavía un equipo físico.

Para rechazar se envía a `POST /api/solicitudes-asignacion/{id}/rechazar/`:

```json
{"motivo_rechazo": "No corresponde a la necesidad informada"}
```

El motivo es obligatorio. Las solicitudes ya resueltas no pueden aprobarse o rechazarse nuevamente. Las validaciones responden `400` y una solicitud inexistente, `404`.

### Filtros de consulta

`GET /api/solicitudes-asignacion/` admite `estado` y `categoria` por identificador o nombre; `search` busca en motivo, categoría o identificador de solicitud. El Administrador y el Técnico también pueden filtrar por `usuario`, usando identificador, correo, RUT, nombres o apellidos. El alcance del Solicitante siempre se limita a sus registros. Para revisar las solicitudes pendientes se utiliza `/api/solicitudes-asignacion/?estado=Pendiente`.

## Entregas, asignaciones y devoluciones

| Método | Ruta | Operación y acceso | Respuesta correcta |
| --- | --- | --- | --- |
| GET | `/api/asignaciones/` | Consultar asignaciones propias; Administrador y Técnico consultan el listado general. | `200`, lista de asignaciones. |
| POST | `/api/asignaciones/` | Registrar entrega indicando solicitud y activo; Técnico. | `201`, asignación creada. |
| GET | `/api/asignaciones/{id}/` | Consultar una asignación propia o, con rol interno, cualquier asignación. | `200`, detalle de la asignación. |
| POST | `/api/asignaciones/{id}/devolucion/` | Registrar devolución y evaluación inicial del equipo; Técnico. | `201`, devolución registrada. |
| GET | `/api/asignaciones/estados/` | Consultar estados de asignación; usuario autenticado. | `200`, lista de estados. |

### Registrar entrega

`POST /api/solicitudes-asignacion/{id}/entregar/`

```json
{"id_activo": 1, "fecha_devolucion_prevista": "2026-10-30T18:00:00Z"}
```

`id_activo` es obligatorio; `fecha_devolucion_prevista` es opcional y admite `null`. Si se informa una fecha, debe ser igual o posterior al momento de la entrega.

También se puede registrar mediante `POST /api/asignaciones/`, incluyendo la solicitud:

```json
{"id_solicitud": 1, "id_activo": 1}
```

La solicitud debe estar Aprobada y sin entrega anterior. El activo debe estar Disponible y corresponder a la categoría solicitada. Al completar la operación, la asignación queda `Activa`, el activo `Asignado` y la solicitud `Atendida`.

La respuesta contiene `id_asignacion`, `id_solicitud`, `solicitud`, `id_activo`, `activo`, `id_tecnico_entrega`, `tecnico_entrega`, `id_estado_asignacion`, `estado`, `fecha_entrega`, `fecha_devolucion_prevista` y `fecha_finalizacion`. Los objetos relacionados muestran los datos del solicitante, equipo y técnico. La fecha de finalización permanece `null` mientras la asignación está abierta.

### Consultar asignaciones

`GET /api/asignaciones/` admite `usuario`, `equipo`, `estado` y `search`. `activo` se admite como alternativa a `equipo`.

- `usuario`: identificador, correo, RUT, nombres o apellidos; disponible para Administrador y Técnico.
- `equipo`: identificador, código de inventario, serie o modelo.
- `estado`: identificador o nombre del estado de asignación.
- `search`: identificador de asignación, datos del equipo o del solicitante.

### Registrar devolución y evaluación

`POST /api/asignaciones/{id}/devolucion/`

```json
{
  "condicion_fisica": "Con falla técnica",
  "motivo_devolucion": "Falla durante el uso",
  "observaciones": "El equipo no enciende"
}
```

| Campo | Condición |
| --- | --- |
| `condicion_fisica` | Obligatorio: `Buen estado`, `Con falla técnica` o `Con daño físico`. |
| `motivo_devolucion` | Opcional; máximo 100 caracteres. |
| `observaciones` | Opcional; descripción de la condición recibida. |
| `id_ticket_asociado` | Opcional; ticket activo del mismo equipo y solicitante, cuando existe falla o daño. |

La recepción y la evaluación inicial se completan en la misma operación. Una devolución ya registrada no admite una segunda evaluación mediante esta ruta. La devolución cierra la asignación y registra el resultado:

| Condición recibida | Estado del activo | Soporte |
| --- | --- | --- |
| Buen estado | Disponible | Queda habilitado para otra asignación. |
| Con falla técnica | En revisión | Se genera o asocia un ticket. |
| Con daño físico | En revisión | Se genera o asocia un ticket y se conservan las observaciones. |

Si ya existe un ticket activo del mismo equipo y solicitante, se reutiliza. Un ticket cerrado, resuelto o ajeno se rechaza. En una devolución en buen estado no corresponde enviar `id_ticket_asociado`.

La respuesta incluye `id_devolucion`, `id_asignacion`, `id_tecnico_receptor`, `tecnico_receptor`, `id_estado_activo_resultante`, `estado_activo_resultante`, `fecha_devolucion`, `condicion_fisica`, `motivo_devolucion` y `observaciones`. Se registra el historial del estado y la auditoría de la operación.

Una asignación inexistente responde `404`. Una asignación finalizada, una devolución duplicada o una condición inválida responde `400`.

## Tickets de soporte

Los tres roles oficiales pueden registrar tickets a su nombre. El Solicitante consulta sus propios tickets; el Administrador y el Técnico pueden consultar el listado general. Los catálogos requieren sesión activa.

| Método | Ruta | Operación | Respuesta correcta |
| --- | --- | --- | --- |
| GET | `/api/tickets/` | Consultar tickets dentro del alcance del usuario. | `200`, lista de tickets. |
| POST | `/api/tickets/` | Registrar un ticket inicial. | `201`, ticket creado. |
| GET | `/api/tickets/{id}/` | Consultar un ticket autorizado. | `200`, detalle del ticket. |
| GET | `/api/tickets/prioridades/` | Consultar prioridades y nivel de urgencia. | `200`, lista de prioridades. |
| GET | `/api/tickets/estados/` | Consultar estados de ticket. | `200`, lista de estados. |
| GET | `/api/tickets/sla/` | Consultar tiempos de respuesta y resolución por prioridad. | `200`, lista de políticas de servicio. |

### Crear un ticket

`POST /api/tickets/`

```json
{
  "asunto": "El equipo no enciende",
  "descripcion": "Al presionar el botón de encendido no hay respuesta",
  "id_activo": 1,
  "id_prioridad": 2
}
```

`asunto` es obligatorio y admite hasta 200 caracteres. `descripcion` es obligatoria. `id_activo` e `id_prioridad` son opcionales y admiten `null`; si se informan, deben corresponder a registros existentes. La prioridad predeterminada es `Medio` en el catálogo inicial.

Si se informa `id_activo`, el Usuario solicitante solo puede asociar un activo que tenga mediante una asignación en estado `Activa` y con `fecha_finalizacion` en `null`. El permiso `TICKET_CREAR` permite crear tickets, pero no concede acceso global a los activos: sin rol interno se aplica la misma restricción. El Administrador del sistema y el Técnico de soporte mantienen su alcance por rol y pueden asociar cualquier activo existente, sin exigir una asignación propia activa.

Para un usuario sin rol interno, un activo no autorizado devuelve HTTP `403` con el mensaje genérico `No tiene autorización para reportar ese activo.`, sin crear el ticket ni registrar auditoría de creación. Omitir `id_activo` o enviarlo como `null` permite registrar un ticket sin equipo específico.

En las creaciones manuales con activo, tanto por API como por el portal, la autorización aplicable se verifica nuevamente dentro de una transacción, después de adquirir el bloqueo existente del activo (`70403`) y antes del bloqueo de tickets. La creación permanece dentro de esa misma transacción para coordinarse con las devoluciones concurrentes que utilizan este mecanismo. En la API, los roles internos conservan el alcance descrito anteriormente.

La creación automática de tickets durante una devolución mantiene su comportamiento independiente mediante el servicio existente: puede asociar el activo aunque la asignación ya esté `Finalizada`. La restricción de asignación activa para la creación manual no se aplica a ese flujo automático.

El ticket se crea `Abierto`, con código asignado por el sistema y sin técnico asignado. Se impide un ticket activo con el mismo asunto, activo y solicitante. El registro de un ticket por sí solo no cambia el estado del equipo.

La respuesta contiene `id_ticket`, `codigo_ticket`, `id_usuario_solicitante`, `solicitante`, `id_tecnico_asignado`, `tecnico_asignado`, `id_activo`, `activo`, `id_estado_ticket`, `estado`, `id_prioridad`, `prioridad`, `asunto`, `descripcion`, `fecha_creacion` y `fecha_resolucion`. Los datos de técnico y resolución son inicialmente `null`; los del activo también pueden ser `null` si el ticket no está asociado a un equipo.

### Consultar tickets y tiempos de atención

`GET /api/tickets/` admite `search` para código, asunto o descripción; `estado` y `prioridad` por identificador o nombre; y `activo` por identificador, código o serie. Para Administrador y Técnico, `usuario` permite filtrar por identificador, correo, RUT, nombres o apellidos del solicitante.

`GET /api/tickets/sla/` devuelve `id_sla`, `id_prioridad`, `prioridad`, `tiempo_respuesta_horas`, `tiempo_resolucion_horas` y `descripcion`. Los tiempos están expresados en horas. Las prioridades incluyen su `nivel_urgencia` y descripción; los estados incluyen identificador, nombre y descripción.

## Respuestas y errores

| Código | Significado |
| --- | --- |
| `200` | Consulta, actualización o retiro de una asociación completado. |
| `201` | Registro creado o permiso asociado a un rol. |
| `400` | Datos incompletos o inválidos, duplicado de negocio o transición de estado no permitida. |
| `403` | Sesión ausente o inactiva, falta de autorización, acceso a un registro ajeno o protección CSRF rechazada. |
| `404` | Registro o asociación no encontrado. |
| `405` | Método no admitido en esa ruta. |
| `409` | Usuario duplicado en aprovisionamiento o conflicto con una restricción de integridad. |
| `500` | Fallo interno que impidió completar la operación. |
| `502` | Error del servicio externo de autenticación o aprovisionamiento. |

Los errores de campo identifican el dato que debe corregirse:

```json
{"motivo": ["Este campo es requerido."]}
```

Los errores generales de la API usan `detail`, por ejemplo:

```json
{"detail": "Asignación no encontrada."}
```

En la administración de usuarios y permisos, los errores de negocio usan `error` y las confirmaciones de retiro o asociación usan `mensaje`. Por ejemplo:

```json
{"mensaje": "Rol retirado exitosamente."}
```

Las respuestas de acceso y recuperación son páginas HTML y redirecciones, según la sección de acceso y sesión.

## Alcance frente a la arquitectura preliminar

Las rutas de activos, solicitudes, aprobación, rechazo, entrega, devolución y creación y consulta de tickets conservan las rutas del Anexo B del [Documento de Diseño y Arquitectura Preliminar SIGET](../../Evidencias%20de%20documentaci%C3%B3n/Arquitectura/Documento%20de%20Dise%C3%B1o%20y%20Arquitectura%20Preliminar%20SIGET.docx). Las consultas de detalle, catálogos y administración de accesos descritas aquí completan la API disponible.

Las siguientes operaciones están previstas en la arquitectura, pero todavía no están implementadas:

| Método previsto | Ruta prevista | Función pendiente |
| --- | --- | --- |
| POST | `/api/tickets/{id}/asignar/` | Asignar o reasignar un ticket a un Técnico. |
| POST | `/api/ordenes-trabajo/` | Abrir una orden de trabajo. |
| POST | `/api/diagnosticos/` | Registrar un diagnóstico. |
| POST | `/api/repuestos/asignar/` | Registrar consumo de repuestos. |
| GET | `/api/auditoria/` | Consultar la bitácora de auditoría. |

Estas rutas no forman parte de los endpoints disponibles para pruebas de este incremento.
