"""Aislamiento de sesiones locales y selección de cuenta durante la autenticación."""

import errno
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from PySide6.QtWidgets import QApplication

from siget_desktop.auth.cache import guardar_cache, leer_cache, ruta_cache
from siget_desktop.auth.manager import AuthManager, AuthProviderError
from siget_desktop.auth.pkce import PkceContext
from siget_desktop.auth.session import current_session
from siget_desktop.perfiles import configurar_perfil, titulo_con_perfil, validar_perfil


class PerfilesEscritorioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        carpeta = tempfile.TemporaryDirectory()
        self.base = Path(carpeta.name)
        self.addCleanup(carpeta.cleanup)
        parche = patch("siget_desktop.auth.cache.QStandardPaths.writableLocation", return_value=str(self.base))
        parche.start()
        self.addCleanup(parche.stop)
        configurar_perfil()
        self.addCleanup(configurar_perfil)
        self.addCleanup(current_session.clear)
        current_session.clear()

    def guardar(self, perfil, token):
        configurar_perfil(perfil)
        current_session.set_tokens(token, 3600)
        current_session.update_user_info({"acceso_escritorio": True, "roles": ["Técnico de soporte"]})
        self.assertTrue(guardar_cache())
        return ruta_cache()

    def test_sesiones_independientes_y_cierre_no_afecta_otro_perfil(self):
        admin = self.guardar("admin", "token-admin")
        tecnico = self.guardar("tecnico", "token-tecnico")
        self.assertNotEqual(admin, tecnico)
        self.assertTrue(admin.is_file())
        datos_tecnico = leer_cache()
        assert datos_tecnico is not None
        self.assertEqual(datos_tecnico[0], "token-tecnico")
        current_session.clear()
        self.assertFalse(tecnico.exists())
        configurar_perfil("admin")
        datos_admin = leer_cache()
        assert datos_admin is not None
        self.assertEqual(datos_admin[0], "token-admin")

    def test_nombre_no_otorga_rol_y_titulo_identifica_instancia(self):
        self.guardar("admin", "token-tecnico")
        self.assertTrue(current_session.is_tecnico())
        self.assertFalse(current_session.is_admin())
        self.assertEqual(titulo_con_perfil("SIGET"), "SIGET [admin]")
        configurar_perfil()
        self.assertEqual(titulo_con_perfil("SIGET"), "SIGET")
        self.assertEqual(ruta_cache(), self.base / "sesion" / "acceso.json")

    def test_validacion_evitar_rutas_y_normalizar_nombre(self):
        self.assertEqual(validar_perfil("Admin-01"), "admin-01")
        for valor in ("", "../admin", "a/b", "a\\b", "a b", "á", "a" * 41):
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                validar_perfil(valor)

    def test_perfil_nombrado_pide_nueva_autenticacion_conservando_pkce(self):
        pkce = PkceContext.create()
        normal = parse_qs(urlsplit(AuthManager().construir_url_autorizacion(pkce)).query)
        self.assertEqual(normal["prompt"], ["login"])
        configurar_perfil("tecnico")
        separado = parse_qs(urlsplit(AuthManager().construir_url_autorizacion(pkce)).query)
        self.assertEqual(separado["prompt"], ["login"])
        self.assertEqual(normal, separado)

    @patch("siget_desktop.auth.manager.esperar_retorno_oauth", side_effect=OSError(errno.EADDRINUSE, "ocupado"))
    @patch("siget_desktop.auth.manager.config")
    def test_dos_autenticaciones_simultaneas_indican_reintento(self, _config, _retorno):
        with self.assertRaisesRegex(AuthProviderError, "otro inicio de sesión"):
            AuthManager().iniciar_flujo_login()

    def test_dos_procesos_conservan_tokens_y_cierres_separados(self):
        programa = '''
import sys
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from siget_desktop.auth.cache import guardar_cache, leer_cache
from siget_desktop.auth.session import current_session
from siget_desktop.perfiles import configurar_perfil
app = QApplication([])
configurar_perfil(sys.argv[1])
with patch("siget_desktop.auth.cache.QStandardPaths.writableLocation", return_value=sys.argv[3]):
    if sys.argv[2] == "guardar":
        current_session.set_tokens("token-" + sys.argv[1], 3600)
        current_session.update_user_info({"acceso_escritorio": True})
        assert guardar_cache()
    elif sys.argv[2] == "cerrar":
        current_session.clear()
    else:
        datos = leer_cache()
        print(datos[0] if datos else "sin-sesion")
'''

        def proceso(perfil, accion):
            resultado = subprocess.run(
                [sys.executable, "-c", programa, perfil, accion, str(self.base)],
                cwd=Path(__file__).resolve().parents[2],
                env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
                capture_output=True, text=True, timeout=20, check=True,
            )
            return resultado.stdout.strip()

        proceso("admin", "guardar")
        proceso("tecnico", "guardar")
        self.assertEqual(proceso("admin", "leer"), "token-admin")
        self.assertEqual(proceso("tecnico", "leer"), "token-tecnico")
        proceso("tecnico", "cerrar")
        self.assertEqual(proceso("admin", "leer"), "token-admin")
        self.assertEqual(proceso("tecnico", "leer"), "sin-sesion")
