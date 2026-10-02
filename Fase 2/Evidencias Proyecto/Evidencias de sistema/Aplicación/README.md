# SIGET — Aplicación

Este directorio contiene el código fuente y la configuración de ejecución de la solución SIGET (Sistema Integral de Gestión de Equipos y Soporte Tecnológico), proyecto Capstone de Ingeniería Informática de Duoc UC.

## Arquitectura de la Solución

SIGET posee una arquitectura dual modular respaldada por un núcleo de servicios centralizado:

1. **Plataforma Web (Django 5.2)**:
   - Portal de autoservicio orientado exclusivamente al **Usuario solicitante**.
   - Permite la consulta de equipos asignados, registro y seguimiento de solicitudes, y tickets de soporte.
   - Aplica autorización de canal mediante RBAC en PostgreSQL: usuarios sin el rol oficial `Usuario solicitante` reciben respuesta HTTP 403 controlada (*Portal no disponible*).

2. **Aplicación de Escritorio (PySide6)**:
   - Consola operativa y administrativa orientada al **Técnico de soporte** y al **Administrador del sistema** (gestión de inventario, activos, asignaciones, órdenes de trabajo, resolución de tickets y administración RBAC).
   - Planificada para un sprint posterior (no implementada en esta etapa).

3. **Backend Central (Django / Django REST Framework + PostgreSQL 17)**:
   - Concentra las reglas de negocio, persistencia relacional, integridad referencial y el núcleo de autorización **RBAC** transversal para todos los canales.
   - Integración federada con **Auth0** para autenticación delegada OpenID Connect / OAuth 2.0 y recuperación de credenciales.

---

## Estado Actual del Desarrollo

- **Plataforma Web de Autoservicio**: Interfaz del Usuario solicitante, con navegación institucional, indicadores neutrales y secciones provisionales.
- **Autenticación Externa (SSO / Auth0 - E1-H1)**: Flujo Authorization Code Grant / OpenID Connect con vinculación local segura (`/auth/login/`, `/auth/callback/`, `/auth/logout/`).
- **Recuperación de Acceso Institucional (E1-H2)**: Restablecimiento de contraseña delegado a Auth0 mediante endpoint institucional seguro y mitigación de enumeración de cuentas (`/auth/recover/`).
- **Núcleo Backend RBAC (E1-H3)**:
  - Modelos relacionales oficiales (`Usuario`, `Rol`, `Permiso`, `UsuarioRol`, `RolPermiso` con `managed=False` mapeados a `init_siget_bd.sql`).
  - Catálogo de tres roles canónicos: `Usuario solicitante`, `Técnico de soporte` y `Administrador del sistema`.
  - Capa de servicios para resolución de roles, cálculo de permisos efectivos y decoradores de autorización backend (`@requiere_administrador`, `@requiere_permiso`).
  - Autorización estricta basada en PostgreSQL que ignora manipulaciones manuales en sesión (`session["roles"]`), garantizando la prevención de escalada de privilegios.
- **Módulos en Preparación (`activos` y `asignaciones`)**: Aplicaciones Django inicializadas como base estructural para la gestión de activos e inventario en sprints posteriores.
- **Entorno Containerizado**: Configuración completa con Docker Compose para desarrollo local reproducible.

---

## Estructura del Directorio

```text
Aplicación/
├── .env.example              # Plantilla de variables de entorno (Django, PostgreSQL, Auth0)
├── docker-compose.yml        # Orquestación de servicios (web y postgres)
├── README.md                 # Documentación técnica de la aplicación
└── siget_web/                # Proyecto Django
    ├── Dockerfile            # Imagen de Django basada en Python 3.12-slim
    ├── manage.py             # Utilidad de administración de Django
    ├── requirements.txt      # Dependencias del proyecto Python
    ├── pyrightconfig.json    # Configuración de análisis estático
    ├── siget/                # Configuración principal del proyecto (settings, urls, wsgi, asgi)
    ├── static/               # Archivos estáticos globales
    │   ├── css/siget.css     # Hoja de estilos con identidad visual corporativa SIGET
    │   └── img/logo_SIGET.png
    ├── templates/            # Plantillas HTML globales
    ├── usuarios/             # Módulo de autenticación, portal de autoservicio y RBAC
    │   ├── forms.py          # Formulario institucional de recuperación de acceso (E1-H2)
    │   ├── models.py         # Modelos relacionales RBAC (Usuario, Rol, Permiso, UsuarioRol, RolPermiso)
    │   ├── services.py       # Núcleo de servicios backend (Auth0, vinculación, lógica RBAC y autorización)
    │   ├── views.py          # Vistas de autenticación institucional y portal de autoservicio
    │   ├── urls.py           # Rutas Web de autenticación (/auth/*)
    │   ├── templates/        # Plantillas HTML del portal Web (inicio, login, recover, error, portal_no_disponible)
    │   └── tests/            # Suite automatizada de pruebas unitarias, servicios, vistas y seguridad
    ├── activos/              # Estructura base para gestión de inventario y equipos (sprint posterior)
    └── asignaciones/         # Estructura base para control de asignaciones (sprint posterior)
```

---

## Requisitos

Para ejecutar el entorno se requiere:

- [Docker Engine](https://docs.docker.com/engine/)
- [Docker Compose v2](https://docs.docker.com/compose/)

> No es necesario instalar PostgreSQL ni las dependencias de Python directamente en el sistema anfitrión si se ejecuta la aplicación mediante Docker.

---

## Configuración de Variables de Entorno

Crear el archivo `.env` a partir de la plantilla `.env.example`:

```bash
cp .env.example .env
```

El archivo `.env` define los parámetros esenciales agrupados en:

1. **Django**:
   - `DJANGO_SECRET_KEY`: Clave secreta para criptografía y firmas de Django.
   - `DJANGO_DEBUG`: Modo depuración (`True` en entorno de desarrollo).
   - `DJANGO_ALLOWED_HOSTS`: Hosts y dominios autorizados (`127.0.0.1,localhost`).

2. **Base de Datos (PostgreSQL)**:
   - `POSTGRES_DB`: Nombre de la base de datos (`siget_db`).
   - `POSTGRES_USER`: Usuario administrador (`siget_dev`).
   - `POSTGRES_PASSWORD`: Contraseña del usuario.
   - `POSTGRES_HOST`: Host del servicio (`postgres` dentro de Docker, `127.0.0.1` en local).
   - `POSTGRES_PORT`: Puerto de conexión (`5432`).

3. **Proveedor de Identidad (Auth0)**:
   - `AUTH0_DOMAIN`: Dominio del tenant de Auth0.
   - `AUTH0_CLIENT_ID`: Identificador de la aplicación cliente en Auth0.
   - `AUTH0_CLIENT_SECRET`: Clave secreta para el intercambio de tokens OIDC.
   - `AUTH0_DB_CONNECTION`: Conexión de base de datos en Auth0 para cambio de contraseña.

> El archivo `.env` contiene credenciales locales y no debe ser versionado en Git.

---

## Levantar el Entorno

Desde el directorio `Aplicación/`, ejecutar:

```bash
docker compose up -d --build
```

Verificar el estado de los servicios:

```bash
docker compose ps
```

La Plataforma Web estará disponible en:

```text
http://127.0.0.1:8000/
```

---

## Rutas y Endpoints Principales

| Ruta | Descripción | Acceso |
| :--- | :--- | :--- |
| `/` | Portal de autoservicio si cuenta con rol `Usuario solicitante`, o pantalla de inicio de sesión si no hay sesión | Público / Solicitante |
| `/auth/login/` | Inicia la redirección OAuth 2.0 / OIDC hacia Auth0 | Público |
| `/auth/callback/` | Callback de Auth0 para intercambio de tokens y vinculación de sesión SIGET | Auth0 |
| `/auth/logout/` | Cierre de sesión local en SIGET y redirección de desconexión en Auth0 | Autenticado |
| `/auth/recover/` | Solicitud de recuperación de contraseña institucional (E1-H2) | Público |
| `/admin/` | Panel técnico de administración nativo de Django | Superusuario Django |

> **Nota arquitectónica:** La gestión visual administrativa de usuarios, roles y permisos corresponde a la futura Aplicación de Escritorio PySide6. La plataforma Web opera exclusivamente como portal de autoservicio del Usuario solicitante.

---

## Pruebas Automatizadas

El proyecto incluye pruebas unitarias, de integración y de seguridad que validan la autenticación federada, recuperación de acceso, autorización de canal del portal de autoservicio, servicios del núcleo RBAC y prevención de escalada de privilegios.

Para ejecutar la suite completa de pruebas:

```bash
docker compose exec web python manage.py test usuarios -v 2
```

O en un entorno virtual local activado:

```bash
python manage.py test usuarios -v 2
```

---

## Verificación y Migraciones de Django

Ejecutar las comprobaciones internas del proyecto:

```bash
docker compose exec web python manage.py check
```

Ejecutar las migraciones de Django (para tablas internas de administración y sesiones):

```bash
docker compose exec web python manage.py migrate
```

Consultar el estado de las migraciones:

```bash
docker compose exec web python manage.py showmigrations
```

---

## Base de Datos PostgreSQL

PostgreSQL se ejecuta dentro del entorno Docker y es consumido por Django mediante la red interna de Docker Compose.

Para acceder directamente a la consola de base de datos (`psql`):

```bash
docker compose exec postgres psql -U siget_dev -d siget_db
```

El esquema inicial y los datos de prueba de SIGET se cargan desde:

```text
../Base de datos/init_siget_bd.sql
```

El script de inicialización se ejecuta automáticamente cuando PostgreSQL inicializa un volumen de datos vacío.

---

## Detener el Entorno

Detener los servicios preservando los datos:

```bash
docker compose down
```

Para volver a levantarlo:

```bash
docker compose up -d
```

---

## Reinicializar Completamente la Base de Datos

Para eliminar los contenedores y el volumen persistente de PostgreSQL:

```bash
docker compose down -v
```

Luego reconstruir el entorno:

```bash
docker compose up -d --build
```

> **Advertencia:** Este procedimiento elimina todos los datos almacenados en la base de datos de desarrollo y vuelve a ejecutar el script de inicialización `init_siget_bd.sql`.

---

## Logs

Logs de Django:

```bash
docker compose logs -f web
```

Logs de PostgreSQL:

```bash
docker compose logs -f postgres
```

Logs de todos los servicios:

```bash
docker compose logs -f
```

---

## Tecnologías Principales

- [Python 3.12](https://docs.python.org/3.12/)
- [Django 5.2](https://docs.djangoproject.com/en/5.2/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [PostgreSQL 17](https://www.postgresql.org/docs/17/index.html)
- [Psycopg 3](https://www.psycopg.org/)
- [Authlib](https://docs.authlib.org/) (Cliente OAuth 2.0 / OpenID Connect)
- [Auth0](https://auth0.com/) (Proveedor de Identidad Federado)
- [Requests](https://requests.readthedocs.io/) (Cliente HTTP para API Auth0)
- [django-environ](https://pypi.org/project/django-environ/)
- [Docker](https://www.docker.com/) & [Docker Compose](https://docs.docker.com/compose/)