# SIGET

## Sistema Integral de Gestión de Equipos y Soporte Tecnológico

**SIGET** es una solución orientada a centralizar la gestión de activos tecnológicos y los procesos de soporte TI de una organización.

El sistema permite administrar el ciclo de vida de los equipos tecnológicos, desde su registro y asignación hasta su devolución, mantenimiento y soporte, integrando además una **Mesa de Ayuda (Service Desk)** para la gestión y seguimiento de incidentes.

Proyecto desarrollado para la asignatura **Capstone de Ingeniería en Informática — Duoc UC**.

---

## Objetivo

Desarrollar una solución que permita centralizar la información relacionada con los activos tecnológicos y los procesos de soporte TI, mejorando su **control, trazabilidad y seguimiento**.

SIGET busca facilitar la interacción entre usuarios solicitantes, técnicos de soporte y administradores mediante una solución centralizada para la gestión de equipamiento y soporte tecnológico.

---

## Usuarios del sistema

| Perfil | Responsabilidad |
|---|---|
| **Usuario solicitante** | Consultar equipos, realizar solicitudes y gestionar tickets de soporte. |
| **Técnico de soporte** | Gestionar asignaciones, devoluciones, tickets, diagnósticos, reparaciones y mantenimiento. |
| **Administrador del sistema** | Administrar activos, usuarios, roles, permisos y procesos administrativos. |

---

## Componentes principales

### Plataforma Web

Orientada principalmente al **Usuario solicitante**.

Permite:

- Iniciar sesión y recuperar acceso.
- Consultar equipos asignados.
- Realizar solicitudes de equipos.
- Consultar el estado de solicitudes.
- Registrar tickets de soporte.
- Consultar información e historial de equipos.
- Revisar notificaciones y datos de perfil.

### Aplicación de Escritorio

Orientada a **Técnicos de soporte** y **Administradores del sistema**.

Contempla:

- Administración de activos tecnológicos.
- Gestión de solicitudes y asignaciones.
- Aprobación y rechazo de solicitudes.
- Registro de entregas y devoluciones.
- Gestión de tickets de soporte.
- Diagnósticos y reparaciones.
- Mantenimientos.
- Administración de usuarios, roles y permisos.
- Trazabilidad, auditoría y reportes.

### Backend / API REST

El backend centraliza las reglas de negocio y permite la comunicación entre los componentes de SIGET.

Está desarrollado con **Python, Django y Django REST Framework** y se encarga de:

- Procesar las operaciones del sistema.
- Aplicar reglas de negocio.
- Gestionar autenticación y autorización.
- Administrar el acceso a datos.
- Exponer servicios REST.
- Registrar operaciones relevantes para auditoría.

### Base de Datos

SIGET utiliza **PostgreSQL** como sistema gestor de base de datos relacional.

El modelo contempla información relacionada con:

- Usuarios, roles y permisos.
- Activos tecnológicos.
- Solicitudes y asignaciones.
- Devoluciones.
- Estados de equipos.
- Tickets y mensajes.
- Reparaciones y mantenimientos.
- Repuestos.
- Notificaciones.
- Auditoría.
- Historial y trazabilidad.

---

## Arquitectura general

```text
                         ┌──────────────────────┐
                         │        Auth0         │
                         │   Autenticación      │
                         └──────────┬───────────┘
                                    │
                                    ▼
┌─────────────────────┐    ┌───────────────────────┐
│   Plataforma Web    │───▶│                       │
│      Django         │    │   Backend Django /    │
└─────────────────────┘    │ Django REST Framework │
                           │                       │
┌─────────────────────┐    │   Lógica de negocio  │
│    Aplicación de    │───▶│   APIs REST / RBAC   │
│ Escritorio PySide6  │    │                       │
└─────────────────────┘    └───────────┬───────────┘
                                       │
                                       ▼
                              ┌─────────────────┐
                              │   PostgreSQL    │
                              │ Base de Datos   │
                              └─────────────────┘
```

La **Plataforma Web** y la **Aplicación de Escritorio** utilizan un backend centralizado que concentra la lógica de negocio, autorización y acceso a los datos.

---

## Módulos principales

- Gestión de usuarios y autenticación.
- Gestión de roles y permisos.
- Gestión de activos tecnológicos.
- Gestión de solicitudes y asignaciones.
- Gestión de devoluciones y trazabilidad.
- Mesa de Ayuda y tickets de soporte.
- Gestión de reparación y mantenimiento.
- Gestión de repuestos e insumos técnicos.
- Notificaciones y seguimiento.
- Auditoría y reportes.
- Integración de APIs y seguridad.

---

## Tecnologías

| Área | Tecnología |
|---|---|
| **Backend** | Python, Django |
| **API REST** | Django REST Framework |
| **Base de datos** | PostgreSQL |
| **Plataforma Web** | Django, HTML5, CSS3, JavaScript |
| **Aplicación de Escritorio** | Python, PySide6 |
| **Autenticación** | Auth0, OAuth 2.0, OpenID Connect |
| **Contenedores** | Docker, Docker Compose |
| **Control de versiones** | Git, GitHub |

---

## Estructura del repositorio

El repositorio organiza las evidencias académicas, documentación técnica y desarrollo del sistema de acuerdo con las distintas fases del proyecto Capstone.

```text
SIGET/
├── Fase 1/
│   ├── Evidencias Grupales/
│   └── Evidencias Individuales/
│
├── Fase 2/
│   ├── Evidencias Grupales/
│   ├── Evidencias Individuales/
│   └── Evidencias Proyecto/
│       │
│       ├── Evidencias de documentación/
│       └── Evidencias de sistema/
│           ├── Aplicación/
│           │   ├── siget_web/
│           │   ├── docker-compose.yml
│           │   └── README.md
│           │
│           └── Base de datos/
│               └── init_siget_bd.sql
│
├── Fase 3/
│   ├── Evidencias Grupales/
│   └── Evidencias Individuales/
│
└── README.md
```

> La estructura anterior es una representación resumida del repositorio. Los archivos específicos de código, pruebas, documentación y evidencias se encuentran organizados dentro de sus respectivas carpetas.

---

## Documentación del proyecto

La documentación principal del proyecto se encuentra en:

```text
Fase 2/
└── Evidencias Proyecto/
    └── Evidencias de documentación/
```

Incluye documentación relacionada con:

- Arquitectura de la solución.
- Casos de uso.
- Historias de usuario.
- Product Backlog.
- Requisitos no funcionales.
- Modelo de datos.
- Mockups.
- Roles y responsabilidades.
- Gestión Scrum.
- Registros de Sprint.

### Arquitectura

Los diagramas y documentación de arquitectura se encuentran en:

```text
Fase 2/Evidencias Proyecto/Evidencias de documentación/Arquitectura/
```

La documentación contempla distintas vistas de la solución:

- Vista de Despliegue.
- Vista de Escenario.
- Vista Física.
- Vista Lógica.
- Vista de Proceso.

---

## Evidencias del sistema

El código fuente y la base de datos utilizados como evidencia del desarrollo se encuentran en:

```text
Fase 2/
└── Evidencias Proyecto/
    └── Evidencias de sistema/
        ├── Aplicación/
        └── Base de datos/
```

### Aplicación

La implementación de la solución se encuentra en:

```text
Fase 2/Evidencias Proyecto/Evidencias de sistema/Aplicación/
```

Incluye:

- Backend Django.
- Plataforma Web.
- APIs REST.
- Módulos funcionales.
- Pruebas automatizadas.
- Configuración Docker.
- Variables de entorno de ejemplo.
- Documentación técnica de ejecución.

La configuración técnica y ejecución de la aplicación se encuentra detallada en:

**[README de la aplicación](Fase%202/Evidencias%20Proyecto/Evidencias%20de%20sistema/Aplicación/README.md)**

### Base de datos

El script de inicialización de PostgreSQL se encuentra en:

```text
Fase 2/Evidencias Proyecto/Evidencias de sistema/Base de datos/init_siget_bd.sql
```

Contiene la estructura relacional y datos necesarios para inicializar la base de datos utilizada por SIGET.

---

## Metodología de trabajo

El proyecto se desarrolla utilizando **Scrum**, organizando el trabajo mediante Sprints e historias de usuario.

La gestión del proyecto contempla:

- Product Backlog.
- Sprint Backlog.
- Historias de usuario.
- Criterios de aceptación.
- Daily Standup.
- Retrospectivas.
- Registro de actividades y horas.
- Control de versiones mediante Git y GitHub.
- Pruebas.
- Documentación.
- Evidencias de desarrollo.

Los registros correspondientes a cada Sprint se almacenan dentro de:

```text
Fase 2/Evidencias Proyecto/Evidencias de documentación/Scrum/
```

---

## Evidencias académicas

El repositorio también mantiene las evidencias requeridas durante las distintas fases del Capstone.

### Fase 1

Contiene:

- Evidencias grupales.
- Evidencias individuales.
- Presentación inicial del proyecto.

### Fase 2

Contiene:

- Evidencias grupales.
- Evidencias individuales.
- Evidencias de documentación.
- Evidencias del sistema implementado.

### Fase 3

Contiene:

- Evidencias grupales.
- Evidencias individuales.

---

**Duoc UC — Escuela de Informática y Telecomunicaciones**  
**Ingeniería en Informática — Capstone**