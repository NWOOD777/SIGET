# Etiquetas QR de activos

**Ruta:** `/api/activos/{id}/qr/`  
**Permiso:** Administrador del sistema, verificado en PostgreSQL.

## Consultar la asociación

`GET` informa si el activo tiene una etiqueta registrada. No consulta al proveedor
externo ni modifica datos.

```json
{"id_activo": 1, "generado": false}
```

Cuando existe una asociación, se incluyen `id_qr`, `payload_qr`, `formato_imagen`,
`fecha_generacion` y `veces_reimpreso`.

## Generar o reimprimir

`POST` obtiene el SVG desde QR Server. El cuerpo es un objeto JSON:

```json
{"reimprimir": false}
```

Con `reimprimir: false`, se crea la asociación cuando todavía no existe. Repetir
esta operación conserva su identificador, fecha y contador. Con `reimprimir: true`,
se exige una asociación previa y se incrementa el contador después de recibir una
imagen válida. El contenido codificado siempre es el código de inventario original.
El contador registra las solicitudes de reimpresión preparadas por esta operación.

La respuesta HTTP 200 contiene los datos de la asociación, `id_activo`,
`codigo_inventario`, `numero_serie`, `marca`, `modelo` y el campo `svg` con la imagen
vectorial. No contiene información de usuarios. La tabla `codigo_qr` conserva la
asociación; la imagen se obtiene del proveedor en cada solicitud.

La consulta externa ocurre antes de la transacción de persistencia. La asociación
y su auditoría se guardan juntas, con bloqueo del activo para evitar duplicaciones
y pérdidas del contador ante solicitudes simultáneas. La generación no cambia la
serie, el estado ni los demás datos del equipo.

## Errores

| Estado | Situación |
|---|---|
| 400 | Cuerpo o identificador inválido. |
| 401 / 403 | Sesión ausente, inválida o sin autorización administrativa. |
| 404 | Activo inexistente o reimpresión solicitada sin una etiqueta previa. |
| 409 | El identificador cambió durante la solicitud o no coincide con la asociación. |
| 502 | Error del proveedor que requiere revisar la solicitud o configuración. |
| 503 | Indisponibilidad temporal, límite de solicitudes, tiempo agotado o respuesta inválida. |

Los errores del proveedor incluyen `detail`, `codigo` y `reintentable`. Un fallo no
crea asociaciones ni incrementa el contador. El escritorio muestra el error y
permite solicitar un nuevo intento.

## Uso en el escritorio

En **Activos TI**, seleccionar un activo y pulsar **Generar Etiqueta QR**. La ventana
muestra el código y los datos de la etiqueta y permite **Guardar PDF** o **Imprimir**.
Después de registrar un activo, el inventario lo deja seleccionado para este flujo.

Para un lote, seleccionar hasta 50 equipos con Ctrl o Mayús y pulsar **Imprimir
Lote**. Se procesan por separado; las etiquetas obtenidas se conservan y **Reintentar
pendientes** solicita únicamente las que fallaron. Cerrar la ventana detiene las
solicitudes pendientes; una solicitud que ya está en curso puede terminar.

Para una etiqueta dañada, abrir la ficha del activo y pulsar **Reimprimir QR**.
La ficha presenta una sola acción: **Generar etiqueta QR** si todavía no existe
una asociación y **Reimprimir QR** cuando ya está registrada. Después de generar
la primera etiqueta, el botón cambia a reimpresión sin cerrar la ficha.

El PDF usa A4 vertical con márgenes de 8 mm y una cuadrícula calculada según la
cantidad de etiquetas. Una etiqueta ocupa el área útil de la hoja; varias se
distribuyen buscando el mayor tamaño posible del QR, conservando su forma
cuadrada. Las filas incompletas se centran.

Cuando no caben todos los códigos con un lado mínimo de 25 mm, el lote se reparte
en páginas equilibradas. El QR permanece vectorial. El código de inventario se
muestra completo; la serie y el modelo se abrevian si exceden el espacio.
La distribución es para papel A4 común y no requiere hojas de rótulos de medidas
fijas.

La impresión directa utiliza el diálogo de impresoras del sistema. El PDF también
permite imprimir desde otro equipo. La preparación de la etiqueta se confirma
antes de enviar la solicitud; guardar o imprimir no repite la consulta externa.

[API de activos](../README.md) · [Proveedor QR Server](../../externas/qrserver/README.md)
