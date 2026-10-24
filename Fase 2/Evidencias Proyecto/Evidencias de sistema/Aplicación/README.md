# SIGET — Aplicación

Esta carpeta contiene el backend, el portal Web y el cliente de escritorio. La descripción del proyecto, sus perfiles, tecnologías y arquitectura se encuentran en el [README principal](../../../../README.md).

## Organización del código

```text
Aplicación/
├── siget_web/
│   ├── siget/          # Configuración de Django
│   ├── usuarios/       # Identidad y RBAC
│   ├── activos/        # Inventario
│   ├── asignaciones/   # Solicitudes, entregas y devoluciones
│   ├── notificaciones/ # Centro de avisos en plataforma, correo transaccional y proceso programado
│   ├── tickets/        # Service Desk
│   ├── templates/
│   ├── static/
│   └── manage.py
├── siget_desktop/
│   ├── auth/           # Acceso y sesión del cliente
│   ├── api/            # Consumo del backend compartido
│   ├── ui/             # Ventanas y vistas
│   ├── tests/
│   ├── config.py
│   └── main.py
├── api_docs/            # Contratos por API y endpoint
├── configuracion.md     # Variables y registro de clientes
├── .env.example
├── requirements.txt
└── docker-compose.yml
```

## Preparación

Los comandos de esta guía se ejecutan desde la carpeta `Aplicación`, salvo que se indique otra ubicación.

Se requiere Docker Engine y Docker Compose v2 para levantar el backend y PostgreSQL. El escritorio requiere Python 3.12 o superior y un entorno gráfico local.

Antes de iniciar, completar la [configuración compartida](configuracion.md).

### Dependencias locales

Web y Escritorio utilizan un único `requirements.txt`. Para ejecutar el escritorio y las herramientas de revisión, crear un entorno virtual `.venv` en la raíz de SIGET y activarlo. Desde `Aplicación`, instalar:

```bash
python -m pip install -r requirements.txt
```

La imagen Docker instala estas dependencias durante su construcción.

## Backend y PostgreSQL con Docker

```bash
docker compose up -d --build
```

El portal queda disponible en `http://localhost:8000/`. Para consultar el estado, ver registros y detener los servicios:

```bash
docker compose ps
docker compose logs -f
docker compose down
```

La base se inicializa desde [init_siget_bd.sql](../Base%20de%20datos/init_siget_bd.sql) al crear un volumen vacío. Los datos permanecen en el volumen de PostgreSQL al detener los servicios.

### Configuración inicial de catálogos

La inicialización crea el esquema relacional, roles, permisos y asociaciones RBAC,
estados del sistema, prioridades y políticas SLA. Los catálogos de categorías,
marcas, modelos y ubicaciones comienzan vacíos.

En el escritorio, el Administrador accede a **Activos TI → Administrar catálogos**
para crear, buscar y editar estos registros. Primero se registran las categorías,
marcas y ubicaciones; luego se crean los modelos asociando una marca y una categoría.
Con un modelo y una ubicación disponibles se puede registrar un activo.

El mantenedor también permite eliminar registros sin referencias. Los catálogos
asociados a modelos, activos o solicitudes quedan protegidos. Las operaciones se
registran en la bitácora de auditoría.

Los formularios de registro y modificación de activos incluyen acceso al mantenedor
y actualización de selectores sin perder los datos ingresados. La configuración de
catálogos se realiza desde la aplicación; el arranque no carga datos de ejemplo.
Las instalaciones existentes conservan sus registros en el volumen de PostgreSQL.

## Notificaciones por correo

Para configurar y utilizar el servicio de correo, consultar [configuración y uso de Resend](api_docs/externas/resend/README.md).

## Ejecutar el escritorio

Con el backend en ejecución y las dependencias instaladas, utilizar el launcher correspondiente:

**Linux**, desde una terminal:

```bash
./iniciar_escritorio.sh
```

**Windows**, mediante doble clic en `iniciar_escritorio.bat` o desde una terminal:

```bat
iniciar_escritorio.bat
```

Ambos launchers buscan primero `.venv` en la raíz del repositorio, luego en `Aplicación` y finalmente Python en el sistema. No es necesario activar el entorno encontrado.

Pueden ejecutarse desde otra carpeta usando su ruta completa. Comprueban Python 3.12 o superior y las dependencias principales, y transmiten los argumentos al cliente. Para consultar la versión sin abrir la interfaz:

```bash
./iniciar_escritorio.sh --version
```

En Windows, usar `iniciar_escritorio.bat --version`.

El backend se inicia por separado con Docker Compose. Los launchers no instalan paquetes ni modifican la configuración. Para iniciar manualmente, desde `Aplicación` y con el entorno virtual activo:

```bash
python -m siget_desktop.main
```

El [flujo de autenticación](api_docs/uso_general.md#mecanismos-de-autenticación) y los permisos de cada operación se describen en la documentación de las APIs.

### Sesión del escritorio

Al cerrar la ventana se conserva el token de acceso vigente en el directorio local de datos del usuario que determina el sistema operativo mediante Qt. La caché es privada al usuario y contiene únicamente el token, su vencimiento y la identificación del entorno. No guarda contraseñas, roles ni permisos. Al abrir la aplicación se consulta nuevamente la identidad y el acceso en Django. «Cerrar sesión», la expiración o el rechazo de la cuenta eliminan la caché. Una sesión vencida requiere iniciar sesión nuevamente.


## Pruebas

### Backend

```bash
docker compose exec web python manage.py check
docker compose exec web python manage.py test
```

La suite comprueba reglas de negocio, permisos, persistencia y endpoints sobre PostgreSQL.

### Escritorio

```bash
python -m unittest discover -s siget_desktop/tests -p "test_*.py"
```

Las pruebas gráficas utilizan `QT_QPA_PLATFORM=offscreen` y pueden ejecutarse sin una pantalla interactiva.

### Revisión estática

La función, configuración y comandos de Ruff y Pyright se explican en [Revisión estática de la aplicación](../../../../README.md#revisión-estática-de-la-aplicación).

## Documentación de las APIs

El [índice de APIs](api_docs/README.md) reúne los contratos del backend y de las integraciones externas. Cada endpoint documenta sus métodos, permisos, entradas y respuestas.
