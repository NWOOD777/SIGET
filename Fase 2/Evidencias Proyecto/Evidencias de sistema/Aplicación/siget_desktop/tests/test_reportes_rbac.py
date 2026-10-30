import unittest

from siget_desktop.auth.session import UserSession


class ReportesRBACTests(unittest.TestCase):

    def setUp(self):
        self.sesion = UserSession(
            access_token="token_prueba",
            expires_at=0,
            roles=[],
            permisos=[],
            acceso_escritorio=True,
        )

    def test_administrador_con_permiso(self):
        self.sesion.update_user_info(
            {
                "roles": ["Administrador del sistema"],
                "permisos": ["REPORTES_CONSULTAR"],
                "acceso_escritorio": True,
            }
        )

        self.assertTrue(self.sesion.is_admin())
        self.assertTrue(self.sesion.has_permission("REPORTES_CONSULTAR"))

    def test_administrador_sin_permiso(self):
        self.sesion.update_user_info(
            {
                "roles": ["Administrador del sistema"],
                "permisos": [],
                "acceso_escritorio": True,
            }
        )

        self.assertTrue(self.sesion.is_admin())
        self.assertFalse(self.sesion.has_permission("REPORTES_CONSULTAR"))

    def test_tecnico_sin_permiso(self):
        self.sesion.update_user_info(
            {
                "roles": ["Técnico de soporte"],
                "permisos": [],
                "acceso_escritorio": True,
            }
        )

        self.assertTrue(self.sesion.is_tecnico())
        self.assertFalse(self.sesion.is_admin())
        self.assertFalse(self.sesion.has_permission("REPORTES_CONSULTAR"))


if __name__ == "__main__":
    unittest.main()
