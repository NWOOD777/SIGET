# Identificar un equipo por etiqueta o serie

`GET /api/activos/identificar/`

Consulta exacta para Administrador del sistema y Técnico de soporte. La autorización
se verifica mediante los roles del usuario en PostgreSQL. La respuesta contiene la
ficha del activo y no incluye datos personales de su custodio.

| Parámetro | Obligatorio | Descripción |
|---|---|---|
| `identificador` | Sí | Código de inventario o número de serie, hasta 100 caracteres. |
| `id_solicitud` | No | Valida la elegibilidad para entregar un equipo en una solicitud aprobada. |
| `id_asignacion` | No | Valida que el equipo corresponda a una asignación activa durante su devolución. |

Los dos parámetros de contexto son excluyentes. Los identificadores admiten letras
ASCII y dígitos, con guiones, guiones bajos, puntos o barras simples entre grupos
alfanuméricos. No se eliminan espacios ni se convierten números: los ceros iniciales
forman parte de la serie. El código de inventario se compara sin distinguir
mayúsculas; la serie conserva la coincidencia exacta registrada.

Ejemplo:

```http
GET /api/activos/identificar/?identificador=ACT-0001&id_solicitud=12
```

La respuesta `200` utiliza el mismo formato de la
[ficha del activo](detalle_y_modificacion.md), incluyendo `id_activo`,
`codigo_inventario`, `numero_serie`, `modelo`, `marca`, `categoria`, `ubicacion` y
`estado`.

| Estado | Resultado |
|---|---|
| `200` | Activo identificado y compatible con el contexto solicitado. |
| `400` | Identificador o parámetros inválidos. |
| `401` / `403` | Sesión ausente o permisos insuficientes. |
| `404` | Activo, solicitud o asignación inexistente. |
| `409` | Identificador ambiguo, categoría incompatible, equipo no disponible, solicitud sin aprobación o con entrega previa, o equipo ajeno a la asignación activa. |

La consulta no modifica registros. El registro definitivo de entrega o devolución
vuelve a verificar sus reglas en el backend, ya que el estado del equipo puede
cambiar después de la lectura.

Un lector QR o de barras HID entrega el texto ya decodificado al campo del
escritorio. No se envían imágenes ni se ejecutan direcciones o comandos recibidos
desde una etiqueta. USB y Bluetooth utilizan la misma entrada de teclado; esta
captura local es independiente del servicio externo de generación de imágenes QR.

[Índice de activos y asignaciones](../README.md)
