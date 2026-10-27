# Uso general y autenticación

La dirección base y las credenciales se preparan en [configuración de la aplicación](../configuracion.md). Las rutas conservan la barra final `/`. Las peticiones a `/api/` reciben y devuelven datos en formato JSON; se recomienda indicar `Accept: application/json` y, al enviar datos, `Content-Type: application/json`.

Para utilizar la API se debe iniciar sesión con Auth0 y contar con una cuenta SIGET activa. Los perfiles se describen en [usuarios del sistema](../../../../../README.md#usuarios-del-sistema). Los permisos se resuelven mediante roles locales en PostgreSQL.

En las tablas se utilizan los nombres abreviados **Solicitante**, **Técnico** y **Administrador**. Una cuenta puede tener más de un rol. El rol Administrador por sí solo no permite entregar ni recibir equipos.

### Mecanismos de autenticación

SIGET admite dos modalidades de autenticación según el canal de interacción:

1. **Sesión Web (Plataforma Web):** Evaluada mediante cookies de sesión HTTP. Las operaciones que registran, modifican o retiran información requieren además el encabezado `X-CSRFToken` con el valor vigente de la cookie `csrftoken`.
2. **Access Token Bearer (Aplicación de Escritorio PySide6):** El escritorio envía `Authorization: Bearer <access_token>`, obtenido con OAuth 2.0 y PKCE. El backend comprueba la firma del token, su emisor, audiencia y vencimiento mediante las claves públicas de Auth0. Luego consulta la cuenta y sus permisos en PostgreSQL. Esta modalidad no usa cookies de sesión.

Los valores entre llaves, como `{id}`, se reemplazan por el identificador del registro. Los identificadores de los ejemplos son ilustrativos: deben consultarse los registros y catálogos del entorno utilizado. Las fechas simples usan `AAAA-MM-DD`; las fechas con hora usan el formato ISO 8601, por ejemplo `2026-10-20T15:00:00Z`.

Las consultas de listado responden con una lista. Si no hay coincidencias, devuelven `[]` y código `200`. Las rutas de API admiten `OPTIONS` para consultar sus métodos disponibles; las rutas con consulta `GET` también admiten `HEAD`.

En solicitudes de sesión Web, visitar `/` obtiene la cookie CSRF. Su valor debe leerse nuevamente después del login. Las cookies de un navegador no se comparten automáticamente con otro cliente.

Los errores de autenticación se describen en [respuestas y errores](respuestas_y_errores.md). Los controles de interfaz no sustituyen la autorización del backend.

### Acceso desde el escritorio

El cliente inicia un receptor temporal de retorno y abre el navegador del sistema. Auth0 autentica al usuario y devuelve un código; el cliente lo intercambia mediante PKCE por un access token para SIGET. Luego consulta [la identidad actual](acceso_y_usuarios/identidad_actual.md) y permite el ingreso a quienes tengan acceso de Técnico o Administrador. Los parámetros del proveedor se detallan en [autorizar acceso](externas/auth0/autorizar.md) y [obtener tokens](externas/auth0/token.md).

El comportamiento del cierre local y del proveedor se documenta en [cerrar sesión del proveedor](externas/auth0/cerrar_sesion.md).

[Índice general](README.md)
