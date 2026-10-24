# API — Bitácora de Auditoría Interna

Corresponde a los servicios protegidos de trazabilidad histórica de operaciones y eventos críticos, consumidos principalmente por la aplicación de escritorio PySide6 para labores de auditoría administrativa.

| Métodos | Ruta | Descripción |
|---|---|---|
| GET | `/api/auditoria/` | Consulta cronológica de la bitácora con filtros y paginación |
| GET | `/api/auditoria/{id}/` | Consulta de detalle de un registro específico de auditoría |

---

## 1. Consulta general de auditoría

**GET `/api/auditoria/`**

Permite al Administrador del sistema consultar el registro histórico de operaciones críticas ejecutadas en los distintos módulos de SIGET.

### Permisos y control de acceso RBAC
- Requiere usuario activo autenticado (mediante encabezado `Authorization: Bearer <token>` en clientes nativos o sesión Web con CSRF).
- Exige de forma obligatoria el rol canónico **Administrador del sistema** y el permiso efectivo **`AUDITORIA_CONSULTAR`**, validados directamente contra PostgreSQL.
- Las solicitudes anónimas o con credenciales vencidas son rechazadas con **401 Unauthorized**.
- Las solicitudes de usuarios inactivos o con roles no privilegiados (**Técnico de soporte**, **Usuario solicitante**) son rechazadas con **403 Forbidden**.
- Los intentos de enviar roles alternativos en la sesión o en encabezados manipulados no amplían los privilegios efectivos.

### Parámetros de consulta (Query Params)

| Parámetro | Tipo | Descripción |
|---|---|---|
| `usuario` | String / Entero | Filtra por el actor responsable de la operación. Un valor numérico busca exclusivamente el ID del usuario. Un texto permite buscar RUT con formato, correo o fragmento de nombre. |
| `id_usuario` | Entero | Filtro estricto por el identificador numérico de clave primaria del usuario en PostgreSQL. Admite enteros positivos ASCII de hasta 2147483647; los valores inválidos retornan error 400. |
| `activo` | String | Filtra por el código de inventario exacto del equipo (ej. `ACT-001`), aunque sea completamente numérico. No se interpreta como clave primaria. |
| `codigo_inventario` | String | Alias equivalente a `activo`. |
| `modulo` | String | Filtro opcional por módulo del sistema (`USUARIOS`, `RBAC`, `ACTIVOS`, `ASIGNACIONES`, `SERVICE_DESK`, `ORDENES_TRABAJO`). |
| `accion` | String | Filtro opcional por código de acción (ej. `ACTIVO_MODIFICADO`, `OT_PAUSADA`). |
| `page` | Entero | Número de página a consultar. Entero mayor o igual a 1. Valor por defecto: `1`. |
| `page_size` / `limite` | Entero | Cantidad de registros por página. Entero entre 1 y 100. Valor por defecto: `25`. |

### Semántica de filtros y resolución de relaciones de activos

1. **Filtro por actor (`usuario`)**:
   Corresponde exclusivamente al usuario que ejecutó la acción registrada en la bitácora (`id_usuario`), no necesariamente al solicitante o custodio final del recurso. Si el evento proviene de una tarea automática del sistema, `id_usuario` es `null`.

2. **Filtro por activo (`activo` / `codigo_inventario`)**:
   La bitácora asocia operaciones a distintas tablas según la entidad afectada. La consulta resuelve las relaciones reales del equipo en el modelo relacional para consolidar:
   - Eventos directos del activo (`entidad_afectada = 'activo'`).
   - Asignaciones físicas y devoluciones del equipo (`asignacion`, `devolucion_activo`).
   - Solicitudes de asignación vinculadas materialmente mediante asignaciones reales del activo (`solicitud_asignacion`). No se asocian solicitudes de la misma categoría que no hayan sido entregadas con este activo.
   - Tickets de soporte asociados al equipo (`ticket`).
   - Atenciones técnicas y evaluaciones de satisfacción de dichos tickets (`comentario_ticket`, `evaluacion_csat`).
   - Órdenes de trabajo, diagnósticos e intervenciones asociadas (`orden_trabajo`, `diagnostico`, `intervencion`).

   Cada condición asocia de forma estricta el par `(entidad_afectada, id_registro_afectado)`, impidiendo colisiones entre registros de distintas tablas que compartan un mismo identificador numérico. Si el activo no existe, la consulta retorna un listado vacío válido sin generar fallos del servidor.

3. **Combinación de filtros**:
   La especificación simultánea de `usuario` y `activo` aplica una intersección lógica (`AND`), retornando los eventos sobre dicho equipo ejecutados por ese usuario particular.

### Ordenamiento
Los resultados se ordenan de forma estable y determinista utilizando orden cronológico inverso:
1. `fecha_evento` descendente (los eventos más recientes primero).
2. `id_auditoria` descendente (para desempatar transacciones simultáneas con igual marca de tiempo).

### Respuesta exitosa (200 OK)

```json
{
  "count": 45,
  "page": 1,
  "page_size": 25,
  "total_pages": 2,
  "results": [
    {
      "id_auditoria": 158,
      "fecha_evento": "2026-10-23T19:40:12.123456+00:00",
      "id_usuario": 1,
      "usuario": "Administrador Principal",
      "usuario_correo": "admin@siget.example",
      "usuario_rut": "11111111-1",
      "modulo": "ACTIVOS",
      "accion": "ACTIVO_MODIFICADO",
      "entidad_afectada": "activo",
      "id_registro_afectado": 12,
      "recurso": "activo #12",
      "detalle_evento": "ACTIVO_MODIFICADO: ACT-012. Estado actualizado a En reparación.",
      "direccion_ip": "192.168.1.150"
    },
    {
      "id_auditoria": 157,
      "fecha_evento": "2026-10-23T18:15:00+00:00",
      "id_usuario": null,
      "usuario": null,
      "usuario_correo": null,
      "usuario_rut": null,
      "modulo": "NOTIFICACIONES",
      "accion": "PROCESO_CORREO",
      "entidad_afectada": "notificacion",
      "id_registro_afectado": null,
      "recurso": "notificacion",
      "detalle_evento": "Despacho por lotes completado.",
      "direccion_ip": null
    }
  ]
}
```

### Búsqueda sin coincidencias (Criterio 4)
Cuando los criterios ingresados no coinciden con ninguna operación registrada, el endpoint retorna **200 OK** con resultado vacío:

```json
{
  "count": 0,
  "page": 1,
  "page_size": 25,
  "total_pages": 0,
  "results": []
}
```

La aplicación de escritorio presenta exactamente el mensaje:
> *"No se encontraron eventos de auditoría coincidentes con los criterios ingresados"*

---

## 2. Detalle de evento de auditoría

**GET `/api/auditoria/{id}/`**

Permite consultar el registro individual completo en solo lectura.

- Respuesta **200 OK**: objeto JSON con la estructura completa del evento.
- Respuesta **404 Not Found**: si el identificador no existe.

---

## 3. Inmutabilidad y protección de registros

1. **Rechazo de operaciones de escritura**:
   Los métodos `POST`, `PUT`, `PATCH` y `DELETE` están explícitamente deshabilitados en los endpoints de auditoría y responden con **405 Method Not Allowed**. La base de datos no sufre alteraciones.
2. **Inexistencia de acciones de escritura en el cliente**:
   La interfaz PySide6 no dispone de controles gráficos, botones ni formularios de edición o eliminación de registros de auditoría.
3. **Ausencia de efectos colaterales**:
   La consulta de la bitácora no modifica registros existentes ni genera eventos de lectura recursivos.
4. **Protección de datos sensibles**:
   Los registros de auditoría no almacenan contraseñas, tokens de acceso ni cabeceras confidenciales. Las direcciones IP se resuelven de forma autoritativa mediante el backend (`direccion_ip_cliente`).

---

## 4. Uso en la Aplicación de Escritorio

1. Iniciar sesión con una cuenta autorizada con rol **Administrador del sistema**.
2. En la barra de navegación lateral, seleccionar **«Auditoría interna»**.
3. Las fechas se presentan en la hora local del computador, conservando explícitamente el desfase UTC. La vista despliega la tabla con las columnas: **Fecha / Hora**, **Usuario**, **IP**, **Acción**, **Módulo** y **Recurso**.
4. Ingrese un identificador de usuario o código de inventario en los campos superiores y presione **Buscar** (o tecla Enter).
5. Seleccione cualquier fila para habilitar el botón **«Ver detalle»** (o haga doble clic sobre la fila) para abrir el diálogo modal de detalle de solo lectura.
6. Utilice los botones **«◀ Anterior»** y **«Siguiente ▶»** para navegar entre páginas.
7. Presione **«Limpiar filtros»** para reestablecer la vista general. Al cerrar sesión, la tabla e información se eliminan de memoria inmediatamente.



## Selección de filtros en escritorio

«Elegir actor» permite buscar por nombre completo o correo y seleccionar el ID exacto de un actor registrado en la bitácora. «Elegir equipo» busca por código, serie, marca o modelo y aplica el código de inventario exacto del resultado elegido. No es necesario memorizar identificadores. Si se modifica el texto seleccionado, deja de utilizarse la selección anterior. «Limpiar filtros» elimina ambas selecciones.

`GET /api/auditoria/opciones/?tipo=usuario|activo&search=texto` utiliza los mismos permisos de auditoría, devuelve `results` y `has_more`, y limita cada consulta a 20 opciones ordenadas. La búsqueda admite hasta 120 caracteres. Los actores contienen únicamente `id` y `etiqueta` (nombre/correo); los equipos contienen `codigo` y `etiqueta` (código, marca, modelo y serie). No expone RUT, credenciales ni el catálogo completo. Cuando `has_more` es verdadero, debe acotarse la búsqueda.
