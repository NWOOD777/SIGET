"""Contrato REST de cierre técnico con PostgreSQL aislado."""
from unittest.mock import patch

from django.test import override_settings
from django.urls import resolve, reverse
from rest_framework.exceptions import AuthenticationFailed

from notificaciones.models import Notificacion
from ordenes_trabajo.models import CierreTecnico
from ordenes_trabajo.services import iniciar_reparacion, pausar_orden_trabajo
from tickets.tests.test_consolidacion_ot_postgresql import ConsolidacionOTFixture
from usuarios.models import BitacoraAuditoria, RolPermiso, UsuarioRol, Rol


class CierreTecnicoAPITests(ConsolidacionOTFixture):
    def setUp(self):
        super().setUp()
        self.orden = self.crear_ot()
        self.url = reverse("completar-orden-trabajo", kwargs={"pk": self.orden.pk})
        self.datos = {"resultado": "NO_REPARABLE", "informe_descarte": "Placa irreparable"}

    def post(self, datos=None, usuario=None):
        return self.cliente(usuario or self.segundo).post(self.url, self.datos if datos is None else datos, format="json")

    def foto(self):
        self.orden.refresh_from_db(); self.ticket.refresh_from_db(); self.activo_ot.refresh_from_db()
        return (CierreTecnico.objects.count(), BitacoraAuditoria.objects.count(), Notificacion.objects.count(),
                self.orden.id_estado_ot_id, self.ticket.id_estado_ticket_id, self.activo_ot.id_estado_activo_id)

    def test_ruta_y_solo_post(self):
        self.assertEqual(self.url, f"/api/ordenes-trabajo/{self.orden.pk}/completar/")
        self.assertEqual(resolve(self.url).url_name, "completar-orden-trabajo")
        self.assertEqual(self.cliente(self.segundo).get(self.url).status_code, 405)

    def test_no_reparable_respuesta_y_actor_colaborador(self):
        respuesta = self.post()
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        datos = respuesta.json()
        self.assertEqual(set(datos), {"id_orden", "estado", "resultado", "id_cierre_tecnico", "fecha_cierre",
                                     "id_activo", "estado_activo", "id_ticket", "estado_ticket"})
        self.assertEqual(datos["id_orden"], self.orden.pk)
        self.assertEqual(datos["estado"], "Completada")
        self.assertEqual(datos["estado_activo"], "Dado de baja")
        self.assertEqual(datos["estado_ticket"], "Resuelto")
        self.assertEqual(datos["id_ticket"], self.ticket.pk)
        self.assertEqual(datos["id_activo"], self.activo_ot.pk)
        cierre = CierreTecnico.objects.get()
        self.assertEqual(datos["id_cierre_tecnico"], cierre.pk)
        self.assertTrue(datos["fecha_cierre"])
        self.assertEqual(cierre.id_tecnico_id, self.segundo.pk)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.id_tecnico_responsable_id, self.tecnico.pk)

    def test_exito(self):
        iniciar_reparacion(self.orden.pk, self.tecnico)
        respuesta = self.post({"resultado": "REPARACION_EXITOSA", "solucion_aplicada": "Cambio de placa", "pruebas_realizadas": "Encendido y red"})
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["estado_activo"], "Disponible")
        self.assertEqual(respuesta.data["resultado"], "REPARACION_EXITOSA")

    def test_datos_invalidos_sin_efectos(self):
        antes = self.foto()
        for datos in ({}, [], {"resultado": "OTRO"}, {"resultado": "X" * 33},
                      {"resultado": "NO_REPARABLE"}, {"resultado": "NO_REPARABLE", "informe_descarte": " \t"},
                      {"resultado": "NO_REPARABLE", "informe_descarte": 10},
                      {"resultado": "REPARACION_EXITOSA", "solucion_aplicada": "Solución"}):
            with self.subTest(datos=datos):
                self.assertEqual(self.post(datos).status_code, 400)
                self.assertEqual(self.foto(), antes)

    def test_campos_sensibles_y_adicionales_rechazados(self):
        antes = self.foto()
        for campo in ("id_tecnico", "tecnico", "id_orden", "fecha_cierre", "estado", "estado_activo", "estado_ticket", "desconocido"):
            with self.subTest(campo=campo):
                self.assertEqual(self.post({**self.datos, campo: "Manipulado"}).status_code, 400)
                self.assertEqual(self.foto(), antes)

    def test_anonimo_y_roles_no_autorizados(self):
        antes = self.foto()
        self.assertEqual(self.cliente().post(self.url, self.datos, format="json").status_code, 403)
        for usuario in (self.solicitante, self.admin):
            self.assertEqual(self.post(usuario=usuario).status_code, 403)
        self.assertEqual(self.foto(), antes)

    def test_permisos_efectivos(self):
        from django.db import transaction
        for codigo in ("OT_GESTIONAR", "TICKET_ATENDER"):
            with self.subTest(codigo=codigo), transaction.atomic():
                RolPermiso.objects.filter(permiso__codigo=codigo).delete()
                self.assertEqual(self.post().status_code, 403)
                self.assertFalse(CierreTecnico.objects.exists())
                transaction.set_rollback(True)

    def test_tecnico_inactivo(self):
        self.segundo.activo = False; self.segundo.save(update_fields=["activo"])
        self.assertEqual(self.post().status_code, 403)
        self.assertFalse(CierreTecnico.objects.exists())

    def test_bearer_valido_sin_csrf(self):
        with patch("usuarios.authentication.validar_access_token", return_value={"sub": "tecnico-prueba"}), patch(
            "usuarios.authentication.resolver_usuario_access_token", return_value=self.segundo
        ):
            respuesta = self.cliente(csrf=True).post(self.url, self.datos, format="json", HTTP_AUTHORIZATION="Bearer credencial-de-prueba")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(CierreTecnico.objects.get().id_tecnico_id, self.segundo.pk)

    def test_bearer_invalido(self):
        with patch("usuarios.authentication.validar_access_token", side_effect=AuthenticationFailed("Token inválido")):
            respuesta = self.cliente().post(self.url, self.datos, format="json", HTTP_AUTHORIZATION="Bearer invalido")
        self.assertEqual(respuesta.status_code, 401)
        self.assertFalse(CierreTecnico.objects.exists())

    def test_csrf_sesion(self):
        cliente = self.cliente(self.segundo, csrf=True)
        self.assertEqual(cliente.post(self.url, self.datos, format="json").status_code, 403)
        UsuarioRol.objects.create(usuario=self.segundo, rol=Rol.objects.get(nombre="Usuario solicitante"))
        cliente.get("/")
        respuesta = cliente.post(self.url, self.datos, format="json", HTTP_X_CSRFTOKEN=cliente.cookies["csrftoken"].value)
        self.assertEqual(respuesta.status_code, 200, respuesta.data)

    def test_ot_inexistente_y_id_invalido(self):
        cliente = self.cliente(self.segundo)
        self.assertEqual(cliente.post("/api/ordenes-trabajo/2147483647/completar/", self.datos, format="json").status_code, 404)
        self.assertEqual(cliente.post("/api/ordenes-trabajo/0/completar/", self.datos, format="json").status_code, 400)

    def test_ot_pausada(self):
        pausar_orden_trabajo(self.orden.pk, self.tecnico, "Esperando")
        antes = self.foto()
        self.assertEqual(self.post().status_code, 400)
        self.assertEqual(self.foto(), antes)

    def test_segundo_cierre_no_duplica_efectos(self):
        self.assertEqual(self.post().status_code, 200)
        antes = self.foto()
        self.assertEqual(self.post().status_code, 400)
        self.assertEqual(self.foto(), antes)

    def test_ticket_resuelto_o_cerrado(self):
        for estado in ("Resuelto", "Cerrado"):
            self.origen(estado)
            antes = self.foto()
            self.assertEqual(self.post().status_code, 400)
            self.assertEqual(self.foto(), antes)

    def test_no_omite_validacion_estado_del_activo(self):
        from activos.models import EstadoActivo
        self.activo_ot.id_estado_activo = EstadoActivo.objects.get(nombre="Disponible")
        self.activo_ot.save(update_fields=["id_estado_activo"])
        antes = self.foto()
        self.assertEqual(self.post().status_code, 400)
        self.assertEqual(self.foto(), antes)

    def test_rollback_error_interno(self):
        antes = self.foto()
        with patch("ordenes_trabajo.cierre.registrar_notificacion", side_effect=RuntimeError("Fallo instrumental")):
            with self.assertRaises(RuntimeError): self.post()
        self.assertEqual(self.foto(), antes)

    @override_settings(DEBUG=False)
    def test_500_no_expone_detalles_internos(self):
        cliente = self.cliente(self.segundo)
        cliente.raise_request_exception = False
        with patch("ordenes_trabajo.views.cerrar_orden_trabajo", side_effect=RuntimeError("SQL_PRIVADO_PRUEBA")):
            respuesta = cliente.post(self.url, self.datos, format="json")
        self.assertEqual(respuesta.status_code, 500)
        self.assertNotIn(b"SQL_PRIVADO_PRUEBA", respuesta.content)
