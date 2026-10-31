# Notificaciones por correo con Resend

SIGET utiliza Resend para enviar avisos y recordatorios. Los mensajes se guardan
en PostgreSQL y el servicio Docker `correo` los procesa al recibir un aviso nuevo.
También revisa los pendientes cada 60 segundos.

## Configuración

Verificar un dominio en Resend y crear una clave **Sending access** restringida
a ese dominio. Completar `.env`:

```dotenv
RESEND_API_KEY=REEMPLAZAR_CON_TU_API_KEY_DE_RESEND
RESEND_FROM_EMAIL="SIGET <notificaciones@example.org>"
RESEND_TIMEOUT_SECONDS=10
RESEND_MAX_ATTEMPTS=5
RESEND_RETRY_SECONDS=60
```

El remitente debe pertenecer al dominio verificado. La clave permanece en el
backend y no se incorpora al repositorio. `SIGET_PUBLIC_URL` define la dirección
del portal que se incluye en los enlaces; puede usar un dominio distinto del remitente.

## Funcionamiento

| Evento | Canal |
|---|---|
| Aprobación o rechazo de solicitudes y actualizaciones de tickets | Portal y correo. |
| Entregas y devoluciones | Portal. |
| Recordatorio de devolución dentro de las próximas 24 horas | Correo. |
| Descarte de un equipo en el cierre técnico | Correo a administradores activos. |

El envío comienza después de guardar la operación y no bloquea la respuesta de
la aplicación. Los fallos temporales se reintentan. Reiniciar el servicio recupera
los avisos pendientes. Marcar un aviso como leído no cambia su envío por correo.

El estado `ENVIADA` indica que Resend aceptó el mensaje; su entrega se puede
consultar en el panel del proveedor. Los enlaces abren el detalle del registro
en SIGET, con el acceso correspondiente.

## Comandos

```bash
# Iniciar los servicios
docker compose up -d --build

# Revisar registros
docker compose logs --tail=50 correo

# Procesar un ciclo de pendientes
docker compose exec web python manage.py procesar_notificaciones

# Reintentar un aviso después de corregir su configuración
docker compose exec web python manage.py reintentar_correo ID_NOTIFICACION

# Enviar una prueba real a un destinatario autorizado
docker compose run --rm --no-deps web python manage.py probar_correo --destinatario usuario@example.org
```

Un reintento conserva la identificación del envío para evitar duplicados. Si se
agotan los intentos o pasan 23 horas desde el primero, revisar el resultado en
Resend antes de volver a enviar.

## Pruebas

```bash
docker compose exec -e POSTGRES_TEST_DB=test_siget_correo web python manage.py test notificaciones --noinput
```

Estas pruebas simulan Resend y no envían correos reales.

[Documentación de Resend](https://resend.com/docs/api-reference/emails/send-email)
· [Centro de avisos](../../acceso_y_usuarios/web/notificaciones.md)
· [APIs externas](../README.md)
