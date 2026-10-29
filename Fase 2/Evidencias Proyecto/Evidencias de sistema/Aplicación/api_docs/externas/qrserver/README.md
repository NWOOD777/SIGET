# Generación QR con QR Server

El backend utiliza la API pública de QR Server para obtener imágenes SVG a partir
del código de inventario de un activo. La solicitud contiene únicamente ese
identificador, por ejemplo `ACT-0001`. No incluye datos de usuarios ni la ficha del
equipo.

El proveedor admite solicitudes POST a
`https://api.qrserver.com/v1/create-qr-code/` y no requiere clave de API.
Consultar la [documentación oficial](https://goqr.me/api/doc/create-qr-code/)
y la [política de privacidad del proveedor](https://goqr.me/privacy-safety-security/).

## Configuración

Las variables se definen en el entorno del backend o en `.env` de `Aplicación`:

```dotenv
QR_SERVER_URL=https://api.qrserver.com/v1/create-qr-code/
QR_SERVER_CONNECT_TIMEOUT_SECONDS=5
QR_SERVER_READ_TIMEOUT_SECONDS=15
QR_SERVER_SIZE=300
```

La URL se restringe al endpoint HTTPS del proveedor. Los tiempos de conexión y
lectura son positivos y admiten hasta 60 segundos cada uno. El tamaño de presentación
admite entre 10 y 1000 unidades por lado. El contenido conserva su formato vectorial.
No se necesitan credenciales adicionales.

## Uso desde el backend

```python
from activos.qr import generar_qr_activo
from activos.qr_client import ErrorGeneracionQR

try:
    imagen = generar_qr_activo(activo)
except ErrorGeneracionQR as error:
    mensaje = str(error)
else:
    contenido_svg = imagen.contenido
```

`activo` debe ser una instancia guardada de `Activo`. El resultado `ImagenQR`
contiene el identificador en `payload`, los bytes en `contenido`, el formato `SVG`
y el tipo `image/svg+xml`. El código de inventario debe tener el prefijo `ACT-`
seguido de al menos cuatro dígitos, dentro del límite de 50 caracteres del campo.

La generación no modifica el activo ni escribe registros en PostgreSQL. El flujo
que la invoque controla la autorización administrativa, el almacenamiento de la
etiqueta y su presentación. Mantener la solicitud externa fuera de las transacciones
que registran el activo permite conservarlo si el proveedor falla.

## Errores y respuesta

`ErrorGeneracionQR` entrega un mensaje, un `codigo` y el indicador `transitorio`.
Los códigos distinguen configuración o identificador inválidos, errores HTTP,
tiempo agotado, falta de conexión, errores de red y respuestas inválidas.
Los errores de conexión, espera, HTTP 429 y HTTP 5xx permiten un nuevo intento
controlado. No se repiten solicitudes automáticamente.

Se exige una respuesta HTTP 200 de tipo SVG, con un máximo de 1 MiB. El backend
valida la estructura y rechaza scripts, eventos, entidades XML y recursos externos.
La imagen conserva las coordenadas originales mediante `viewBox` y utiliza el
tamaño configurado para su presentación. Los registros de error guardan únicamente
el tipo de fallo, sin copiar el contenido remoto ni el identificador enviado.

## Comprobación de conexión

Desde `Aplicación`, con Docker en ejecución:

```bash
docker compose exec web python manage.py verificar_qr --codigo ACT-9999
```

El comando realiza una solicitud real, informa el tamaño de la imagen y su hash
SHA-256. No crea activos ni registros QR. Para guardar el resultado dentro del
contenedor, agregar `--salida /tmp/qr-verificado.svg`; el archivo debe ser nuevo.
También puede ejecutarse desde `siget_web` con `python manage.py verificar_qr`
y los mismos argumentos.

## Pruebas

```bash
docker compose exec web python manage.py test activos.tests.test_qr_client activos.tests.test_qr_activos_postgresql --noinput
```

Las pruebas habituales simulan las respuestas HTTP y verifican transporte,
validaciones, errores y conservación del activo en PostgreSQL. La comprobación
contra el proveedor se activa por separado:

```bash
docker compose exec -e SIGET_TEST_QR_LIVE=1 web python manage.py test activos.tests.test_qr_client.QRServerLiveTests --noinput
```

[APIs externas](../README.md) · [Configuración](../../../configuracion.md)
