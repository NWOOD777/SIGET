"""Persistencia, revocación y Enter en formularios Qt."""
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton, QVBoxLayout

from siget_desktop.auth.cache import guardar_cache, leer_cache
from siget_desktop.auth.manager import AuthForbiddenError, AuthManager, AuthProviderError
from siget_desktop.auth.session import current_session
from siget_desktop.tests.qt_helpers import limpiar_widgets
from siget_desktop.ui.dialogs.common import SessionDialog


class SesionPersistenteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.addCleanup(limpiar_widgets)
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "privado" / "acceso.json"
        self.patch = patch("siget_desktop.auth.cache.ruta_cache", return_value=self.path)
        self.patch.start()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.patch.stop)
        self.addCleanup(current_session.clear)
        current_session.clear()
        current_session.set_tokens("token-de-prueba", 3600, id_token="no-persistir")
        current_session.update_user_info({"id_usuario": 1, "acceso_escritorio": True, "roles": ["Técnico de soporte"]})

    def test_cache_privada_no_guarda_roles_ni_id_token(self):
        self.assertTrue(guardar_cache())
        data = json.loads(self.path.read_text())
        self.assertEqual(set(data), {"entorno", "access_token", "expires_at"})
        if os.name == "posix":
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(self.path.parent.stat().st_mode & 0o777, 0o700)

    def test_reabre_revalidando_roles_actuales(self):
        guardar_cache()
        # Simula un proceso nuevo sin invocar el cierre explícito de sesión.
        current_session.access_token = None
        profile = {"id_usuario": 1, "acceso_escritorio": True, "roles": ["Administrador del sistema"]}
        with patch.object(AuthManager, "_sincronizar_perfil_con_backend", return_value=profile) as backend:
            result = AuthManager().restaurar_sesion()
        backend.assert_called_once_with("token-de-prueba")
        self.assertEqual(result, profile)
        self.assertTrue(current_session.is_admin())

    def test_cerrar_sesion_elimina_cache(self):
        guardar_cache()
        AuthManager().cerrar_sesion()
        self.assertFalse(self.path.exists())
        self.assertFalse(current_session.is_authenticated())

    def test_expirada_corrupta_o_otro_entorno_no_se_recupera(self):
        for change in ({"expires_at": time.time() - 10}, {"entorno": "otro"}, {"expires_at": float("nan")}):
            guardar_cache()
            data = json.loads(self.path.read_text())
            data.update(change)
            self.path.write_text(json.dumps(data))
            self.assertIsNone(leer_cache())
            self.assertFalse(self.path.exists())
        self.path.write_text("[]")
        self.assertIsNone(leer_cache())

    def test_cuenta_sin_acceso_elimina_cache_sin_restaurar(self):
        guardar_cache()
        current_session.access_token = None
        with patch.object(AuthManager, "_sincronizar_perfil_con_backend", return_value={"acceso_escritorio": False}):
            with self.assertRaises(AuthForbiddenError):
                AuthManager().restaurar_sesion()
        self.assertFalse(self.path.exists())
        self.assertFalse(current_session.is_authenticated())

    def test_error_de_red_conserva_cache_para_reintento(self):
        guardar_cache()
        current_session.access_token = None
        with patch.object(AuthManager, "_sincronizar_perfil_con_backend", side_effect=AuthProviderError("Sin red")):
            with self.assertRaises(AuthProviderError):
                AuthManager().restaurar_sesion()
        self.assertTrue(self.path.exists())
        self.assertFalse(current_session.is_authenticated())

    def test_enter_no_pulsa_cancelar_ni_cierra_modal_vacio(self):
        dialog = SessionDialog()
        layout = QVBoxLayout(dialog)
        field = QLineEdit()
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(dialog.reject)
        layout.addWidget(field)
        layout.addWidget(cancel)
        dialog.show()
        self.app.processEvents()
        for widget in (field, cancel):
            widget.setFocus()
            QTest.keyClick(widget, Qt.Key.Key_Return)
            self.app.processEvents()
            self.assertTrue(dialog.isVisible())
        dialog.reject()

    def test_cierre_durante_restauracion_no_abre_sesion(self):
        from threading import Event

        from siget_desktop.auth.manager import AuthCancelledError
        guardar_cache()
        current_session.access_token = None
        cancel = Event()
        cancel.set()
        with patch.object(AuthManager, "_sincronizar_perfil_con_backend", return_value={"acceso_escritorio": True}):
            with self.assertRaises(AuthCancelledError):
                AuthManager().restaurar_sesion(cancel_event=cancel)
        self.assertFalse(current_session.is_authenticated())
        self.assertTrue(self.path.exists())
