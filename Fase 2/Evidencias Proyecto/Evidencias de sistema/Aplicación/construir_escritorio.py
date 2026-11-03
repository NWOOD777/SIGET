#!/usr/bin/env python3
"""Construye el paquete de escritorio de SIGET para el equipo actual."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

DEPENDENCIAS_ESCRITORIO = {"pyside6", "requests", "python-dotenv", "openpyxl"}


def python_del_proyecto(app: Path) -> Path:
    ruta_python = "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
    entorno_local = app / ".venv"
    entornos = [entorno_local]
    if len(app.parents) >= 4:
        entornos.insert(0, app.parents[3] / ".venv")
    for entorno in entornos:
        python = entorno / ruta_python
        if (entorno / "pyvenv.cfg").is_file() and python.is_file():
            return python

    print("Creando el entorno virtual de SIGET…", flush=True)
    venv.EnvBuilder(with_pip=True).create(entorno_local)
    return entorno_local / ruta_python


def instalar_dependencias(app: Path) -> None:
    requisitos = {}
    for linea in (app / "requirements.txt").read_text(encoding="utf-8").splitlines():
        nombre = re.match(r"[\w.-]+", linea.lstrip())
        if nombre and nombre[0].lower() in DEPENDENCIAS_ESCRITORIO:
            requisitos[nombre[0].lower()] = linea.strip()
    faltantes = DEPENDENCIAS_ESCRITORIO - requisitos.keys()
    if faltantes:
        raise OSError(f"Faltan dependencias en requirements.txt: {', '.join(sorted(faltantes))}.")

    print("Verificando las dependencias del escritorio…", flush=True)
    subprocess.run(
        [
            sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
            "PyInstaller==6.22.3", *requisitos.values(),
        ],
        check=True,
        cwd=app,
    )


def leer_configuracion_proyecto() -> dict[str, str]:
    try:
        from siget_desktop.config import config
    except ValueError:
        raise OSError("Revisa los valores numéricos de la configuración del escritorio.") from None

    configuracion = {
        "SIGET_PUBLIC_URL": config.api_base_url.strip(),
        "AUTH0_DOMAIN": config.auth0_domain.strip(),
        "AUTH0_API_AUDIENCE": config.auth0_audience.strip(),
        "AUTH0_DESKTOP_CLIENT_ID": config.auth0_client_id.strip(),
        "SIGET_HTTP_TIMEOUT": str(config.http_timeout),
        "AUTH0_DESKTOP_CALLBACK_PORT": str(config.auth0_callback_port),
    }
    faltantes = [clave for clave, valor in configuracion.items() if not valor]
    if faltantes:
        raise OSError(f"Completa en el .env de Aplicación: {', '.join(faltantes)}.")
    if config.http_timeout < 1:
        raise OSError("SIGET_HTTP_TIMEOUT debe ser un entero positivo.")
    if not 1 <= config.auth0_callback_port <= 65535:
        raise OSError("AUTH0_DESKTOP_CALLBACK_PORT debe estar entre 1 y 65535.")
    if any("\n" in valor or "\r" in valor for valor in configuracion.values()):
        raise OSError("La configuración del escritorio debe usar valores de una sola línea.")
    return configuracion


def escribir_configuracion(destino: Path, configuracion: dict[str, str]) -> None:
    lineas = []
    for clave, valor in configuracion.items():
        escapado = valor.replace("\\", "\\\\").replace("'", "\\'")
        lineas.append(f"{clave}='{escapado}'\n")
    destino.write_text("".join(lineas), encoding="utf-8")


def construir(carpeta: Path, *, consola: bool, configuracion: dict[str, str]) -> Path:
    app = Path(__file__).resolve().parent
    escritorio = app / "siget_desktop"
    entrada = escritorio / "main.py"
    recursos = escritorio / "ui" / "assets"
    if not entrada.is_file() or not recursos.is_dir():
        raise OSError("El script debe estar junto a la carpeta siget_desktop de SIGET.")

    windows = sys.platform == "win32"
    with tempfile.TemporaryDirectory(prefix="siget-compilacion-") as temporal:
        trabajo = Path(temporal)
        spec = trabajo / "spec"
        spec.mkdir()
        archivo_publico = trabajo / ".env"
        escribir_configuracion(archivo_publico, configuracion)
        print("Generando el paquete de SIGET…", flush=True)
        subprocess.run(
            [
                sys.executable, "-m", "PyInstaller",
                "--onefile", "--console" if consola else "--windowed", "--noupx",
                "--name", "SIGET",
                "--distpath", str(trabajo / "dist"),
                "--workpath", str(trabajo / "build"),
                "--specpath", str(spec),
                "--paths", str(app),
                "--add-data", f"{recursos}:siget_desktop/ui/assets",
                "--add-data", f"{archivo_publico}:.",
                str(entrada),
            ],
            check=True,
            cwd=app,
        )
        nombre = "SIGET.exe" if windows else "SIGET"
        ejecutable = trabajo / "dist" / nombre
        if not ejecutable.is_file():
            raise OSError("PyInstaller no generó el ejecutable de SIGET.")

        carpeta.mkdir(parents=True, exist_ok=True)
        plataforma = "windows" if windows else "linux"
        destino = Path(tempfile.mkdtemp(prefix=f"{plataforma}-", dir=carpeta))
        try:
            shutil.move(str(ejecutable), destino / nombre)
        except OSError:
            shutil.rmtree(destino, ignore_errors=True)
            raise
        return destino / nombre


def main() -> int:
    parser = argparse.ArgumentParser(description="Construye el ejecutable de escritorio de SIGET.")
    parser.add_argument(
        "--salida",
        type=Path,
        default=Path.home() / "SIGET-compilaciones",
        help="Carpeta donde se guardan los paquetes. Por defecto, SIGET-compilaciones en tu carpeta de usuario.",
    )
    parser.add_argument("--consola", action="store_true", help="Muestra una consola para diagnosticar el arranque.")
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        parser.error("Se necesita Python 3.12 o superior.")
    if sys.platform not in {"win32", "linux"}:
        parser.error("Ejecuta el script en el sistema de destino: Windows o Linux.")

    try:
        app = Path(__file__).resolve().parent
        if not (app / ".env").is_file():
            raise OSError("Crea el .env de Aplicación a partir de .env.example.")
        if sys.prefix == sys.base_prefix:
            python = python_del_proyecto(app)
            return subprocess.run([str(python), __file__, *sys.argv[1:]], check=False).returncode

        instalar_dependencias(app)
        configuracion = leer_configuracion_proyecto()
        ejecutable = construir(args.salida.expanduser().resolve(), consola=args.consola, configuracion=configuracion)
    except KeyboardInterrupt:
        print("\nCompilación cancelada.", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as error:
        print(f"La compilación falló (código {error.returncode}). Revisa la salida anterior.", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"No fue posible construir SIGET: {error}", file=sys.stderr)
        return 1
    print(f"Ejecutable: {ejecutable}")
    print("Para distribuir SIGET, copia este archivo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
