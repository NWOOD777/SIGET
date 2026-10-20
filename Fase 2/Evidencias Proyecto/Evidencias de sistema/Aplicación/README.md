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

## Ejecutar el escritorio

Con el backend en ejecución y el entorno virtual activo:

```bash
python -m siget_desktop.main
```

El [flujo de autenticación](api_docs/uso_general.md#mecanismos-de-autenticación) y los permisos de cada operación se describen en la documentación de las APIs.

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
