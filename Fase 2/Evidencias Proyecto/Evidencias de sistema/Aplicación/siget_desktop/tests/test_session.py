"""Pruebas unitarias de gestión de sesión del usuario en memoria."""

import time
import unittest

from siget_desktop.auth.session import UserSession


class UserSessionTests(unittest.TestCase):
    def setUp(self):
        self.session = UserSession()

    def test_estado_inicial_no_autenticado(self):
        self.assertFalse(self.session.is_authenticated())
        self.assertIsNone(self.session.access_token)
        self.assertEqual(len(self.session.roles), 0)

    def test_set_tokens_y_vigencia(self):
        self.session.set_tokens("token_abc", expires_in=3600, id_token="id_123")
        self.assertEqual(self.session.access_token, "token_abc")
        self.assertEqual(self.session.id_token, "id_123")
        self.assertFalse(self.session.is_expired())
        self.assertTrue(self.session.is_authenticated())

    def test_expiracion_controlada(self):
        # Token ya expirado
        self.session.access_token = "token_expirado"
        self.session.expires_at = time.time() - 10
        self.assertTrue(self.session.is_expired())
        self.assertFalse(self.session.is_authenticated())

    def test_actualizar_perfil_rbac(self):
        datos_backend = {
            "id_usuario": 10,
            "nombres": "Ana",
            "apellidos": "López",
            "nombre_completo": "Ana López",
            "correo": "ana.lopez@siget.cl",
            "roles": ["Técnico de soporte"],
            "permisos": ["CATALOGO_CONSULTAR", "TICKET_ATENDER"],
            "acceso_escritorio": True,
        }
        self.session.update_user_info(datos_backend)

        self.assertEqual(self.session.id_usuario, 10)
        self.assertEqual(self.session.nombre_completo, "Ana López")
        self.assertTrue(self.session.is_tecnico())
        self.assertFalse(self.session.is_admin())
        self.assertTrue(self.session.has_permission("TICKET_ATENDER"))
        self.assertFalse(self.session.has_permission("USUARIOS_ADMINISTRAR"))
        self.assertTrue(self.session.acceso_escritorio)

    def test_limpieza_completa_en_logout(self):
        self.session.set_tokens("token_xyz", expires_in=3600)
        self.session.update_user_info({
            "id_usuario": 5,
            "roles": ["Administrador del sistema"],
            "permisos": ["USUARIOS_ADMINISTRAR"],
            "acceso_escritorio": True,
        })
        self.assertTrue(self.session.is_admin())

        self.session.clear()

        self.assertIsNone(self.session.access_token)
        self.assertIsNone(self.session.id_token)
        self.assertEqual(self.session.expires_at, 0.0)
        self.assertIsNone(self.session.id_usuario)
        self.assertEqual(len(self.session.roles), 0)
        self.assertEqual(len(self.session.permisos), 0)
        self.assertFalse(self.session.acceso_escritorio)
        self.assertFalse(self.session.is_authenticated())


if __name__ == "__main__":
    unittest.main()
