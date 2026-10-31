# Generación QR con QR Server

El backend solicita a QR Server una imagen SVG usando el código de inventario
del activo, por ejemplo `ACT-0001`. No envía datos de usuarios ni la ficha del equipo.

## Configuración

Definir en `.env` o en el entorno del backend:

```dotenv
QR_SERVER_URL=https://api.qrserver.com/v1/create-qr-code/
QR_SERVER_CONNECT_TIMEOUT_SECONDS=5
QR_SERVER_READ_TIMEOUT_SECONDS=15
QR_SERVER_SIZE=300
```

La API no requiere clave. SIGET admite únicamente el endpoint HTTPS indicado,
tiempos de espera de hasta 60 segundos y tamaños entre 10 y 1000 unidades por lado.
La imagen conserva su formato vectorial.

## Uso

El escritorio consulta el estado de la etiqueta mediante
`GET /api/activos/{id}/qr/` y solicita su generación o reimpresión mediante `POST`.
El backend verifica el acceso del Administrador y devuelve el SVG para visualizar,
imprimir o guardar como PDF. El [contrato de etiquetas](../../api_1_activos_asignaciones/activos/qr.md)
describe las entradas y respuestas.

Para obtener solo la imagen desde código del backend:

```python
from activos.qr import generar_qr_activo

imagen = generar_qr_activo(activo)
contenido_svg = imagen.contenido
```

El activo debe estar registrado. `ImagenQR` contiene `payload`, `contenido`,
`formato` y `tipo_contenido`; los fallos se informan como `ErrorGeneracionQR`.
La asociación con el activo y su auditoría se guardan mediante `preparar_etiqueta`.

Se rechazan respuestas inválidas, archivos mayores a 1 MiB y SVG con scripts o
recursos externos. Los fallos del proveedor permiten reintentar sin modificar
el equipo ni su etiqueta registrada.

## Comprobar la conexión

Desde `Aplicación`, con Docker en ejecución:

```bash
docker compose exec web python manage.py verificar_qr --codigo ACT-9999
```

Esta comprobación hace una solicitud real sin crear activos ni asociaciones QR.
Agregar `--salida /tmp/qr-verificado.svg` para guardar la imagen en un archivo nuevo
dentro del contenedor.

## Pruebas

```bash
docker compose exec web python manage.py test activos.tests.test_qr_client activos.tests.test_qr_activos_postgresql activos.tests.test_etiquetas_qr_postgresql --noinput
```

Las pruebas habituales simulan al proveedor. La prueba de conexión real se activa
por separado con `SIGET_TEST_QR_LIVE=1`.

[Documentación del proveedor](https://goqr.me/api/doc/create-qr-code/)
· [Privacidad](https://goqr.me/privacy-safety-security/)
· [Configuración](../../../configuracion.md)
