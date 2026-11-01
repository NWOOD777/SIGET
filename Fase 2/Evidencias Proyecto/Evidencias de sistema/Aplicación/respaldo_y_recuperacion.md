# Respaldo y recuperación

PostgreSQL conserva los datos en su volumen. Un respaldo separado permite
recuperarlos ante pérdida del volumen o errores de operación. El archivo contiene
información de usuarios y actividad: guardarlo fuera del repositorio, en una
ubicación con acceso restringido. Mantener una copia en otro dispositivo.

## Crear un respaldo

Ejecutar desde `Aplicación`, con PostgreSQL disponible y la imagen actualizada.
Crear una carpeta fuera del proyecto y montarla en el contenedor:

```bash
mkdir -p "$HOME/respaldos_siget"
docker compose run --rm --no-deps --volume "$HOME/respaldos_siget:/respaldos" web python manage.py respaldo_bd --salida /respaldos/siget_2026-11-01.dump
```

En Windows PowerShell:

```powershell
$sigetBackupDir = Join-Path $env:USERPROFILE "Documents/respaldos_siget"
New-Item -ItemType Directory -Force -Path $sigetBackupDir
docker compose run --rm --no-deps --volume "${sigetBackupDir}:/respaldos" web python manage.py respaldo_bd --salida /respaldos/siget_2026-11-01.dump
```

Usar un nombre distinto en cada respaldo. El comando no reemplaza archivos
existentes. PostgreSQL obtiene una copia consistente de la estructura y datos.
Las sesiones de acceso se excluyen: tras recuperar una base, los usuarios deben
autenticarse nuevamente. Las identidades y contraseñas administradas por Auth0,
la configuración `.env` y los archivos externos no forman parte del respaldo SQL;
conservar su configuración de forma separada y privada.

Realizar un respaldo antes de cambios de estructura y al finalizar cada jornada
con actividad. Verificar periódicamente una restauración en un entorno separado.

## Restaurar

Elegir la base de destino mediante la configuración de Compose. Para una prueba,
utilizar un proyecto y volumen separados. Para recuperar la instalación habitual,
detener primero las escrituras y conservar una copia de su estado actual.

```bash
docker compose stop web correo
docker compose run --rm --no-deps --volume "$HOME/respaldos_siget:/respaldos" web python manage.py restaurar_bd --archivo /respaldos/siget_2026-11-01.dump --confirmar
docker compose up -d web
```

En PowerShell, utilizar el montaje `"${sigetBackupDir}:/respaldos"` del ejemplo
anterior. La restauración se ejecuta en una transacción: si falla, no deja una
recuperación parcial. `--confirmar` es obligatorio porque se reemplazan los datos
de la base elegida. Restaurar solamente archivos de confianza.

Comprobar el acceso, inventario, asignaciones, tickets, stock y bitácora después
de restaurar. Revisar las notificaciones pendientes antes de iniciar el servicio
`correo`, para decidir cuáles corresponde despachar. Después, ejecutar
`docker compose up -d correo`. Al usar un respaldo de una
versión anterior, verificar su compatibilidad con el código antes de levantar servicios.

## Comprobar el entorno

```bash
docker compose ps
docker compose exec web python manage.py check
docker compose exec web python manage.py showmigrations
```

Si el login no puede guardar sesiones, reconstruir la imagen y reiniciar Web;
el arranque aplica las migraciones pendientes. Si no existen cuentas, utilizar
`primer_admin` según el README de aplicación. Los errores de configuración deben
revisarse localmente sin publicar `.env`, cabeceras de autorización ni tokens.
