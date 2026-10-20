# SIGET

## Sistema Integral de Gestión de Equipos y Soporte Tecnológico

**SIGET** es una solución orientada a centralizar la gestión de activos tecnológicos y los procesos de soporte TI de una organización.

El sistema permite administrar el ciclo de vida de los equipos tecnológicos, desde su registro y asignación hasta su devolución, mantenimiento y soporte, integrando además una **Mesa de Ayuda (Service Desk)** para la gestión y seguimiento de incidentes.

Proyecto desarrollado para la asignatura **Capstone de Ingeniería en Informática — Duoc UC**.

---

## Usuarios del sistema

| Perfil | Responsabilidad |
|---|---|
| **Usuario solicitante** | Consultar equipos, realizar solicitudes y gestionar tickets de soporte. |
| **Técnico de soporte** | Gestionar asignaciones, devoluciones, tickets, diagnósticos, reparaciones y mantenimiento. |
| **Administrador del sistema** | Administrar activos, usuarios, roles, permisos y procesos administrativos. |

---

## Componentes principales

| Componente | Función |
|---|---|
| Plataforma Web | Autoservicio del Usuario solicitante. |
| Aplicación de Escritorio PySide6 | Operaciones del Técnico de soporte y del Administrador. |
| Backend Django / Django REST Framework | Reglas de negocio, permisos y servicios REST compartidos. |
| PostgreSQL | Persistencia de usuarios, activos, asignaciones, soporte y trazabilidad. |

Los endpoints disponibles y las integraciones pendientes se distinguen en el [alcance de las APIs](Fase%202/Evidencias%20Proyecto/Evidencias%20de%20sistema/Aplicación/api_docs/alcance_y_pendientes.md).

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
│           │   ├── siget_desktop/
│           │   ├── requirements.txt
│           │   ├── api_docs/
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
├── ruff.toml
├── pyrightconfig.json
└── README.md
```

> La estructura anterior es una representación resumida del repositorio. Las carpetas de fases contienen el código y las evidencias académicas. Los archivos `ruff.toml` y `pyrightconfig.json` de la raíz configuran la revisión compartida del backend y del cliente de escritorio, descrita en [Revisión estática de la aplicación](#revisión-estática-de-la-aplicación).

---

## Documentación y aplicación

| Recurso | Ubicación |
|---|---|
| Ejecución, dependencias y pruebas | [README de la aplicación](Fase%202/Evidencias%20Proyecto/Evidencias%20de%20sistema/Aplicación/README.md) |
| Variables de entorno y registro de clientes | [Configuración de la aplicación](Fase%202/Evidencias%20Proyecto/Evidencias%20de%20sistema/Aplicación/configuracion.md) |
| Contratos y endpoints | [Índice de las APIs](Fase%202/Evidencias%20Proyecto/Evidencias%20de%20sistema/Aplicación/api_docs/README.md) |
| Modelo e inicialización de PostgreSQL | [init_siget_bd.sql](Fase%202/Evidencias%20Proyecto/Evidencias%20de%20sistema/Base%20de%20datos/init_siget_bd.sql) |
| Arquitectura y diagramas | [Arquitectura](Fase%202/Evidencias%20Proyecto/Evidencias%20de%20documentación/Arquitectura/) |
| Requisitos, historias, backlog y documentación académica | [Evidencias de documentación](Fase%202/Evidencias%20Proyecto/Evidencias%20de%20documentación/) |
| Registros de trabajo por Sprint | [Scrum](Fase%202/Evidencias%20Proyecto/Evidencias%20de%20documentación/Scrum/) |

### Revisión estática de la aplicación

La aplicación utiliza Ruff y Pyright para revisar el código Python del backend Django/DRF y del cliente de escritorio PySide6. Sus configuraciones se mantienen en la raíz para aplicar los mismos criterios a ambos componentes y facilitar su revisión desde el repositorio completo.

| Archivo | Función |
|---|---|
| [ruff.toml](ruff.toml) | Orden de imports, imports y variables sin usar, nombres indefinidos y errores básicos. Utiliza reglas estables y una configuración moderada. |
| [pyrightconfig.json](pyrightconfig.json) | Análisis básico de tipos, uso de valores opcionales y resolución de imports en el backend y el escritorio, incluidas sus pruebas. |

Los controles consideran Python 3.12 y excluyen las migraciones generadas por Django. Ruff conserva una excepción puntual para el arranque directo del escritorio, que ajusta su ruta antes de importar el paquete. Los imports y las variables sin usar siguen revisándose en ese archivo.

Después de [instalar las dependencias compartidas](Fase%202/Evidencias%20Proyecto/Evidencias%20de%20sistema/Aplicación/README.md#dependencias-locales), ejecutar desde la raíz de SIGET con `.venv` activo:

```bash
ruff check .
pyright
```

Para corregir automáticamente el orden de imports y otros casos seguros se utiliza `ruff check . --fix`. Estas revisiones complementan las pruebas automatizadas de la aplicación.


## Metodología de trabajo

El equipo utiliza Scrum, con historias de usuario, criterios de aceptación, Product Backlog y Sprint Backlog. Las reuniones diarias, retrospectivas y registros de actividades se conservan en la carpeta Scrum enlazada arriba; Git y GitHub mantienen el historial del desarrollo.

## Evidencias académicas

Las carpetas `Fase 1`, `Fase 2` y `Fase 3` organizan las evidencias grupales e individuales de cada etapa. La segunda fase reúne además la documentación y el sistema implementado, según la estructura del repositorio.

**Duoc UC — Escuela de Informática y Telecomunicaciones**  
**Ingeniería en Informática — Capstone**
