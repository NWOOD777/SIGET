# SIGET — Aplicación

Este directorio contiene la implementación de la aplicación **SIGET**, incluyendo el backend Django, Plataforma Web, APIs REST, configuración Docker y pruebas automatizadas.

Para la descripción general, objetivos y arquitectura global del proyecto, consultar el [README principal](../../../../README.md).

---

## Arquitectura de la aplicación

La aplicación utiliza un backend central desarrollado con **Django 5.2** y **Django REST Framework**, conectado a **PostgreSQL 17**.

Actualmente contempla:

- **Plataforma Web:** canal de autoservicio para el Usuario solicitante.
- **API REST:** servicios de negocio utilizados por los distintos módulos de SIGET.
- **Aplicación de Escritorio:** cliente PySide6 para Técnicos de soporte y Administradores.
- **Auth0:** autenticación mediante OpenID Connect / OAuth 2.0.
- **RBAC:** autorización mediante roles y permisos almacenados en PostgreSQL.

---

## Módulos

El backend está organizado principalmente en:

```text
siget_web/
├── siget/          # Configuración principal de Django
├── usuarios/       # Autenticación, usuarios y RBAC
├── activos/        # Gestión de activos TI
├── asignaciones/   # Solicitudes, asignaciones y devoluciones
├── tickets/        # Mesa de ayuda y tickets
├── templates/      # Plantillas Web
├── static/         # Recursos estáticos
├── manage.py
└── requirements.txt
```

Los módulos implementan servicios relacionados con:

- Autenticación y recuperación de acceso.
- Administración de usuarios, roles y permisos.
- Gestión de activos TI.
- Solicitudes y asignaciones de equipos.
- Entregas y devoluciones.
- Mesa de ayuda y tickets de soporte.
- Auditoría de operaciones.

---

## Requisitos

- Docker Engine.
- Docker Compose v2.

Opcionalmente, para ejecución sin Docker:

- Python 3.12+.
- PostgreSQL 17.

---

## Variables de entorno

Crear el archivo `.env` desde la plantilla incluida:

```bash
cp .env.example .env
```

La configuración incluye variables para:

- Django.
- PostgreSQL.
- Auth0.
- Auth0 Management API.

> `.env` contiene credenciales privadas y no debe incorporarse al repositorio.

La lista completa de variables y ejemplos se encuentra en `.env.example`.

---

## Ejecución con Docker

### Iniciar

```bash
docker compose up -d --build
```

### Consultar estado

```bash
docker compose ps
```

### Logs

```bash
docker compose logs -f
```

### Detener

```bash
docker compose down
```

La Plataforma Web estará disponible en:

```text
http://localhost:8000/
```

---

## API REST

SIGET utiliza Django REST Framework para exponer los servicios necesarios para usuarios, activos, asignaciones, devoluciones y tickets.

---

## Pruebas

Comprobar la configuración de Django:

```bash
docker compose exec web python manage.py check
```

Ejecutar la suite completa:

```bash
docker compose exec web python manage.py test
```

Las pruebas cubren lógica de negocio, permisos, persistencia, APIs e integración entre módulos.

---

## Base de datos

SIGET utiliza PostgreSQL como base de datos relacional.

El esquema e inicialización se encuentran en:

```text
../Base de datos/init_siget_bd.sql
```

La base de datos contiene el modelo relacional, catálogos maestros, configuración RBAC y relaciones utilizadas por los módulos de la aplicación.

---

## Seguridad

La aplicación implementa:

- Autenticación delegada mediante Auth0.
- OAuth 2.0 / OpenID Connect.
- Autorización RBAC en PostgreSQL.
- Variables de entorno para secretos y credenciales.
- Validación de permisos en el backend.
- Auditoría de operaciones relevantes.

Las credenciales de Auth0, PostgreSQL y Django nunca deben incorporarse al repositorio.