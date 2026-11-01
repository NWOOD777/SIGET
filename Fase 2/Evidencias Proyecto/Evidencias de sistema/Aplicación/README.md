# SIGET — Aplicación

Esta carpeta contiene el portal web, el cliente de escritorio, el backend y la
configuración de Docker. La descripción general del proyecto está en el
[README principal](../../../../README.md).

## Preparación

Se requiere Docker con Compose v2 para el backend y PostgreSQL. El escritorio
requiere Python 3.12 o superior y un entorno gráfico.

Los comandos siguientes se ejecutan desde `Aplicación`. Crear el archivo local
de configuración y completar sus valores según la [guía de configuración](configuracion.md):

```bash
cp .env.example .env
```

### Dependencias locales

Para ejecutar el escritorio, crear y activar un entorno virtual `.venv` en la
raíz de SIGET e instalar las dependencias compartidas:

```bash
python -m pip install -r requirements.txt
```

## Iniciar el sistema

Levantar el backend, la base de datos y el servicio de correo:

```bash
docker compose up -d --build
```

El backend aplica las migraciones de Django antes de iniciar el servidor; el SQL
canónico crea las tablas de negocio al inicializar el volumen PostgreSQL.
El portal queda disponible en `http://localhost:8000/`.

En la primera instalación, crear el Administrador con un correo propio y un RUT válido:

```bash
docker compose exec web python manage.py primer_admin --email admin@ejemplo.cl --rut 12.345.678-5 --nombres Nombre --apellidos Apellido
```

Reemplazar los datos del ejemplo por los de la persona responsable. Auth0 crea
la identidad y envía las instrucciones para definir la contraseña. Desde el
escritorio, ese Administrador puede aprovisionar las demás cuentas. No se cargan
usuarios ni contraseñas predeterminados.

Para respaldar o recuperar la base, consultar el [procedimiento de respaldo y restauración](respaldo_y_recuperacion.md).

| Acción | Comando |
|---|---|
| Consultar servicios | `docker compose ps` |
| Ver registros | `docker compose logs -f` |
| Detener servicios | `docker compose down` |

PostgreSQL conserva los datos en su volumen. En una instalación nueva, el esquema
se crea con [init_siget_bd.sql](../Base%20de%20datos/init_siget_bd.sql), que incluye
roles, permisos, estados y prioridades. Los datos de operación se registran desde
la aplicación. Este script es de inicialización y no debe ejecutarse sobre una
base que se quiera conservar.

### Abrir el escritorio

Con el backend disponible, utilizar el iniciador correspondiente:

```bash
# Linux
./iniciar_escritorio.sh
```

```bat
rem Windows
iniciar_escritorio.bat
```

Los iniciadores buscan `.venv` en la raíz de SIGET y en `Aplicación`; después
buscan Python en el sistema. También se puede iniciar con
`python -m siget_desktop.main` desde un entorno virtual activo.

El acceso se realiza con Auth0. Al reabrir el escritorio, una sesión guardada
vigente se valida con el servidor. **Cerrar sesión** elimina ese acceso local.

### Mantener dos cuentas abiertas

Usar un perfil local distinto en cada instancia. En terminales separadas:

```bash
./iniciar_escritorio.sh --perfil admin
./iniciar_escritorio.sh --perfil tecnico
```

En Windows, utilizar `iniciar_escritorio.bat` con los mismos argumentos. El perfil
aparece en el título de la ventana y separa las sesiones guardadas; no asigna
roles. Completar un inicio de sesión antes de comenzar el siguiente, ya que
comparten el puerto de retorno de Auth0.

## Uso por perfil

| Perfil | Funciones principales |
|---|---|
| Solicitante, en el portal web | Consultar sus equipos, enviar solicitudes y tickets, revisar avisos y calificar la atención. |
| Administrador, en el escritorio | Administrar activos, catálogos y cuentas; aprobar solicitudes, asignar técnicos y consultar auditoría y reportes. |
| Técnico, en el escritorio | Registrar entregas y devoluciones, tomar y atender tickets, gestionar órdenes de trabajo y sus repuestos. |

La interfaz muestra las acciones permitidas para cada cuenta. El servidor
comprueba sus permisos al realizar cada operación.

### Preparar el inventario

En **Activos TI → Administrar catálogos**, crear categorías, marcas y ubicaciones;
luego registrar modelos asociados a una marca y categoría. Con esos datos se
pueden registrar activos.

Los catálogos y activos que tienen referencias no se eliminan. Los activos
retirados conservan su historial mediante el estado de baja. Una cuenta con
actividad puede desactivarse sin borrar sus registros.

Los formularios solicitan confirmación antes de guardar cambios. El valor de
adquisición admite enteros y muestra separadores de miles, por ejemplo `1.250.000`.

### Etiquetas QR y lectura de equipos

En **Activos TI**, seleccionar un equipo para generar su etiqueta o dos o más
para **Imprimir lote**, hasta un máximo de 50. En la ficha del activo, el botón
cambia a **Reimprimir QR** cuando la etiqueta ya existe.

**Guardar PDF** ajusta el tamaño de las etiquetas a la cantidad y utiliza A4.
Una etiqueta aprovecha la hoja; los lotes grandes se reparten entre páginas.

Para identificar equipos, enfocar **Código de inventario o número de serie** y
escanear o escribir el identificador. El lector debe finalizar con Enter o Tab
y utilizar la misma distribución de teclado que el computador.

- En entrega, se comprueba la disponibilidad y la categoría de la solicitud aprobada.
- En devolución, se compara el equipo recibido con el esperado en la asignación.
- Al crear una orden de trabajo, se muestran los tickets elegibles del equipo identificado.

Después de revisar los datos, se confirma la operación. La lectura por sí sola
no registra movimientos. Más información en [etiquetas QR](api_docs/api_1_activos_asignaciones/activos/qr.md).

### Avisos, historial y datos de usuarios

El solicitante consulta sus avisos desde el centro de notificaciones del portal.
El [servicio de correo](api_docs/externas/resend/README.md) envía las notificaciones
y recordatorios configurados.

El historial de equipos se consulta en **Solicitudes y entregas → Historial y
Trazabilidad**. Para una orden de trabajo, ingresar su código o ID en la pestaña
de historial de **Órdenes de Trabajo** y pulsar **Buscar**.

El Administrador registra y corrige el RUT desde la gestión de cuentas. Se
conserva para trazabilidad y no se muestra en las consultas habituales. Cada
usuario puede revisar el suyo en **Mi perfil**.

## Código y documentación

| Carpeta | Contenido |
|---|---|
| `siget_web/` | Backend Django, APIs y portal web. |
| `siget_desktop/` | Cliente PySide6 y sus pruebas. |
| `api_docs/` | Rutas, permisos, datos y respuestas de las APIs. |

Consultar el [índice de APIs](api_docs/README.md), la
[configuración](configuracion.md) y las guías de cada servicio para los detalles técnicos.

## Pruebas y revisión del código

```bash
# Backend
docker compose exec web python manage.py check
docker compose exec web python manage.py test

# Escritorio, con el entorno virtual activo
python -m unittest discover -s siget_desktop/tests -p "test_*.py"
```

Las pruebas del backend utilizan una base PostgreSQL separada. Las pruebas
gráficas del escritorio se ejecutan sin abrir ventanas mediante
`QT_QPA_PLATFORM=offscreen`.

Desde la raíz de SIGET, con `.venv` activo, ejecutar `ruff check .` y `pyright`
para revisar errores de código y tipos.
