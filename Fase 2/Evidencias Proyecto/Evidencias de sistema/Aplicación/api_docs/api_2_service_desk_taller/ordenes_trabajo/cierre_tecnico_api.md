# E6-H17 — API de cierre técnico

## POST /api/ordenes-trabajo/{id}/completar/

Ejecuta el servicio interno de cierre técnico. No requiere ser el responsable
original; conserva responsables y registra al ejecutor autenticado.

Autenticación existente: Bearer Auth0 o sesión SIGET. Sesión requiere CSRF válido;
Bearer no requiere CSRF. Técnico activo con rol Técnico de soporte y permisos
efectivos OT_GESTIONAR y TICKET_ATENDER, consultados en PostgreSQL.

### Solicitud: reparación exitosa

```json
{
  "resultado": "REPARACION_EXITOSA",
  "solucion_aplicada": "Se reemplazó el componente defectuoso.",
  "pruebas_realizadas": "Encendido y conectividad verificados."
}
```

Solo desde OT En Reparación. Resultado: Completada, activo Disponible, ticket Resuelto.

### Solicitud: no reparable

```json
{
  "resultado": "NO_REPARABLE",
  "informe_descarte": "Daño irreversible en la placa principal."
}
```

Desde OT En Diagnóstico o En Reparación. Resultado: Completada, activo Dado de baja,
ticket Resuelto. Se persisten avisos por correo a administradores activos con
correo válido; si no hay destinatarios, se registra advertencia operativa.

### Validación

El cuerpo debe ser un objeto JSON. Los textos obligatorios deben ser cadenas no
vacías, sin aceptar solo espacios. El catálogo de resultado es cerrado; los campos
TEXT no tienen un límite funcional adicional. Los campos del resultado contrario
son opcionales. Se rechaza cualquier campo adicional con 400, incluidos actor,
fecha, identificador de OT y estados finales. El ID de OT procede de la URL.

Rechaza OT Pausada/Completada, ticket Resuelto/Cerrado, relaciones o estados del
activo incompatibles, asignaciones sin finalizar y otra OT vigente del activo.
No cambia diagnósticos, responsables ni stock. No envía HTTP de correo desde la vista.

### Respuesta 200

Ejemplo ilustrativo; los identificadores y la fecha se generan en el servidor:

```json
{
  "id_orden": 123,
  "estado": "Completada",
  "resultado": "REPARACION_EXITOSA",
  "id_cierre_tecnico": 45,
  "fecha_cierre": "2026-10-29T14:00:00Z",
  "id_activo": 67,
  "estado_activo": "Disponible",
  "id_ticket": 89,
  "estado_ticket": "Resuelto"
}
```

Para NO_REPARABLE se conserva la estructura; resultado cambia a NO_REPARABLE y
estado_activo a Dado de baja. Fecha ISO 8601, conforme al renderizador DRF.

### Errores

| HTTP | Condición |
| --- | --- |
| 400 | JSON/campos/ID inválidos, estado o cierre no permitido, segundo cierre |
| 401 | Bearer inválido conforme a la autenticación existente |
| 403 | Sesión ausente, usuario no autorizado/inactivo o fallo CSRF |
| 404 | OT inexistente (con cuerpo válido y usuario autorizado), o ruta no coincidente |
| 405 | Método distinto de POST |
| 500 | Error inesperado; no se transforma un error PostgreSQL en mensaje REST con SQL |

Errores de campos usan objetos con listas de mensajes. Ejemplo de campos extra:
`{"non_field_errors": ["El cuerpo contiene campos no permitidos."]}`.
404: `{"detail": "La orden de trabajo no existe."}`.
No se introduce 409 para cierre duplicado; se conserva 400 del servicio.
La respuesta genérica 500 depende del manejo estándar de Django y DEBUG=False;
no se habilita DEBUG en despliegues expuestos.

### Transacción e instalación

La vista no abre otra transacción ni escribe modelos directamente. Delega al
servicio atómico existente, que registra cierre, OT, activo, ticket, historial,
auditoría y notificaciones. Un segundo cierre no duplica efectos persistidos.

**La tabla cierre_tecnico sigue sin instalarse en siget_db.** Antes de habilitar
este endpoint en desarrollo se requiere autorización para instalar y verificar
el SQL aditivo de la Etapa 1. No ejecutar init_siget_bd.sql sobre desarrollo.
Las pruebas utilizan exclusivamente test_siget_db con HTTP/SMTP externos bloqueados.

La [interfaz PySide6](cierre_tecnico_escritorio.md) ya está implementada; su
demostración real depende de la instalación PostgreSQL autorizada.

## Instalación de la tabla `cierre_tecnico`

**Estado actual: instalación pendiente en la base de desarrollo inspeccionada.**
Actualizar el repositorio con `git pull` no instala esta tabla: el modelo utiliza
`managed=False` y no hay una instalación automática mediante migraciones.

### Base de datos nueva

La tabla ya está definida en `Base de datos/init_siget_bd.sql`, situado fuera del
directorio de aplicación (`../Base de datos/init_siget_bd.sql` desde Aplicación).
Al preparar una base completamente nueva mediante el procedimiento de
inicialización del proyecto, se creará junto con las demás tablas.

### Base de datos existente

Si PostgreSQL ya contiene tablas y datos de SIGET, utilizar exclusivamente
`siget_web/ordenes_trabajo/sql/e6_h17_cierre_tecnico.sql` para instalar esta entidad.
El script crea la tabla, su secuencia, índices implícitos de PK/UNIQUE y restricciones;
no elimina ni recrea tablas existentes.

Antes de ejecutarlo:

1. Confirmar contenedor, volumen, base y esquema reales. Revisar compatibilidad de
   `public.orden_trabajo.id_orden` y `public.usuario.id_usuario` (PK integer), permisos
   y ausencia de objetos incompatibles con los nombres del script.
2. Preparar un respaldo verificable fuera del repositorio: comprobar resultado,
   integridad del archivo y posibilidad de restaurarlo en un entorno aislado.
3. Revisar el script aprobado y acordar una ventana con el equipo.
4. Fijar explícitamente `search_path=public` en la conexión que lo ejecute; por
   ejemplo, mediante la opción de conexión `-c search_path=public`. Los nombres del
   script no están calificados. Usar `psql -X -v ON_ERROR_STOP=1`, base explícita y
   límites de espera acordados. El script ya contiene `BEGIN` y `COMMIT`.
5. Ejecutar únicamente después de recibir autorización explícita de instalación.

No volver a ejecutarlo sin comprobar antes el estado: no usa `IF NOT EXISTS` y una
segunda ejecución falla deliberadamente. Una instalación parcial o distinta exige
inspección y un procedimiento específico; no eliminar objetos para forzarla.

### Advertencia importante

**NO ejecutar `init_siget_bd.sql` sobre una base existente que se quiera conservar.**
Contiene instrucciones `DROP TABLE ... CASCADE` y puede eliminar tablas y datos.
Tampoco recrear contenedores o cambiar volúmenes como forma de instalar esta tabla.

### Dependencia de E7-H18

La auditoría de la base de desarrollo detectó que faltaban las columnas de anulación
de `orden_repuesto`, su FK/CHECK y `repuesto.activo`; también observó un predeterminado
de stock mínimo diferente. La sincronización debe coordinarse con el responsable
de E7-H18. No se afirma que esas diferencias estén corregidas o instaladas.

No son dependencias directas del CREATE de cierre_tecnico, pero deben revisarse para
operar y demostrar coherentemente el módulo integrado. Esta sección no autoriza ni
automatiza la instalación de E7-H18.

### Verificación posterior de solo lectura

En una conexión con `default_transaction_read_only=on`, confirmar primero base,
esquema y modo, y después inspeccionar la definición instalada:

```sql
SELECT current_database(), current_schema(),
       current_setting('transaction_read_only');

SELECT to_regclass('public.cierre_tecnico');

SELECT column_name, data_type, is_nullable, column_default,
       character_maximum_length
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'cierre_tecnico'
ORDER BY ordinal_position;

SELECT c.conname, c.contype, pg_get_constraintdef(c.oid)
FROM pg_constraint AS c
JOIN pg_class AS t ON t.oid = c.conrelid
JOIN pg_namespace AS n ON n.oid = t.relnamespace
WHERE n.nspname = 'public' AND t.relname = 'cierre_tecnico'
ORDER BY c.conname;

SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public' AND tablename = 'cierre_tecnico';

SELECT pg_get_serial_sequence('public.cierre_tecnico', 'id_cierre_tecnico');
```

Comparar con `ordenes_trabajo.models.CierreTecnico`: PK AutoField/integer; OT única;
FK integer a OT y usuario con RESTRICT; resultado VARCHAR(32); tres campos TEXT
nullable; fecha_cierre TIMESTAMPTZ no nula con hora del servidor. Verificar PK,
ambas FK, UNIQUE y los CHECK de resultado y contenido Unicode de 29 caracteres.
Estos SELECT inspeccionan estructura; las pruebas de rechazo, concurrencia y el
POST de cierre realizan escrituras y requieren otro entorno/autorización.

La reparación exitosa deja el activo Disponible; no lo reasigna automáticamente
al trabajador anterior. Esa decisión funcional está fuera del alcance actual.
