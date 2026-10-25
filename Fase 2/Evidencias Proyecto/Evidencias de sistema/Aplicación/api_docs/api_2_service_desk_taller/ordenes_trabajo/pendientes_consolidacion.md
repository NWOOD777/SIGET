# Pendientes de consolidación Service Desk / Taller

Este documento separa comportamiento observado de garantías deseadas. No autoriza
cambios funcionales ni sustituye los criterios oficiales. Producción de referencia:
`e2abc9e` más correcciones locales autorizadas de concurrencia e integridad.
Pruebas: `tickets.tests.test_consolidacion_ot_postgresql`.

| Caso | Caracterización / cobertura | Corrección o decisión pendiente |
|---|---|---|
| A | Corregido localmente: rechazo secuencial y concurrente de segunda OT vigente por activo. | Comprobación bajo bloqueo del activo, conservando unicidad por ticket y estados reales. |
| B | Corregido localmente con alternativa A aprobada: se restaura exactamente la fase previa; el activo se valida sin modificarlo. | Legado sin evidencia inequívoca se rechaza con 400; no se sanea silenciosamente. |
| C | Corregido localmente: inicio y pausa comparten bloqueo de fila OT, con validación posterior. | Pruebas en ambos órdenes, repetidas tres veces, y rollback. |
| D | Antes se reprodujo deadlock `40P01` por bloqueo de catálogos mediante JOIN. Ahora se bloquea solo la fila necesaria y se leen relaciones después del bloqueo. | La prueba exige ambos éxitos, repite tres veces y falla ante conflictos. No es una garantía universal contra todo deadlock. |
| E | Corregido localmente en etapa 2B: serializers tipados en vistas; errores 400 por campo para textos no textuales, IDs inválidos, booleanos y límites; cuerpos no objeto rechazados. | Se conservan servicios, respuestas válidas y formato de errores admitido por PySide6. |
| F | Mutaciones de OT inexistente: 400; historial: 404. Pruebas verifican formatos actuales y flujo válido. | Acordar si unificar errores y cómo preservar clientes existentes. |

## Interpretación de pruebas

- B ahora verifica restauración de fase; E reemplaza las aserciones de excepciones por 400 sin efectos.
  F conserva los contratos de inexistencia para IDs válidos.
- Están activas todas las garantías A/B/C/D/E. La última prueba omitida se activó
  para verificar diagnóstico y reparación. `test_validacion_entradas_ot` añade
  validación sin base; `test_reanudacion_fase_ot` cubre metadatos, legado y carreras.
- Concurrencia: conexiones independientes, eventos/barrera, esperas limitadas,
  `lock_timeout=4s` y `statement_timeout=8s`; cierre de conexiones al terminar.
- En D se exigen dos resultados `ok`; deadlock, timeout o excepción hacen fallar
  la prueba. Se comprueban estados y auditorías. SQL adicional comprueba el alcance
  `FOR UPDATE OF` sin bloqueo de catálogos.
- No se reemplazan operaciones de dominio para conseguir resultados favorables.
  La instrumentación SQL fija el orden; los fallos de auditoría se inyectan solo
  en las pruebas explícitas de rollback.

## Próxima etapa propuesta

1. Granularidad futura de OT_GESTIONAR: actualmente basta el rol técnico activo.
   No se propone restringir por propietario: la gestión colaborativa está confirmada.
2. Decisión de compatibilidad 400/404 para recursos inexistentes.

Coordinar estos cambios con el responsable de OT. No sincronizar automáticamente
responsables de ticket y OT. El cierre técnico y sus efectos sobre activo/ticket
pertenecen a E6-H17 y quedan fuera de esta etapa.

## Ejecución segura

Antes de ejecutar: confirmar `TEST_RUNNER`, nombre efectivo `test_siget_db` y DDL
protegido. El proceso de prueba debe impedir conexiones de aplicación a otras
bases y bloquear HTTP externo. La conexión administrativa de Django a `postgres`
se usa exclusivamente para crear/eliminar la base temporal, no `siget_db`.
No ejecutar migraciones sobre desarrollo ni consumidores de correo contra pruebas.

## Resultados históricos de la etapa de caracterización

Ejecución con ambos archivos Compose locales, sin modificar su configuración,
mediante `exec -T web python -B -` y un envoltorio en memoria del runner Django.
Se comprobó que desarrollo configura `siget_db`, TEST configura `test_siget_db`
y el runner es `siget.testing.PostgreSQLTestRunner`. El envoltorio fuerza el
nombre de aplicación a `test_siget_db`, rechaza otras conexiones (excepto
`__no_db__` a `postgres` para administrar la base temporal) y bloquea HTTP externo.
La base temporal se creó y eliminó mediante el runner. No se abrió una conexión
de prueba a `siget_db` ni se ejecutó el consumidor de correos sobre pruebas.

| Selección Django | Descubiertas | Aprobadas | Fallidas / errores | Omitidas |
|---|---:|---:|---:|---:|
| `tickets.tests.test_consolidacion_ot_postgresql` (versión final) | 15 | 10 | 0 | 5 |
| `tickets ordenes_trabajo` (incluye las nuevas) | 234 | 229 | 0 | 5 |

Los grupos se superponen y no deben sumarse. El grupo relacionado se ejecutó antes
del último ajuste que añade límites de espera también a la conexión principal;
después se volvió a ejecutar el archivo nuevo completo, con el resultado indicado.
No se ejecutó la suite general de 681 pruebas.

El deadlock D se reprodujo en las ejecuciones realizadas con resultado
`('ok', '40P01')`. Las caracterizaciones A, B, C y E también reprodujeron las
brechas descritas. Las cinco omisiones son garantías pendientes, no aprobaciones.

## Alcance de la corrección local de concurrencia

No se cambiaron estados, permisos, HTTP válidos, modelos, SQL ni servicios de
tickets. Se conserva `@transaccion_operacion` y la numeración con bloqueo global.
Orden de recursos: creación global → ticket → activo → inserción de OT;
inicio advisory por operación → OT → activo; pausa/reanudación/reasignación
advisory por operación → OT. La consulta de duplicados no bloquea OT existentes.
Las relaciones de OT se leen después de adquirir su bloqueo para validar el
estado vigente, evitando además depender de datos relacionados de un JOIN previo.

El bloqueo de activo se limita a su fila. No se añade bloqueo global para la
nueva regla; continúa la serialización global preexistente por numeración.
No requiere migración. Escritores futuros, incluido E6-H17, deben respetar estos
recursos y orden; las pruebas no demuestran ausencia universal de condiciones de carrera.

## Validación histórica de la etapa 2A

Se conserva el envoltorio en memoria de aislamiento y bloqueo de HTTP descrito
arriba, ambos archivos Compose y exclusivamente `test_siget_db` para aplicación,
DDL y migraciones de pruebas. La conexión administrativa `postgres` no accede
a `siget_db`. El runner eliminó la base temporal después de las ejecuciones.

| Selección | Descubiertas | Aprobadas | Fallidas / errores | Omitidas |
|---|---:|---:|---:|---:|
| Consolidación (archivo final) | 17 | 15 | 0 | 2 |
| `tickets ordenes_trabajo` | 236 | 234 | 0 | 2 |
| Suite general Django | 698 | 696 | 0 | 2 |

Los grupos se superponen y no se suman. Las dos omisiones permanecen por decisiones
funcionales/validación tipada, no por concurrencia. Las pruebas repiten tres veces
creación concurrente para el mismo activo, ambos órdenes de inicio/pausa y
pausa/reanudación de OT diferentes. Se verifican rollback y ausencia de efectos
parciales al fallar auditoría, y compatibilidad de los contratos HTTP vigentes.

No hubo `40P01` ni timeouts en los escenarios corregidos de estas ejecuciones.
Esto valida las intercalaciones controladas ensayadas; no garantiza ausencia de
deadlocks en escritores futuros o fuera del protocolo de bloqueo revisado.

## Etapa 2B: validación tipada de entrada

Se agregaron serializers de entrada y se integraron únicamente en vistas OT.
No se modificaron servicios, estados, bloqueos, permisos, modelos ni serialización
de salida. Textos estrictos, booleanos JSON estrictos, IDs positivos y límites
AutoField derivados del backend. Se preservan IDs como cadenas ASCII y campos
extra ignorados; no se impone un máximo artificial a los TextField existentes.

Se inspeccionaron los payloads de `siget_desktop/api/services.py` y el recolector
de errores de `api/client.py`: los formatos válidos y errores campo/lista siguen
siendo compatibles. El agente no ejecutó una interfaz PySide6 real en esta validación.

Cambios de error deliberados por validación de entrada: tipos antes causantes de
excepciones internas ahora producen 400; cuerpos JSON no objeto devuelven 400;
IDs de ruta cero/fuera de rango devuelven 400 `id_orden`. Segmentos no admitidos
por el converter siguen 404. IDs válidos inexistentes mantienen 400/404 actuales.
Con varios campos inválidos puede haber varios mensajes, conservando el formato
campo → lista; no se conserva la prioridad anterior del primer error.

### Resultados de validación 2B

Se volvió a comprobar configuración de desarrollo `siget_db`, TEST
`test_siget_db` y runner protegido antes de ejecutar. Todas las ejecuciones usaron
ambos archivos Compose y el mismo envoltorio en memoria que fuerza aplicación a
`test_siget_db`, rechaza conexiones a desarrollo y bloquea HTTP externo.
La base temporal se creó y eliminó mediante el runner; sin migraciones sobre desarrollo.

| Selección | Descubiertas | Aprobadas | Fallidas / errores | Omitidas |
|---|---:|---:|---:|---:|
| Consolidación + validación unitaria de entradas | 25 | 24 | 0 | 1 |
| `tickets ordenes_trabajo` | 244 | 243 | 0 | 1 |
| Suite general Django | 706 | 705 | 0 | 1 |

Son grupos superpuestos. Permanece únicamente la omisión sobre semántica de
reanudación. Se reemplazaron caracterizaciones de AttributeError/ValueError por
400 sin efectos parciales, se activó la garantía tipada pendiente y se agregaron
pruebas de cuerpos no objeto, rutas, extremos, nulos, tipos estrictos, ausencia de
cuerpo compatible con PySide6, formato de salida y mensajes por campo.
La suite conservó las pruebas de concurrencia y regresión anteriores.

## Recuperación de fase: alternativa A aprobada

`auditoria_fases.py` añade al detalle legible una última línea versionada con JSON
de fase, ID, acción y motivo. Se verifica contra la OT y su justificación; no se
interpreta el motivo ni se aceptan destinos del cliente. Un motivo que contiene el
marcador no reemplaza la última línea generada por el servidor.

La última transición debe ser OT_PAUSADA; solo OT_REASIGNADA se ignora al recuperar
fase. Un registro explícito válido es suficiente aunque falten eventos más antiguos.
Sin registro explícito se acepta únicamente el primer ciclo completo desde
OT_CREADA, con cero o un REPARACION_INICIADA antes de la pausa. Historial incompleto,
acciones desconocidas, ciclos antiguos ambiguos o metadatos inválidos devuelven
400. No se supone que toda OT histórica sea recuperable ni se migra su información.

La OT se bloquea antes de recuperar fase y el activo se bloquea antes de validar
su estado. Diagnóstico requiere En revisión; reparación requiere En reparación.
No se actualiza el activo automáticamente. Auditoría, fase y limpieza del motivo
comparten transacción; se conservan eventos y cálculo temporal del SLA.

Se mantienen métodos, rutas, cuerpo de reanudación, permisos, responsables y campos
de salida. Cambia el estado devuelto según la decisión aprobada y se agregan errores
400 de historial/activo incompatibles. El escritorio ya representa ambos estados
y refresca tras éxito; el agente no modificó ni ejecutó la interfaz PySide6 real.

Riesgos residuales: la recuperación depende de la integridad de la bitácora,
igual que otros usos de auditoría. Escrituras directas fuera del protocolo no
quedan cubiertas por los bloqueos de servicios. Casos históricos rechazados
requieren revisión autorizada, no un destino por defecto. E6-H17 y los cambios
de responsabilidad/RBAC quedan fuera de esta etapa.

### Política confirmada para la entrega final

Cualquier Técnico de soporte activo puede pausar, reanudar o reasignar una OT,
aunque no sea su responsable. Las restricciones de estado, coherencia y transacción
siguen aplicando. E6-H16/E6-H24 revisadas describen el rol técnico y no exigen
exclusividad del responsable; no se identificó contradicción con esta política.
No sincronizar automáticamente los responsables de ticket y OT.

OT_GESTIONAR permanece en el catálogo, sin comprobación explícita en estas vistas.
Se documenta como futura decisión de granularidad de permisos, no como defecto
pendiente de esta entrega. Tampoco se cambian los contratos de inexistencia 400/404.

El usuario confirmó manualmente que PySide6 funciona correctamente. Las validaciones
automatizadas registradas aquí corresponden al backend; no sustituyen esa prueba
manual ni afirman que la suite gráfica se haya ejecutado en este entorno.

La revisión final repitió las validaciones con el mismo aislamiento: 62 pruebas
focalizadas, 255 de tickets/OT y 717 de la suite general aprobadas, sin fallos,
errores ni omisiones en ningún grupo. Los grupos se superponen y no se suman.
Durante esa revisión solo se añadieron aclaraciones documentales; no se cambió
código ni se crearon commits o staging.

### Resultados de la alternativa A

Verificación previa del runner protegido y `TEST.NAME=test_siget_db`; mismo
envoltorio en memoria con bloqueo de conexiones a `siget_db` y HTTP externo.
Ambos archivos Compose locales, sin modificar configuración. Todas las escrituras,
DDL y migraciones del runner se realizaron exclusivamente en la base temporal,
creada y eliminada al terminar. `postgres` se utilizó solo como conexión administrativa.

| Selección final | Descubiertas | Aprobadas | Fallidas / errores | Omitidas |
|---|---:|---:|---:|---:|
| Consolidación, fases y pausa/derivación | 62 | 62 | 0 | 0 |
| `tickets ordenes_trabajo` | 255 | 255 | 0 | 0 |
| Suite general Django | 717 | 717 | 0 | 0 |

Los grupos se superponen. Se activó la última omisión. Once pruebas nuevas cubren
ambas fases y ciclos repetidos, formato y validación de metadatos, legado recuperable
y ambiguo, activo incompatible, rollback, motivo que contiene el marcador, historial
y payload PySide6. La duración de pausas continúa cubierta por las pruebas existentes.
Pausa/reanudación sobre la misma OT se repite tres veces por orden; se prueban ambos
órdenes de reanudación/reasignación y revalidación ante cambio concurrente del activo.
El agente no ejecutó el escritorio real, no se revisaron registros de desarrollo y no se
modificaron sus datos. Los resultados no garantizan ausencia universal de deadlocks.
