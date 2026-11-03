# Manual de construcción y distribución de SIGET

SIGET se entrega en dos partes. El portal y la API se construyen con Docker Compose y se ejecutan junto a PostgreSQL y el servicio de correo. El cliente PySide6 se empaqueta como una aplicación de escritorio independiente. El equipo que recibe el cliente no necesita instalar Python, pero sí necesita acceso al backend de SIGET y a Auth0.

Los comandos se ejecutan desde la carpeta `Aplicación`, donde están `docker-compose.yml` y `siget_desktop/`:

```text
Fase 2/Evidencias Proyecto/Evidencias de sistema/Aplicación
```

## 1. Construir y preparar el servidor

Instala Docker con Compose v2. Clona el repositorio y sitúate en `Aplicación`. Para una instalación nueva, crea un `.env` de servidor con los nombres de variables de `.env.example`. Si ya existe, conserva la configuración que corresponde a ese entorno.

```bash
# Linux
cp -n .env.example .env
```

```powershell
# Windows PowerShell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Completa la conexión de PostgreSQL, las claves de Django y los parámetros de Auth0 y correo de acuerdo con la [guía de configuración](configuracion.md). En Auth0, registra el portal y el cliente Native como aplicaciones separadas. El escritorio usa Authorization Code con PKCE. La audiencia de la API debe coincidir en Auth0, el backend y el escritorio.

Construye la imagen de Django y levanta los tres servicios:

```bash
docker compose build web
docker compose up -d
docker compose ps
```

`web` ejecuta el portal y la API. `correo` reutiliza la imagen y despacha notificaciones. `postgres` crea el esquema de negocio con `init_siget_bd.sql` cuando inicializa un volumen vacío. Django aplica sus migraciones al iniciar. El portal queda disponible en [http://localhost:8000/](http://localhost:8000/). Si el arranque falla, revisa `docker compose logs --tail 100 web postgres correo`.

En una instalación nueva, ejecuta el alta inicial con los datos del administrador responsable. Sustituye los datos del ejemplo antes de ejecutar el comando:

```bash
docker compose exec web python manage.py primer_admin --email admin@ejemplo.cl --rut 12.345.678-5 --nombres Nombre --apellidos Apellido
```

El Compose del repositorio publica el servicio en `127.0.0.1` y usa el servidor de desarrollo de Django. Sirve para la instalación local y la demostración. Para clientes en otros equipos, el servidor debe estar publicado con una URL HTTPS accesible y una configuración de despliegue apropiada. En ese caso, configura esa URL en el servidor y en el escritorio, y registra el callback web correspondiente en Auth0. El callback Native sigue apuntando al equipo donde corre el escritorio.

## 2. Construir el ejecutable de escritorio

Instala Python 3.12 o superior en el equipo que compilará el cliente. Utiliza el sistema operativo y la arquitectura de destino, por ejemplo x86-64. Si falta alguna dependencia, el equipo debe poder descargarla. Desde la carpeta `Aplicación`, ejecuta el comando correspondiente:

**Linux**

```bash
python3 construir_escritorio.py
```

**Windows (PowerShell)**

```powershell
py -3 construir_escritorio.py
```

Si tu instalación de Windows ofrece `python` en lugar de `py`, ejecuta `python construir_escritorio.py`.

El [script de construcción](construir_escritorio.py) usa el entorno virtual activo. Si ejecutas el comando con el Python del sistema, busca `.venv` en la raíz de SIGET y luego en `Aplicación`. Si no encuentra uno, lo crea en `Aplicación`. Conserva los paquetes compatibles ya instalados y usa `requirements.txt` para respetar las versiones del proyecto al completar las dependencias del escritorio. También instala PyInstaller si hace falta.

El script genera un archivo único con los recursos y la configuración pública del cliente. Muestra la ruta de salida en `SIGET-compilaciones`, dentro de tu carpeta de usuario. Para distribuirlo, copia solo `SIGET.exe` en Windows o `SIGET` en Linux. En Windows se abre con doble clic. En Linux se puede ejecutar con `./SIGET`. El archivo extrae sus dependencias en una carpeta temporal al abrirse.

Para compilar en otra ubicación, agrega `--salida RUTA`. Para investigar un fallo de arranque en Windows, agrega `--consola` y abre ese ejecutable desde PowerShell. Si distribuyes a varias versiones de Linux, construye y prueba en la más antigua que quieras soportar. El paquete conserva dependencias del sistema, entre ellas glibc y las bibliotecas gráficas que usa Qt.

## 3. Configuración pública y verificación

La compilación toma la configuración pública del mismo `.env` de `Aplicación` que usa el escritorio en desarrollo. Las variables de entorno de la terminal tienen prioridad si están definidas. Si falta un valor obligatorio, el script indica qué variable debes completar antes de volver a ejecutarlo.

| Variable | Valor |
|---|---|
| `SIGET_PUBLIC_URL` | URL del backend. Usa `http://localhost:8000` si corre en el mismo equipo, o su URL HTTPS si está en otro. |
| `AUTH0_DOMAIN` | Dominio de Auth0 sin `https://`. |
| `AUTH0_API_AUDIENCE` | Identificador de la API de SIGET en Auth0. |
| `AUTH0_DESKTOP_CLIENT_ID` | Identificador público de la aplicación Native. |
| `AUTH0_DESKTOP_CALLBACK_PORT` | Opcional. Puerto local de retorno, `42813` por defecto. |
| `SIGET_HTTP_TIMEOUT` | Opcional. Tiempo de espera HTTP en segundos, `10` por defecto. |

En Auth0, autoriza `http://127.0.0.1:42813/callback` o la URL con el puerto que hayas elegido. El ejecutable conserva los parámetros públicos de la compilación y puede usar variables de entorno para reemplazarlos al abrirse. Si cambia el servidor y quieres entregar un ejecutable listo para abrir con doble clic, vuelve a compilarlo con la URL nueva.

Las credenciales y claves de Django, PostgreSQL, Auth0 Web, Management API y Resend permanecen en el servidor. El cliente necesita conexión al backend y a Auth0 para iniciar sesión y operar.

Antes de distribuir cada compilación:

1. Copia solo el ejecutable a una carpeta vacía y ábrelo. Debe aparecer la pantalla de acceso.
2. Inicia sesión con una cuenta de prueba y verifica que el navegador vuelva al escritorio y que se cargue el perfil.
3. Consulta un activo y abre una función con recursos gráficos, como la vista previa de una etiqueta QR. Si el perfil dispone de reportes, verifica una exportación.
4. Repite la comprobación en el sistema operativo y arquitectura de destino. Si Qt no puede cargar su plataforma gráfica en Linux, ejecuta el binario desde la terminal y revisa las dependencias del complemento Qt de la distribución.

Referencias: [opciones de PyInstaller](https://pyinstaller.org/en/stable/usage.html), [configuración de archivos en el paquete](https://pyinstaller.org/en/stable/runtime-information.html) y [manual de la aplicación](README.md).
