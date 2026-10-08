"""
Pruebas de enrutamiento y resolución de URLs para el módulo de usuarios,
administración RBAC y Django admin en SIGET.
"""

from django.test import SimpleTestCase
from django.urls import Resolver404, resolve, reverse


class UrlsRoutingTests(SimpleTestCase):
    """
    Verificación de la estructura de enrutamiento:

    - Autenticación externa: /auth/...
    - Administración RBAC: /administracion/...
    - Django Admin técnico: /admin/...
    """

    def test_01_reverse_auth_login(self):
        self.assertEqual(
            reverse("usuarios:auth_login"),
            "/auth/login/",
        )

    def test_02_reverse_auth_callback(self):
        self.assertEqual(
            reverse("usuarios:auth_callback"),
            "/auth/callback/",
        )

    def test_03_reverse_auth_logout(self):
        self.assertEqual(
            reverse("usuarios:auth_logout"),
            "/auth/logout/",
        )

    def test_04_reverse_auth_recover(self):
        self.assertEqual(
            reverse("usuarios:auth_recover"),
            "/auth/recover/",
        )

    def test_05_rutas_administrativas_web_ya_no_existen(self):
        rutas_removidas = [
            "/administracion/usuarios/",
            "/administracion/usuarios/1/",
            "/administracion/usuarios/1/roles/",
            "/administracion/roles/2/permisos/",
        ]
        for ruta in rutas_removidas:
            with self.subTest(ruta=ruta):
                with self.assertRaises(Resolver404):
                    resolve(ruta)

    def test_09_admin_sigue_resolviendo_django_admin(self):
        match = resolve("/admin/")

        self.assertEqual(
            match.app_name,
            "admin",
        )

    def test_10_auth_admin_ya_no_es_ruta_valida_siget(self):
        with self.assertRaises(
            Resolver404
        ):
            resolve("/auth/admin/")

    def test_11_rutas_soporte_web_ya_no_existen(self):
        """
        Valida que las rutas web operativas de soporte (/soporte/, /soporte/activos/)
        fueron retiradas de la Web de autoservicio según la arquitectura oficial
        (canal definitivo: consola de escritorio PySide6).
        """
        rutas_soporte = [
            "/soporte/",
            "/soporte/activos/",
        ]
        for ruta in rutas_soporte:
            with self.subTest(ruta=ruta):
                with self.assertRaises(Resolver404):
                    resolve(ruta)

