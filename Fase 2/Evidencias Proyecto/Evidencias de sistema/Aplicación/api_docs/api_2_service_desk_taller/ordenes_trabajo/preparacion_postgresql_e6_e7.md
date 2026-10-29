# Preparación PostgreSQL E6-H17 / E7-H18 — sin instalación

## Política de espacios de E6-H17

Un campo obligatorio es vacío si es NULL o si al quitar estos 29 caracteres no
queda contenido: U+0009–000D, U+001C–001F, U+0020, U+0085, U+00A0, U+1680,
U+2000–200A, U+2028, U+2029, U+202F, U+205F y U+3000.
Coinciden con str.isspace() de Python 3.12. La constante ESPACIOS_CIERRE fija la
política; una prueba detecta cambios en futuras versiones de Python.

La validación usa strip con ese conjunto. El CHECK usa translate con exactamente
los mismos puntos Unicode, sin regex dependiente de lc_ctype. Ambos requieren
contenido para solución/pruebas de éxito o informe de descarte de no reparable.
Los campos opcionales siguen permitiendo NULL, vacío o espacios. No se impone
normalización Unicode ni se considera U+200B (ZERO WIDTH SPACE) un espacio vacío.
Los textos reales, incluso rodeados de espacios, siguen siendo válidos.

Se actualizaron únicamente las expresiones de contenido de cierre_tecnico del
script aditivo y del esquema de referencia; no su sección destructiva. El script
de cierre sigue sin instalarse en desarrollo. En una base donde la tabla ya
existiera, este CREATE no actualizaría sus CHECK: haría falta otra revisión aditiva.

## Diferencias E7-H18 observadas en la auditoría

- public.orden_repuesto carece de anulado, fecha_anulacion, motivo_anulacion,
  id_usuario_anulacion, su FK y ck_orden_repuesto_anulacion.
- public.repuesto carece de activo; stock_minimo tiene DEFAULT 1.
- Los modelos managed=False esperan estos campos; stock_minimo tiene default 5.
- Existen PK enteras de usuario y orden_repuesto e índice por id_orden.
- El contenedor auditado usa siget_postgres_data, distinto del volumen definido
  en el override local. No recrear el contenedor ni cambiar volúmenes para instalar.

## Propuesta pendiente de revisión con el responsable de E7-H18

Archivo: siget_web/ordenes_trabajo/sql/propuesta_e7_h18_sincronizacion.sql.
No se ejecutó, tampoco en las pruebas de esta tarea. No se cambió código de negocio.

Agrega columnas con tipos compatibles, FK de responsable de anulación a usuario
con ON DELETE RESTRICT y el mismo CHECK que el esquema de referencia de E7-H18.
No se amplía la corrección Unicode a ese CHECK: cambiaría el contrato de otro módulo.
No incorpora índices nuevos: las operaciones actuales identifican imputaciones por
PK y OT, ya indexadas. La FK no crea índice automáticamente; evaluar uno sobre
id_usuario_anulacion si el volumen y operaciones de eliminación de usuarios lo exigen.

### Historia y predeterminados

- anulado NOT NULL DEFAULT FALSE interpreta todas las imputaciones anteriores
  como vigentes. Los tres campos de detalle son nullable y quedan NULL.
- activo NOT NULL DEFAULT TRUE interpreta todos los repuestos anteriores como
  activos. NO deduce bajas históricas ni reconstruye anulaciones.
- El responsable debe confirmar esas interpretaciones contra trazabilidad existente
  antes de aprobar. Si hay bajas/anulaciones anteriores, detenerse y preparar una
  reconciliación específica; no inventar actor, fecha o motivo.
- SET DEFAULT 5 afecta solo inserciones futuras que omitan stock_minimo. No cambia
  los mínimos existentes ni stock, costos, consumos o movimientos. Este cambio de
  predeterminado forma parte de la propuesta y requiere aprobación explícita.

No contiene UPDATE/DELETE ni reemplaza tablas. Agregar campos con predeterminado
constante en PostgreSQL 17 puede usar el mecanismo de valor faltante sin reescribir
todas las filas, pero cambia su interpretación y necesita bloqueos de esquema.

### Reejecución y compatibilidad

Instalación de una sola ejecución. BEGIN/COMMIT agrupa todos los cambios; psql debe
usar ON_ERROR_STOP=1. Si una columna o restricción ya existe, falla y revierte, en
vez de asumir que es compatible. No es idempotente: no volver a ejecutarlo tras
éxito. Para estados parcialmente instalados, inspeccionar y preparar otro script.
Se incluyen lock_timeout=5s y statement_timeout=30s; un timeout exige detenerse y
revisar, no quitar las protecciones automáticamente. CHECK/FK pueden requerir
escaneo y ALTER TABLE necesita bloqueos fuertes: acordar ventana de mantenimiento.

## Procedimiento propuesto (no ejecutado)

1. Confirmar base siget_db, esquema public, versión, contenedor y volumen efectivos.
2. Inspeccionar de nuevo columnas, tipos, restricciones y nombres en solo lectura.
3. Revisar las interpretaciones históricas con el responsable de E7-H18.
4. Obtener respaldo íntegro fuera del repositorio, SHA-256, pg_restore --list y
   verificar restauración aislada con autorización separada.
5. Ensayar el script E7-H18 sobre una copia de esquema anterior en una base aislada
   autorizada, con registros sintéticos. Probar datos históricos, FK, CHECK, rollback
   y rechazo seguro de segunda ejecución. Esta instalación de ensayo queda pendiente.
6. Revisar el diff/hash aprobado, coordinar ausencia de escrituras y ejecutar solo
   el script aditivo autorizado, con psql -X -v ON_ERROR_STOP=1. Nunca init_siget_bd.sql.
7. Inspeccionar columnas, nulabilidad, defaults y pg_get_constraintdef; comprobar
   que no cambiaron valores previos de stock, costo ni stock_minimo.
8. Probar E7-H18 en entorno aislado; cualquier prueba real de API en desarrollo
   requiere autorización y datos de validación, porque modifica stock y movimientos.
9. Instalar cierre_tecnico únicamente mediante autorización independiente.

## Recuperación

Un fallo antes del commit debe revertir la transacción completa. Detener el cliente
y comprobar el estado antes de reintentar. No eliminar columnas automáticamente.
Si ya hubo commit y operaciones nuevas, conservar los datos nuevos de anulación y
baja; deshacer eliminando columnas perdería trazabilidad. Preferir corrección
aditiva revisada. Una restauración requiere autorización, ventana coordinada y
reconciliar los cambios posteriores al respaldo; nunca restaurar automáticamente
encima de desarrollo. No se generaron respaldos ni se instalaron objetos en esta tarea.
