# Configuración de la aplicación

Web, Docker y Escritorio utilizan el archivo `.env` de esta carpeta. La [plantilla .env.example](.env.example) contiene la lista completa de variables y sus valores de ejemplo. Desde `Aplicación`, crear la copia local una sola vez:

```bash
cp .env.example .env
```

Reemplazar los valores de ejemplo antes de ejecutar la aplicación. `.env` contiene secretos y no debe incorporarse al repositorio.

## Django y PostgreSQL

| Variables | Uso |
|---|---|
| `DJANGO_SECRET_KEY` | Clave privada de Django. |
| `DJANGO_DEBUG` | Activa el modo de desarrollo. |
| `DJANGO_ALLOWED_HOSTS` | Hosts admitidos, separados por comas. |
| `SIGET_PUBLIC_URL` | Dirección pública del backend, compartida por Web y Escritorio. |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Base de datos y credenciales. |
| `POSTGRES_HOST`, `POSTGRES_PORT` | Conexión desde el proceso Django. Docker Compose establece el servicio `postgres` y su puerto interno; fuera de Docker se usa la conexión del entorno local. |

## Identidad y clientes Auth0

| Variables | Uso |
|---|---|
| `AUTH0_DOMAIN` | Dominio del proveedor, sin `https://`, compartido por ambos clientes. |
| `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET` | Credenciales de la aplicación Web. |
| `AUTH0_DB_CONNECTION` | Conexión de usuarios utilizada en recuperación y aprovisionamiento. |
| `AUTH0_MGMT_CLIENT_ID`, `AUTH0_MGMT_CLIENT_SECRET` | Credenciales del backend para administrar identidades. Si no se definen, Django utiliza las credenciales Web. |
| `AUTH0_MGMT_AUDIENCE` | Destino de los tokens administrativos: `https://{AUTH0_DOMAIN}/api/v2/`. Si se omite, Django lo deriva del dominio. |
| `AUTH0_API_AUDIENCE` | Identifier de la API propia registrada en Auth0. Es un identificador; no necesita coincidir con la dirección del backend ni resolver como sitio Web. |
| `AUTH0_API_ALLOWED_CLIENT_IDS` | Lista opcional de clientes admitidos por Django mediante el claim `azp`, separada por comas. |
| `AUTH0_DESKTOP_CLIENT_ID` | Identificador público del cliente Native, independiente del cliente Web y sin client secret. |
| `AUTH0_DESKTOP_CALLBACK_PORT` | Puerto del receptor local de autorización del escritorio. |

Las dos audiencias corresponden a servicios diferentes y deben conservarse separadas. El backend utiliza la audiencia de SIGET para validar el acceso a sus APIs; la audiencia de Management API permite administrar identidades en Auth0.

En Auth0, registrar la API propia con firma RS256 y un Identifier idéntico a `AUTH0_API_AUDIENCE`. Registrar el escritorio como aplicación Native, con Authorization Code y PKCE. Su callback predeterminado es `http://127.0.0.1:42813/callback`; si se cambia el puerto, actualizar también la URL autorizada. El retorno Web es `{SIGET_PUBLIC_URL}/auth/callback/`. Las URL de cierre de sesión utilizadas deben estar autorizadas en el cliente correspondiente.

## Tiempos de espera y validación

| Variables | Uso |
|---|---|
| `AUTH0_JWKS_CACHE_SEGUNDOS` | Duración de la caché de claves públicas del backend, en segundos. |
| `AUTH0_TOKEN_LEEWAY` | Tolerancia de reloj al validar tokens, en segundos. |
| `AUTH0_HTTP_TIMEOUT` | Tiempo máximo de las consultas de identidad desde Django, en segundos. |
| `SIGET_HTTP_TIMEOUT` | Tiempo máximo de las consultas HTTP del escritorio, en segundos. |

## Correo transaccional Resend

`RESEND_API_KEY` y `RESEND_FROM_EMAIL` configuran el proveedor y remitente. `RESEND_TIMEOUT_SECONDS` vale 10, `RESEND_MAX_ATTEMPTS` vale 5 y `RESEND_RETRY_SECONDS` vale 60 por defecto. La clave es privada del backend; los clientes no la utilizan. El servicio Docker `correo` genera recordatorios y despacha avisos. Consultar [configuración y uso del servicio de correo](api_docs/externas/resend/README.md).

## Configuración pública del escritorio

El escritorio lee únicamente `SIGET_PUBLIC_URL`, `SIGET_HTTP_TIMEOUT`, `AUTH0_DOMAIN`, `AUTH0_API_AUDIENCE`, `AUTH0_DESKTOP_CLIENT_ID` y `AUTH0_DESKTOP_CALLBACK_PORT`. Las variables del entorno tienen prioridad sobre `.env`; su ubicación se resuelve desde la carpeta de la aplicación, independientemente del directorio de ejecución.

El archivo compartido se utiliza en desarrollo. Para distribuir el escritorio a otro equipo, proporcionar solo estos valores públicos como variables del entorno. Los secretos de Django, PostgreSQL, Web y Management API permanecen en el servidor.

[Volver a ejecución y pruebas](README.md) · [Uso de las APIs](api_docs/uso_general.md)
