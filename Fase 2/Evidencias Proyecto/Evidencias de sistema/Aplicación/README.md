# SIGET — Aplicación

Este directorio contiene el código fuente, la configuración de ejecución y la documentación técnica de la solución **SIGET** (Sistema Integral de Gestión de Equipos y Soporte Tecnológico), proyecto Capstone de la carrera de Ingeniería en Informática de Duoc UC.

---

## Arquitectura de la Solución

SIGET implementa una arquitectura modular con múltiples canales de acceso soportados por un núcleo de servicios centralizado:

1. **Plataforma Web (Django 5.2)**:
   - Portal de autoservicio orientado exclusivamente al **Usuario solicitante**.
   - Permite la consulta de catálogo de equipos, registro y seguimiento de solicitudes de asignación y tickets de soporte técnico.
   - Aplica control de acceso de canal mediante RBAC en PostgreSQL: usuarios sin el rol oficial `Usuario solicitante` reciben respuesta HTTP 403 controlada (*Portal no disponible*).

2. **Aplicación de Escritorio (PySide6)**:
   - Consola operativa y administrativa orientada al **Técnico de soporte** y al **Administrador del sistema** (gestión de inventario de activos TI, asignaciones, órdenes de trabajo, atención de tickets y administración RBAC).
   - Consume directamente las APIs REST del backend central mediante autenticación de usuario.
   - Planificada para una etapa posterior de desarrollo.

3. **Backend Central (Django 5.2 / Django REST Framework + PostgreSQL 17)**:
   - Concentra las reglas de negocio, integridad referencial relacional (modelo de 34 tablas) y el motor de autorización **RBAC** transversal para todos los canales.
   - Provee endpoints REST para la futura consola PySide6 (`/api/usuarios/*`, `/api/activos/*`).
   - Integración federada con **Auth0** para autenticación delegada OpenID Connect / OAuth 2.0 y aprovisionamiento administrativo mediante la Management API.

---

## Estado Actual del Desarrollo

El backend y la plataforma Web cuentan actualmente con las siguientes capacidades implementadas y verificadas:

### Autenticación y Recuperación de Acceso
- **Inicio de Sesión Federado (E1-H1)**: Flujo Authorization Code Grant con OpenID Connect mediante Authlib (`/auth/login/`, `/auth/callback/`, `/auth/logout/`), con vinculación local segura a la identidad en PostgreSQL y control de estado activo.
- **Recuperación Institucional de Acceso (E1-H2)**: Restablecimiento de contraseña delegado a Auth0 (`/auth/recover/`) mediante la Authentication API (`POST /dbconnections/change_password`), con mitigación de enumeración de cuentas.

### Aprovisionamiento y Gestión RBAC (E1-H3 Backend)
- **Aprovisionamiento Administrativo (`POST /api/usuarios/aprovisionar/`)**:
  - Validación de campos obligatorios, formato de correo y validación matemática de RUT chileno (módulo 11).
  - Detección previa de duplicados en PostgreSQL.
  - Creación de identidad externa en Auth0 mediante la Management API (`POST /api/v2/users`) con credencial técnica transitoria y marca de invitación pendiente en metadatos.
  - Persistencia atómica de `Usuario` y rol inicial canónico en `UsuarioRol` dentro de PostgreSQL.
  - **Operación Compensatoria Defensiva**: Si la persistencia en PostgreSQL falla tras crear la cuenta en Auth0, se elimina automáticamente la cuenta externa (`DELETE /api/v2/users/{id}`) para garantizar consistencia distribuida.
  - **Invitación de Primer Acceso**: Disparo automático del flujo de configuración de contraseña institucional al correo del usuario recién creado.
  - Registro de auditoría trazable en `bitacora_auditoria` con usuario ejecutor, acción, entidad afectada e IP de origen.
- **APIs REST de Consulta y Gestión RBAC**:
  - Consulta general de usuarios y roles asignados (`GET /api/usuarios/`).
  - Consulta de detalle de accesos y permisos efectivos consolidados (`GET /api/usuarios/<pk>/acceso/`).
  - Asignación y reemplazo de colección de roles (`POST /api/usuarios/<pk>/roles/`).
  - Catálogo de roles del sistema (`GET /api/usuarios/roles/`).
  - Gestión de permisos por rol (`POST` y `DELETE /api/usuarios/roles/<pk>/permisos/`).
- **Seguridad RBAC**:
  - Autorización autoritativa resuelta en PostgreSQL (`Usuario -> UsuarioRol -> Rol -> RolPermiso -> Permiso`). No existen permisos directos asignados a usuarios.
  - Prevención de escalada de privilegios: las comprobaciones ignoran modificaciones manuales en la sesión (`session["roles"]`), validando siempre contra la base de datos.

### Gestión de Activos TI (E2-H4 / E2-H5 Backend)
- **Registrar Activo TI (E2-H4)**:
  - Endpoint `POST /api/activos/` protegido con RBAC, exclusivo para el **Administrador del sistema**.
  - Validación de pertenencia a catálogos oficiales (`modelo_activo`, `ubicacion`, `estado_activo`).
  - Validación de unicidad de número de serie y valor de adquisición no negativo.
- **Modificar Activo TI (E2-H5)**:
  - Endpoints `GET`, `PUT` y `PATCH /api/activos/<pk>/` protegidos con RBAC para el **Administrador del sistema**.
  - Protección de campos inmutables (`codigo_inventario`, `id_activo`) que impiden su alteración en peticiones de edición.
  - Actualización atómica de atributos operativos con validación de serie no duplicada frente a otros activos.
- **Consulta de Activos y Catálogos**:
  - `GET /api/activos/` y `GET /api/activos/catalogos/` habilitados para **Técnico de soporte** y **Administrador del sistema**.

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
    ├── pyrightconfig.json    # Configuración de análisis estático de tipos
    ├── siget/                # Configuración principal del proyecto (settings, urls, wsgi, asgi)
    ├── static/               # Archivos estáticos globales (CSS corporativo, logos)
    ├── templates/            # Plantillas HTML globales
    ├── usuarios/             # Módulo de autenticación, portal de autoservicio y RBAC
    │   ├── api_urls.py       # Enrutamiento de endpoints REST administrativos (/api/usuarios/*)
    │   ├── api_views.py      # Vistas API de aprovisionamiento y administración RBAC
    │   ├── forms.py          # Formulario institucional de recuperación de acceso (E1-H2)
    │   ├── models.py         # Modelos relacionales RBAC (Usuario, Rol, Permiso, UsuarioRol, RolPermiso)
    │   ├── permissions.py    # Clases de permisos DRF (PuedeAdministrarUsuarios)
    │   ├── serializers.py    # Serializadores DRF de usuarios, roles y permisos
    │   ├── services.py       # Núcleo de servicios (Auth0 OIDC, Management API, lógica RBAC, auditoría)
    │   ├── views.py          # Vistas de autenticación institucional y portal de autoservicio
    │   ├── urls.py           # Rutas Web de autenticación (/auth/*)
    │   ├── templates/        # Plantillas HTML del portal Web (inicio, recover, portal_no_disponible)
    │   └── tests/            # Suite automatizada (E1-H1, E1-H2, E1-H3 servicios, API, seguridad y rutas)
    ├── activos/              # Módulo de gestión de inventario y activos TI (E2-H4, E2-H5)
    │   ├── models.py         # Mapeo relacional de activos, modelos, marcas, estados y ubicaciones
    │   ├── permissions.py    # Clases de permisos DRF (PuedeAdministrarActivos, PuedeConsultarActivos)
    │   ├── serializers.py    # Serializadores DRF de registro, modificación y catálogos de activos
    │   ├── services.py       # Servicios de lógica de negocio y validación de activos
    │   ├── urls.py           # Enrutamiento de endpoints REST de inventario (/api/activos/*)
    │   ├── views.py          # Vistas API para listar, registrar, consultar y modificar activos
    │   └── tests/            # Suite automatizada para E2-H4 y E2-H5
    └── asignaciones/         # Estructura base para control de asignaciones (etapa posterior)
```

---

## Requisitos del Sistema

- [Docker Engine](https://docs.docker.com/engine/).
- [Docker Compose v2](https://docs.docker.com/compose/).
- Opcional para desarrollo local sin Docker: Python 3.12+ y PostgreSQL 17 client.

---

## Configuración de Variables de Entorno

Crear el archivo `.env` en la raíz de `Aplicación/` a partir de la plantilla `.env.example`:

```bash
cp .env.example .env
```

Las variables requeridas están agrupadas según su responsabilidad:

### 1. Django
- `DJANGO_SECRET_KEY`: Clave secreta criptográfica de Django.
- `DJANGO_DEBUG`: Modo depuración (`True` en desarrollo, `False` en producción).
- `DJANGO_ALLOWED_HOSTS`: Dominios y direcciones autorizadas (separados por coma, ej. `127.0.0.1,localhost`).

### 2. Base de Datos (PostgreSQL)
- `POSTGRES_DB`: Nombre de la base de datos relacional (ej. `siget_db`).
- `POSTGRES_USER`: Usuario de la base de datos (ej. `siget_dev`).
- `POSTGRES_PASSWORD`: Contraseña del usuario en PostgreSQL.
- `POSTGRES_HOST`: Dirección del servidor (`postgres` dentro de la red Docker, o `127.0.0.1` en desarrollo local nativo).
- `POSTGRES_PORT`: Puerto de conexión a PostgreSQL (por defecto `5432`).

### 3. Proveedor de Identidad Auth0 — Autenticación Web (OIDC / Login)
- `AUTH0_DOMAIN`: Dominio del tenant de Auth0 (ej. `midominio.auth0.com`).
- `AUTH0_CLIENT_ID`: Identificador de cliente de la aplicación Web regular en Auth0.
- `AUTH0_CLIENT_SECRET`: Secreto de cliente para el intercambio de tokens de sesión OIDC.

### 4. Proveedor de Identidad Auth0 — Aprovisionamiento y Management API (E1-H3)
- `AUTH0_DB_CONNECTION`: Nombre de la Database Connection configurada en el tenant de Auth0 donde residen las identidades de SIGET (ejemplo habitual: `Username-Password-Authentication`). Verifique el nombre exacto en su propio tenant.
- `AUTH0_MGMT_CLIENT_ID`: Identificador de cliente de la aplicación Machine-to-Machine autorizada en la Management API.
- `AUTH0_MGMT_CLIENT_SECRET`: Secreto de cliente de la aplicación Machine-to-Machine. **Dato confidencial**: nunca debe publicarse en repositorios ni compartirse.
- `AUTH0_MGMT_AUDIENCE`: Identificador de audiencia de la Management API en Auth0 (generalmente `https://<AUTH0_DOMAIN>/api/v2/`).

> [!IMPORTANT]
> El archivo `.env` contiene credenciales privadas de conexión y no debe subirse al control de versiones. La plantilla `.env.example` provee únicamente ejemplos y marcadores de posición (*placeholders*).

---

## Configuración de Auth0

### 1. Aplicación Machine-to-Machine (Backend SIGET)
Para permitir que el backend aprovisione identidades y ejecute la compensación distribuida, se requiere una aplicación M2M autorizada contra la **Auth0 Management API**.

Bajo el **principio de mínimo privilegio**, los únicos dos scopes necesarios son:
- `create:users`: Permite al backend registrar la identidad del usuario en la base de datos de Auth0 e inicializar `app_metadata` y `user_metadata` durante el aprovisionamiento administrativo (`POST /api/v2/users`).
- `delete:users`: Utilizado exclusivamente por la transacción compensatoria (`DELETE /api/v2/users/{id}`) para revertir la cuenta externa si ocurre un fallo al persistir en PostgreSQL.

> [!NOTE]
> No autorice scopes adicionales como `read:users`, `update:users` o `create:user_tickets`. El backend de SIGET no los utiliza ni los requiere.

### 2. Conexión de Base de Datos (Database Connection)
La variable `AUTH0_DB_CONNECTION` debe coincidir exactamente con el nombre de la conexión de tipo *Database* de su tenant Auth0. Esta conexión debe estar asociada tanto a la aplicación Web regular como a la aplicación M2M.

### 3. Flujo de Contraseña Inicial e Invitación ("Configure su contraseña")
El aprovisionamiento de un usuario sigue el siguiente flujo de seguridad:
1. El Administrador invoca `POST /api/usuarios/aprovisionar/` indicando nombres, apellidos, correo, RUT y rol oficial.
2. SIGET genera internamente una contraseña técnica transitoria y de alta entropía (`secrets.token_urlsafe(16)`). Esta contraseña existe únicamente en memoria durante la llamada a Auth0; **no se guarda en PostgreSQL, no se devuelve en la API, no se muestra al Administrador ni se registra en logs**.
3. SIGET crea el usuario en Auth0 con `"app_metadata": {"invitacion_pendiente": true}`.
4. SIGET persiste la cuenta en PostgreSQL (`Usuario` y `UsuarioRol`) y registra la auditoría.
5. SIGET solicita el envío del correo de cambio de contraseña mediante el endpoint público de Authentication API (`POST /dbconnections/change_password`).
6. El usuario recibe un correo con el enlace seguro para definir su propia contraseña y acceder por primera vez.

### 4. Personalización del Correo de Invitación y Action Post-Login

#### Personalización de la Plantilla de Correo (Change Password)
Para que el usuario recién creado reciba un mensaje de bienvenida ("Configure su contraseña") en lugar de un mensaje de recuperación tradicional ("Restablezca su contraseña"), la plantilla correspondiente al flujo de *Change Password* en Auth0 puede configurarse con lógica condicional en sintaxis Liquid evaluando el metadato:

```liquid
{% if user.app_metadata.invitacion_pendiente %}
  Bienvenido a SIGET. Configure su contraseña inicial para activar su cuenta.
{% else %}
  Hemos recibido una solicitud para restablecer su contraseña de SIGET.
{% endif %}
```

#### Action Post-Login para Desactivar Invitación
Para asegurar que futuras solicitudes legítimas de "Olvidé mi contraseña" muestren el texto normal de restablecimiento, se debe configurar una **Action** en Auth0 asociada al trigger **Post Login** que desmarque la bandera tras la primera autenticación exitosa:

```javascript
/**
 * Handler ejecutado tras un login exitoso.
 * Desmarca la invitación pendiente para que recuperaciones posteriores utilicen el texto habitual.
 */
exports.onExecutePostLogin = async (event, api) => {
  if (event.user.app_metadata && event.user.app_metadata.invitacion_pendiente) {
    api.user.setAppMetadata("invitacion_pendiente", false);
  }
};
```

> [!TIP]
> La organización de menús y opciones en el Dashboard de Auth0 (tales como *Email Templates*, *Actions*, *Triggers* y *Flows*) puede variar según la versión y plan de su tenant. Consulte la documentación oficial en [auth0.com/docs](https://auth0.com/docs) para ubicar la interfaz vigente de edición de plantillas y despliegue de Actions.

---

## Ejecución del Entorno con Docker

El entorno está preparado para operar con **Docker Compose**.

### Iniciar los Servicios
```bash
docker compose up -d
```

Si se realizaron modificaciones en dependencias (`requirements.txt`) o en el `Dockerfile`, reconstruir la imagen:
```bash
docker compose up -d --build
```

### Consultar Estado de Contenedores
```bash
docker compose ps
```

### Visualizar Logs en Tiempo Real
```bash
# Todos los servicios
docker compose logs -f

# Solo el servicio web (Django)
docker compose logs -f web

# Solo la base de datos (PostgreSQL)
docker compose logs -f postgres
```

### Detener los Servicios
```bash
docker compose down
```

La plataforma Web estará accesible en:
```text
http://127.0.0.1:8000/
```

---

## Catálogo de Rutas y Endpoints

### Rutas Web (Portal de Autoservicio y Autenticación)
| Ruta | Método | Propósito | Acceso Requerido |
| :--- | :--- | :--- | :--- |
| `/` | `GET` | Portal de autoservicio o pantalla inicial | Público / Solicitante |
| `/auth/login/` | `GET` | Redirección OAuth 2.0 / OIDC a Auth0 | Público |
| `/auth/callback/` | `GET` | Recepción de autorización e intercambio de sesión | Auth0 Callback |
| `/auth/logout/` | `GET` | Cierre de sesión local y en Auth0 | Autenticado |
| `/auth/recover/` | `GET`, `POST` | Solicitud institucional de recuperación de contraseña (E1-H2) | Público |
| `/admin/` | `GET`, `POST` | Panel de administración técnico nativo de Django | Superusuario Django |

### Endpoints REST — Gestión de Usuarios y RBAC (E1-H3)
| Endpoint | Método | Propósito | Acceso Requerido |
| :--- | :--- | :--- | :--- |
| `/api/usuarios/` | `GET` | Listar usuarios registrados y sus roles | Administrador del sistema |
| `/api/usuarios/aprovisionar/` | `POST` | Aprovisionar usuario en Auth0 y PostgreSQL con rol inicial | Administrador del sistema |
| `/api/usuarios/<pk>/acceso/` | `GET` | Consultar roles y permisos efectivos consolidados | Administrador del sistema |
| `/api/usuarios/<pk>/roles/` | `POST` | Reemplazar colección de roles de un usuario | Administrador del sistema |
| `/api/usuarios/roles/` | `GET` | Listar catálogo de roles y permisos asociados | Administrador del sistema |
| `/api/usuarios/roles/<pk>/permisos/`| `POST`, `DELETE` | Asociar o desvincular un permiso de un rol | Administrador del sistema |

### Endpoints REST — Gestión de Activos TI (E2-H4 / E2-H5)
| Endpoint | Método | Propósito | Acceso Requerido |
| :--- | :--- | :--- | :--- |
| `/api/activos/` | `GET` | Listar inventario de activos TI | Técnico / Administrador |
| `/api/activos/` | `POST` | Registrar nuevo activo TI (E2-H4) | Administrador del sistema |
| `/api/activos/<pk>/` | `GET` | Consultar ficha detallada de un activo TI | Técnico / Administrador |
| `/api/activos/<pk>/` | `PUT`, `PATCH` | Modificar atributos permitidos de un activo TI (E2-H5) | Administrador del sistema |
| `/api/activos/catalogos/` | `GET` | Consultar catálogos maestros (modelos, estados, ubicaciones) | Técnico / Administrador |

### Guía de Uso: Aprovisionamiento de Usuarios vía Endpoint (`POST /api/usuarios/aprovisionar/`)

El endpoint `/api/usuarios/aprovisionar/` implementa el flujo de aprovisionamiento administrativo controlado (**E1-H3**). Permite registrar una nueva identidad institucional en Auth0 y asociarla atómicamente a su rol oficial en PostgreSQL sin exponer contraseñas locales.

#### 1. Especificación del Endpoint
- **URL**: `http://127.0.0.1:8000/api/usuarios/aprovisionar/`
- **Método**: `POST`
- **Autenticación requerida**: Sesión activa con rol **Administrador del sistema** (`PuedeAdministrarUsuarios`).
- **Encabezados HTTP**:
  - `Content-Type: application/json`
  - `Cookie: sessionid=<SESSION_ID>; csrftoken=<CSRF_TOKEN>` (para clientes con sesión activa)
  - `X-CSRFToken: <CSRF_TOKEN>`

#### 2. Estructura del Payload (JSON)
| Campo | Tipo | Requerido | Descripción y Reglas de Validación |
| :--- | :--- | :--- | :--- |
| `nombres` | String | Sí | Nombres de pila del usuario (máximo 100 caracteres). |
| `apellidos` | String | Sí | Apellidos del usuario (máximo 100 caracteres). |
| `correo` | String | Sí | Correo electrónico institucional único (máximo 150 caracteres, formato RFC válido). |
| `rut` | String | Sí | RUT chileno con formato válido (`12.345.678-5` o `12345678-5`), validado matemáticamente con Módulo 11. |
| `rol` | String | Sí | Rol inicial canónico del usuario. Valores admitidos: `"Usuario solicitante"`, `"Técnico de soporte"`, `"Administrador del sistema"`. |

##### Ejemplo de Payload:
```json
{
  "nombres": "Carlos",
  "apellidos": "Pérez González",
  "correo": "carlos.perez@duocuc.cl",
  "rut": "12.345.678-5",
  "rol": "Usuario solicitante"
}
```

#### 3. Ejemplo de Invocación Programática (Python / Django Shell)
Permite realizar el aprovisionamiento directo invocando la capa de servicios o para pruebas locales:
```python
# Ejecutar en consola interactiva: docker compose exec web python manage.py shell
from usuarios.services import aprovisionar_usuario, ROL_ADMINISTRADOR, ROL_USUARIO_SOLICITANTE
from usuarios.models import Usuario

# 1. Obtener el usuario administrador que autoriza la operación
admin = Usuario.objects.filter(usuarios_asignados__rol__nombre=ROL_ADMINISTRADOR).first()

# 2. Invocar el aprovisionamiento
nuevo_usuario = aprovisionar_usuario(
    admin_usuario=admin,
    datos={
        "nombres": "Carlos",
        "apellidos": "Pérez González",
        "correo": "carlos.perez@duocuc.cl",
        "rut": "12.345.678-5",
        "rol": ROL_USUARIO_SOLICITANTE,
    },
    direccion_ip="127.0.0.1"
)

print(f"Usuario aprovisionado: {nuevo_usuario.correo} (ID: {nuevo_usuario.id_usuario})")
```

#### 4. Respuesta Exitosa (`201 Created`)
El endpoint retorna la ficha de acceso RBAC completa del usuario aprovisionado:
```json
{
  "id_usuario": 1,
  "identificador_externo": "auth0|64f2a1b3c4d5e6f7a8b9c0d1",
  "proveedor_identidad": "auth0",
  "rut": "12345678-5",
  "nombres": "Carlos",
  "apellidos": "Pérez González",
  "correo": "carlos.perez@duocuc.cl",
  "activo": true,
  "fecha_creacion": "2026-10-08T18:00:00Z",
  "roles": [
    {
      "id_rol": 1,
      "nombre": "Usuario solicitante",
      "descripcion": "Usuario final de la institución."
    }
  ],
  "permisos_efectivos": [
    {
      "id_permiso": 1,
      "codigo": "SOLICITUD_CREAR",
      "nombre": "Crear Solicitud",
      "modulo": "SOLICITUDES",
      "descripcion": "Permite registrar solicitudes de asignación de equipos."
    }
  ]
}
```

#### 5. Códigos de Estado y Respuestas de Error
| Código HTTP | Causa | Detalle |
| :--- | :--- | :--- |
| `201 Created` | Éxito | Ficha RBAC del nuevo usuario aprovisionado. |
| `400 Bad Request` | Validación fallida | Campo obligatorio faltante, formato de correo incorrecto, RUT no supera validación de Módulo 11 o el rol no es válido. |
| `403 Forbidden` | Acceso no autorizado | Petición sin sesión activa o el usuario no posee el rol `Administrador del sistema`. |
| `409 Conflict` | Identidad duplicada | Ya existe un registro con el mismo correo electrónico o RUT en PostgreSQL. |
| `500 Internal Server Error` | Fallo transaccional | Error al persistir en base de datos. Dispara la compensación defensiva en Auth0 (`DELETE /api/v2/users/{id}`). |
| `502 Bad Gateway` | Fallo de integración | Error al comunicarse con la Management API de Auth0. |

---

### Bootstrap Inicial del Administrador

Para resolver el problema de inicialización en una instalación completamente nueva de SIGET donde aún no existe ningún usuario con rol `Administrador del sistema` en PostgreSQL, se provee el comando de gestión Django `primer_admin`:

```bash
# Ejecución en contenedor Docker
docker compose exec web python manage.py primer_admin \
  --email admin@ejemplo.cl \
  --rut 12.345.678-9 \
  --nombres Administrador \
  --apellidos "del Sistema"

# O en entorno local con virtualenv activado
python manage.py primer_admin \
  --email admin@ejemplo.cl \
  --rut 12.345.678-9
```

#### Consideraciones y Reglas de Seguridad
- **Uso Exclusivo de Bootstrap:** Se utiliza **únicamente** cuando una instalación nueva no posee ningún Administrador. Si ya existe al menos un Administrador en la base de datos, el comando aborta inmediatamente con un mensaje de protección.
- **Gestión Regular de Usuarios (E1-H3):** El resto de usuarios (técnicos, solicitantes y administradores adicionales) debe crearse exclusivamente mediante el servicio y endpoint de aprovisionamiento E1-H3 (`POST /api/usuarios/`).
- **No es Autorregistro Público:** No expone endpoints públicos ni habilita autorregistro.
- **Contraseña Transitoria y Notificación:** No almacena ni imprime contraseñas locales. Crea la identidad en Auth0 con credencial transitoria interna de alta entropía y dispara el flujo de invitación inicial por correo (`POST /dbconnections/change_password`) para que el nuevo Administrador defina su contraseña.

---

## Pruebas Automatizadas y Verificación

La suite de pruebas automatizadas valida la integridad de autenticación, recuperación de acceso, seguridad de canal Web, lógica de autorización RBAC, consistencia transaccional y operaciones de inventario de activos.

Actualmente el proyecto cuenta con **146 pruebas automatizadas** (124 en la aplicación `usuarios` y 22 en la aplicación `activos`), todas aprobadas exitosamente.

### Ejecución en Contenedor Docker
```bash
# Comprobación de consistencia del sistema Django
docker compose exec web python manage.py check

# Ejecutar la suite completa de pruebas
docker compose exec web python manage.py test -v 2

# Ejecutar pruebas del módulo de usuarios y RBAC
docker compose exec web python manage.py test usuarios -v 2

# Ejecutar pruebas del módulo de activos TI
docker compose exec web python manage.py test activos -v 2
```

### Ejecución en Entorno Local (Virtualenv Activado)
```bash
python manage.py check
python manage.py test -v 2
python manage.py test usuarios -v 2
python manage.py test activos -v 2
```

### Análisis Estático de Tipos con Pyright
```bash
pyright
# Resultado actual: 0 errors, 0 warnings, 0 informations
```

---

## Base de Datos e Inicialización

El esquema relacional de 34 tablas y los datos maestros de SIGET se encuentran definidos en:
```text
../Base de datos/init_siget_bd.sql
```

El script incluye:
- Definición de tablas, llaves primarias, llaves foráneas e índices de rendimiento.
- Catálogos maestros: marcas, modelos, categorías, estados operativos, prioridades de tickets, acuerdos de nivel de servicio (SLA) y ubicaciones físicas.
- Configuración canónica de RBAC: roles oficiales (`Usuario solicitante`, `Técnico de soporte`, `Administrador del sistema`), permisos del sistema y matriz de asociaciones `rol_permiso`.
- No incluye usuarios de prueba hardcodeados; el alta de identidades se realiza mediante aprovisionamiento administrativo controlado (E1-H3). Consulte la [Guía de Aprovisionamiento vía Endpoint](#guía-de-uso-aprovisionamiento-de-usuarios-vía-endpoint-post-apiusuariosaprovisionar).

Para conectarse a la consola interactiva de PostgreSQL dentro del contenedor:
```bash
docker compose exec postgres psql -U siget_dev -d siget_db
```

## Consideraciones de Seguridad

1. **Gestión de Secretos**: Los secretos (`DJANGO_SECRET_KEY`, `AUTH0_CLIENT_SECRET`, `AUTH0_MGMT_CLIENT_SECRET`, credenciales de base de datos) se configuran exclusivamente vía variables de entorno en `.env`. El archivo `.env` está excluido de Git mediante `.gitignore`.
2. **Sin Contraseñas en Base de Datos Local**: La tabla `usuario` en PostgreSQL no almacena hashes ni contraseñas. Toda la autenticación está delegada en Auth0, vinculando cuentas mediante el identificador externo `sub`.
3. **Mínimo Privilegio en APIs Externas**: La aplicación Machine-to-Machine cuenta exclusivamente con los permisos `create:users` y `delete:users`. La futura aplicación de escritorio PySide6 consumirá endpoints propios del backend y nunca tendrá acceso al secreto M2M de Auth0.
4. **Autorización RBAC Estricta en Backend**: La pertenencia a roles y los permisos efectivos se calculan contra las tablas relacionales de PostgreSQL en cada petición protegida. Manipulaciones manuales en variables de sesión (`session["roles"]`) son desestimadas de forma automática.
5. **Prevención de Enumeración**: Los formularios y servicios de recuperación de acceso retornan mensajes neutrales y respuestas uniformes independientemente de la existencia previa del correo consultado.

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
- [Docker](https://www.docker.com/) & [Docker Compose v2](https://docs.docker.com/compose/)