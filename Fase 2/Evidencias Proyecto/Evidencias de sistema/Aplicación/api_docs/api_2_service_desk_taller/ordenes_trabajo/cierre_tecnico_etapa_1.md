# E6-H17 — Cierre técnico: estructura y validación

Esta etapa prepara persistencia y validación. No hay endpoint, servicio de cierre,
transiciones ni notificaciones nuevas. El SQL está preparado, **no instalado**.

## Entidad

`CierreTecnico` (`cierre_tecnico`, `managed=False`) conserva un resultado definitivo
por OT, sin sobrescribir `Diagnostico` ni `Intervencion`.

| Campo | Contrato |
| --- | --- |
| id_cierre_tecnico | SERIAL / AutoField, clave primaria |
| id_orden | Entero, FK protegida, único, obligatorio |
| id_tecnico | Entero, FK protegida a usuario, obligatorio; ejecutor real |
| resultado | VARCHAR(32), REPARACION_EXITOSA o NO_REPARABLE |
| solucion_aplicada | TEXT nullable; obligatorio para éxito |
| pruebas_realizadas | TEXT nullable; obligatorio para éxito |
| informe_descarte | TEXT nullable; obligatorio para no reparable |
| fecha_cierre | TIMESTAMPTZ, hora del servidor, no editable |

Los textos obligatorios rechazan vacío y espacios. No se impone un máximo
arbitrario a TEXT: PostgreSQL no define una longitud funcional para estos campos.
El resultado tiene máximo 32 caracteres y catálogo cerrado. Los campos del
resultado contrario pueden omitirse; no se exige ni elimina contenido adicional.

## Capas de validación

- `validaciones_cierre.validar_contenido_cierre`: contenido y tipos, sin consultas.
- `CierreTecnicoEntradaSerializer`: objeto JSON, resultado y textos estrictos;
  normaliza espacios. No expone actor, fecha ni identificadores de persistencia.
- `CierreTecnico.full_clean()`: campos, existencia de referencias, unicidad y clean.
  Django no llama automáticamente full_clean al guardar. La futura operación
  transaccional debe validar y determinar el actor autenticado.
- SQL: PK, FK RESTRICT, UNIQUE por OT y CHECK de catálogo/contenido condicional.
  La FK verifica existencia del usuario, no su rol ni autorización RBAC.

La prevalidación de unicidad no evita carreras; UNIQUE es la garantía definitiva.
Las referencias protegidas impiden borrar un cierre como cascada de OT o usuario.
No se implementa todavía inmutabilidad del registro ni cambios de estado.

## Instalación pendiente

Script independiente: `siget_web/ordenes_trabajo/sql/e6_h17_cierre_tecnico.sql`.
El mismo DDL está en `Base de datos/init_siget_bd.sql` para instalaciones nuevas.
No ejecutar el esquema inicial sobre una base existente.

Antes de instalar: autorización independiente, respaldo, verificación de la base
destino/esquema, existencia y tipos de orden_trabajo y usuario, y ausencia de una
tabla cierre_tecnico incompatible. Revisar primero en una base aislada. El script
usa BEGIN/COMMIT y falla si ya existe la tabla; no oculta discrepancias mediante
IF NOT EXISTS. Crea únicamente tabla, secuencia e índices implícitos necesarios.
No altera datos históricos. managed=False no instala este DDL mediante migraciones.

## Evidencia y etapas posteriores

Las pruebas unitarias usan SimpleTestCase y mocks para referencias/unicidad;
comprueban también el contrato textual del SQL, no su ejecución PostgreSQL.
Las etapas posteriores agregaron pruebas PostgreSQL de FK, UNIQUE, CHECK, rollback
y concurrencia del cierre. La corrección posterior de Unicode utiliza
un conjunto explícito compartido por Python y SQL; consultar
[preparación PostgreSQL](preparacion_postgresql_e6_e7.md) y sus pruebas de equivalencia.

La siguiente etapa debe implementar una única transacción para cierre, OT, ticket,
activo, historial, auditoría y notificaciones persistentes. No debe permitir crear
un cierre parcial desde un endpoint genérico. Debe preservar E5-H14, E7-H18 y el
orden compatible de bloqueos, sin enviar correo dentro de la transacción.
