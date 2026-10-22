# Correo transaccional con Resend

SIGET registra las notificaciones en PostgreSQL y utiliza el servicio Docker `correo` para enviarlas mediante la API REST de Resend. El proceso revisa los avisos y los recordatorios de devolución cada 60 segundos.

## Configuración

Verificar un dominio de envío en Resend y crear una clave con permiso **Sending access** restringida a ese dominio. Configurar el archivo `.env` de la aplicación:

```dotenv
RESEND_API_KEY=REEMPLAZAR_CON_TU_API_KEY_DE_RESEND
RESEND_FROM_EMAIL="SIGET <notificaciones@example.org>"
RESEND_TIMEOUT_SECONDS=10
RESEND_MAX_ATTEMPTS=5
RESEND_RETRY_SECONDS=60
```

Reemplazar el remitente de ejemplo por una dirección del dominio verificado. La clave se utiliza únicamente en el backend y no debe incorporarse al repositorio.

`SIGET_PUBLIC_URL` define la dirección del portal incluida en los enlaces de los mensajes. El dominio de envío y la dirección de la aplicación se configuran de forma independiente.

## Inicio

Para una instalación nueva:

```bash
docker compose up -d --build
```

Para actualizar una instalación que ya contiene datos:

```bash
docker compose build web
docker compose up -d postgres
docker compose run --rm --no-deps web python manage.py preparar_notificaciones
docker compose up -d web correo
```

`preparar_notificaciones` amplía la tabla de notificaciones de forma aditiva. Conserva los registros existentes y puede ejecutarse más de una vez. El archivo de inicialización de la base contiene instrucciones de borrado y se utiliza solamente al crear una base nueva.

## Funcionamiento

Las decisiones de aprobación o rechazo generan un correo al solicitante. El proceso programado genera recordatorios para asignaciones activas cuya devolución prevista está dentro de las próximas 24 horas. Antes de enviar un recordatorio, comprueba nuevamente la vigencia de la asignación y su fecha.

Los avisos se guardan junto con el evento de negocio y se despachan después de confirmar la transacción. Los errores temporales se registran y permiten reintentos con espera creciente, hasta el límite configurado. El control de eventos e idempotencia evita envíos duplicados.

Los enlaces de solicitudes y tickets abren la vista de detalle del registro, donde el solicitante puede consultar su estado actual.

El estado `ENVIADA` indica que Resend aceptó el mensaje. El identificador del proveedor permite consultar su entrega en el panel de Resend.

## Operación

Consultar los registros del servicio:

```bash
docker compose logs --tail=50 correo
```

Ejecutar manualmente un ciclo de generación y envío:

```bash
docker compose exec web python manage.py procesar_notificaciones
```

Este comando despacha los avisos pendientes. Para reintentar una notificación después de corregir su configuración:

```bash
docker compose exec web python manage.py reintentar_correo ID_NOTIFICACION
```

El reintento conserva el contenido, el contador de intentos y la clave de idempotencia. Si se alcanza el límite o transcurren 23 horas desde el primer intento, se requiere revisar el resultado en Resend antes de realizar un nuevo envío.

## Registro de eventos desde el backend

Para notificar una actualización de ticket, invocar el servicio dentro de la transacción que guarda la atención y su evento de auditoría:

```python
from notificaciones.services import notificar_actualizacion_ticket

notificar_actualizacion_ticket(
    ticket,
    id_evento=evento.pk,
    detalle=detalle_guardado,
)
```

El identificador debe corresponder al evento persistido y mantenerse estable al repetir la misma operación. La función registra el aviso; el servicio de correo realiza el envío.

## Pruebas

Enviar un mensaje de prueba a un destinatario autorizado:

```bash
docker compose run --rm --no-deps web python manage.py probar_correo --destinatario usuario@example.org
```

Ejecutar las pruebas automáticas del módulo:

```bash
docker compose exec -e POSTGRES_TEST_DB=test_siget_correo web python manage.py test notificaciones --noinput
```

Las pruebas utilizan PostgreSQL y simulan las respuestas de Resend, sin enviar correos reales.

[API de envío de Resend](https://resend.com/docs/api-reference/emails/send-email) · [Idempotencia](https://resend.com/docs/dashboard/emails/idempotency-keys) · [APIs externas](../README.md)
