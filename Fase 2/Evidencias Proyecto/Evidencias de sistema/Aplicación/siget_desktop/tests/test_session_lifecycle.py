"""Regresiones de cancelación, expiración y resultados de sesiones anteriores."""
import os

os.environ['QT_QPA_PLATFORM']='offscreen'
import dataclasses
import socket
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

import requests
from PySide6.QtWidgets import QApplication

from siget_desktop.api.client import ApiClient, ForbiddenApiError, TokenExpiredApiError
from siget_desktop.auth.manager import AuthForbiddenError, AuthManager
from siget_desktop.auth.pkce import PkceContext
from siget_desktop.auth.server import CallbackResult, esperar_retorno_oauth
from siget_desktop.auth.session import current_session
from siget_desktop.config import config
from siget_desktop.ui.main_window import MainWindow
from siget_desktop.ui.workers import ApiWorker


class SessionLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        current_session.clear()

    def tearDown(self):
        current_session.clear()

    def test_rechazo_backend_no_conserva_credenciales(self):
        context=PkceContext.create()
        result=CallbackResult()
        result.code='code'
        result.state=context.state
        cfg=dataclasses.replace(config,auth0_domain='example.auth0.com',auth0_client_id='native',auth0_audience='https://siget.test')
        with patch('siget_desktop.auth.manager.config',cfg), patch('siget_desktop.auth.manager.PkceContext.create',return_value=context), patch('siget_desktop.auth.manager.esperar_retorno_oauth',return_value=result), patch.object(AuthManager,'_intercambiar_codigo',return_value={'access_token':'token','expires_in':3600}), patch.object(AuthManager,'_sincronizar_perfil_con_backend',side_effect=AuthForbiddenError('Cuenta inactiva')):
            with self.assertRaises(AuthForbiddenError):
                AuthManager(lambda url:True).iniciar_flujo_login()
        self.assertIsNone(current_session.access_token)

    def test_401_limpia_credenciales(self):
        current_session.set_tokens('token',3600)
        response=MagicMock(status_code=401)
        response.json.return_value={'codigo':'token_expirado'}
        with patch('requests.Session.request',return_value=response), self.assertRaises(TokenExpiredApiError):
            ApiClient().get('/api/usuarios/me/')
        self.assertIsNone(current_session.access_token)

    def test_token_vencido_no_sale_a_red(self):
        current_session.set_tokens('token',0)
        with patch('requests.Session.request') as network, self.assertRaises(TokenExpiredApiError):
            ApiClient().get('/api/activos/')
        network.assert_not_called()
        self.assertIsNone(current_session.access_token)

    def test_403_solo_cierra_sesion_si_cuenta_pierde_acceso(self):
        for code, preserved in [('permiso_denegado', True), ('cuenta_sin_acceso', False)]:
            with self.subTest(code=code):
                current_session.set_tokens('token',3600)
                response=MagicMock(status_code=403)
                response.json.return_value={'codigo':code}
                with patch('requests.Session.request',return_value=response), self.assertRaises(ForbiddenApiError):
                    ApiClient().get('/api/usuarios/')
                self.assertEqual(current_session.is_authenticated(),preserved)

    def test_respuesta_anterior_no_rellena_tablas(self):
        current_session.set_tokens('anterior',3600)
        generation=current_session.generation
        window=MainWindow()
        window._cerrar_sesion()
        current_session.set_tokens('nuevo',3600)
        window.view_usuarios._on_datos([{'nombres':'Privado'}],generation)
        self.assertEqual(window.view_usuarios.tabla.rowCount(),0)
        window.deleteLater()

    def test_worker_descarta_resultados_de_sesion_anterior(self):
        current_session.set_tokens('anterior',3600)
        worker=ApiWorker(lambda:current_session.clear())
        received=[]
        worker.signals.finished.connect(received.append)
        worker.run()
        self.assertEqual(received,[])
        worker._liberar()

    def test_401_tardio_no_cierra_nueva_sesion(self):
        current_session.set_tokens('anterior',3600)
        response=MagicMock(status_code=401)
        response.json.return_value={'codigo':'token_expirado'}
        def late(**kwargs):
            current_session.set_tokens('nuevo',3600)
            return response
        with patch('requests.Session.request',side_effect=late), self.assertRaises(TokenExpiredApiError):
            ApiClient().get('/api/usuarios/me/')
        self.assertEqual(current_session.access_token,'nuevo')

    def test_expiracion_retorna_al_acceso_y_limpia_vistas(self):
        current_session.set_tokens('token',3600)
        window=MainWindow()
        window.actualizar_sesion()
        window.view_activos.tabla.setRowCount(2)
        current_session.clear()
        emitted=[]
        window.sesion_cerrada.connect(lambda:emitted.append(True))
        window._verificar_sesion()
        self.assertEqual(window.view_activos.tabla.rowCount(),0)
        self.assertTrue(emitted)
        window.deleteLater()


class LoopbackTests(unittest.TestCase):
    def test_puerto_abierto_antes_navegador_y_liberado_al_cancelar(self):
        with socket.socket() as available:
            available.bind(('127.0.0.1',0))
            port=available.getsockname()[1]
        cancelled=threading.Event()
        def ready():
            with socket.create_connection(('127.0.0.1',port),timeout=1):
                pass
            cancelled.set()
        started=time.monotonic()
        result=esperar_retorno_oauth(port,10,on_ready=ready,cancel_event=cancelled)
        self.assertIsNone(result.code)
        self.assertLess(time.monotonic()-started,2)
        with socket.socket() as released:
            released.bind(('127.0.0.1',port))

    def test_state_invalido_no_finaliza_flujo_y_error_html_escapado(self):
        requests_done=[]
        threads=[]
        with socket.socket() as available:
            available.bind(('127.0.0.1',0))
            port=available.getsockname()[1]
        def callback():
            bad=requests.get(f'http://127.0.0.1:{port}/callback',params={'code':'bad','state':'incorrecto'},timeout=2)
            requests_done.append(bad.status_code)
            good=requests.get(f'http://127.0.0.1:{port}/callback',params={'error':'access_denied','error_description':'<b>prueba</b>','state':'correcto'},timeout=2)
            requests_done.append('<b>prueba</b>' not in good.text)
        def ready():
            thread=threading.Thread(target=callback)
            threads.append(thread)
            thread.start()
        result=esperar_retorno_oauth(port,4,on_ready=ready,expected_state='correcto')
        for thread in threads:
            thread.join(3)
        self.assertEqual(requests_done,[400,True])
        self.assertEqual(result.error,'access_denied')
