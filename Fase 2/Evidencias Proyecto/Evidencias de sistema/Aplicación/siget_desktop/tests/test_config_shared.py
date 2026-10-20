"""Configuración compartida sin mezclar credenciales Web y nativas."""
import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

module = importlib.import_module('siget_desktop.config')


class SharedConfigurationTests(unittest.TestCase):
    def test_solo_valores_publicos_y_sin_exportar_secretos(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'.env'
            path.write_text('AUTH0_DOMAIN=tenant.auth0.com\nAUTH0_DESKTOP_CLIENT_ID=nativo\nDJANGO_SECRET_KEY=privado\nAUTH0_CLIENT_SECRET=privado\n')
            with patch.dict(os.environ,{},clear=True):
                values=module._leer_configuracion_publica(path)
                self.assertEqual(set(values),{'AUTH0_DOMAIN','AUTH0_DESKTOP_CLIENT_ID'})
                self.assertNotIn('DJANGO_SECRET_KEY',os.environ)

    def test_url_dominio_audiencia_compartidos_y_entorno_prioritario(self):
        with patch.dict(module._ENV_LOCAL,{'SIGET_PUBLIC_URL':'http://localhost:8000/','AUTH0_DOMAIN':'tenant.auth0.com','AUTH0_API_AUDIENCE':'https://siget.test','AUTH0_DESKTOP_CLIENT_ID':'nativo'},clear=True), patch.dict(os.environ,{'AUTH0_DOMAIN':'override.auth0.com'},clear=True):
            cfg=module.DesktopConfig()
            self.assertEqual(cfg.api_base_url,'http://localhost:8000')
            self.assertEqual(cfg.auth0_domain,'override.auth0.com')
            self.assertEqual(cfg.auth0_audience,'https://siget.test')
            self.assertEqual(cfg.auth0_client_id,'nativo')

    def test_no_reutiliza_client_id_web(self):
        with patch.dict(module._ENV_LOCAL,{},clear=True), patch.dict(os.environ,{'AUTH0_CLIENT_ID':'web'},clear=True):
            self.assertEqual(module.DesktopConfig().auth0_client_id,'')

    def test_ruta_env_independiente_del_directorio_actual(self):
        assert module.__file__ is not None
        self.assertEqual(module.ENV_PATH,Path(module.__file__).resolve().parent.parent/'.env')
