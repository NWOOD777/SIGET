"""Identificación administrativa sin exposición del RUT en consultas operativas."""
from unittest.mock import patch

from usuarios.models import BitacoraAuditoria, Usuario
from usuarios.tests.test_integracion_postgresql import PostgreSQLTestBase


class IdentificacionAdministrativaTests(PostgreSQLTestBase):
    def test_administrador_consulta_el_rut_en_la_ficha_pero_no_en_listados(self):
        cliente = self.cliente(self.admin)
        r = cliente.get(f"/api/usuarios/{self.solicitante.pk}/acceso/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["rut"], self.solicitante.rut)
        self.assertIn("no-store", r["Cache-Control"])
        for ruta in ("/api/usuarios/", "/api/usuarios/me/"):
            r = cliente.get(ruta)
            self.assertEqual(r.status_code, 200)
            self.assertNotIn(self.solicitante.rut, r.content.decode())
            self.assertNotIn('"rut"', r.content.decode())

    def test_tecnico_y_solicitante_no_acceden_a_la_ficha_administrativa(self):
        for persona in (self.tecnico, self.solicitante, self.otro):
            r = self.cliente(persona).get(f"/api/usuarios/{self.solicitante.pk}/acceso/")
            self.assertEqual(r.status_code, 403)

    def test_aprovisionamiento_registra_rut_sin_copiarlo_en_auditoria(self):
        datos = {"nombres": "Cuenta", "apellidos": "Institucional", "correo": "nueva@example.invalid", "rut": "22.222.222-2", "rol": "Usuario solicitante"}
        with patch("usuarios.services.crear_usuario_auth0", return_value={"user_id": "auth0|nueva"}), patch("usuarios.services.solicitar_recuperacion_acceso", return_value=True):
            r = self.cliente(self.admin).post("/api/usuarios/aprovisionar/", datos, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        persona = Usuario.objects.get(correo=datos["correo"])
        self.assertEqual(persona.rut, "22222222-2")
        evento = BitacoraAuditoria.objects.get(accion="APROVISIONAR_USUARIO")
        self.assertNotIn(persona.rut, evento.detalle_evento)
        self.assertNotIn(datos["rut"], evento.detalle_evento)

    def test_tickets_asignaciones_y_auditoria_no_devuelven_rut(self):
        self.entregar()
        BitacoraAuditoria.objects.create(id_usuario=self.admin, modulo="USUARIOS", accion="REGISTRO", entidad_afectada="usuario", detalle_evento="Identificador: 12.345.678-5")
        for ruta in ("/api/tickets/", "/api/solicitudes-asignacion/", "/api/asignaciones/", "/api/auditoria/"):
            r = self.cliente(self.admin).get(ruta)
            self.assertEqual(r.status_code, 200, (ruta, r.data))
            self.assertNotIn('"rut"', r.content.decode())
            self.assertNotIn("12.345.678-5", r.content.decode())

    def test_acceso_y_perfil_no_solicitan_registro_ni_consentimiento(self):
        cliente = self.cliente(self.solicitante)
        self.assertEqual(cliente.get("/").status_code, 200)
        r = cliente.get("/perfil/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, self.solicitante.rut)
        self.assertNotContains(r, self.otro.rut)
        self.assertContains(r, "contacta al Administrador del sistema")
        r = cliente.get("/perfil/", {"id_usuario": self.otro.pk})
        self.assertContains(r, self.solicitante.rut)
        self.assertNotContains(r, self.otro.rut)
        for ruta in ("/privacidad/", "/api/usuarios/privacidad/", "/api/usuarios/me/rut/"):
            self.assertEqual(cliente.get(ruta).status_code, 404)
            self.assertEqual(cliente.post(ruta, {}, format="json").status_code, 404)

    def test_correccion_conserva_cuenta_movimientos_y_no_duplica_auditoria(self):
        _, asignacion = self.entregar()
        cliente = self.cliente(self.admin)
        ruta = f"/api/usuarios/{self.solicitante.pk}/identificacion/"
        for _ in range(2):
            r = cliente.patch(ruta, {"rut": "22.222.222-2"}, format="json")
            self.assertEqual(r.status_code, 200, r.data)
            self.assertEqual(r.data["rut"], "22222222-2")
            self.assertIn("no-store", r["Cache-Control"])
        self.solicitante.refresh_from_db()
        self.assertEqual(self.solicitante.rut, "22222222-2")
        r = cliente.get(f"/api/asignaciones/{asignacion}/")
        self.assertEqual(r.status_code, 200, r.data)
        eventos = BitacoraAuditoria.objects.filter(accion="IDENTIFICACION_USUARIO_ACTUALIZADA")
        self.assertEqual(eventos.count(), 1)
        evento = eventos.get()
        self.assertEqual(evento.id_registro_afectado, self.solicitante.pk)
        self.assertEqual(evento.id_usuario, self.admin)
        self.assertNotIn("22222222", evento.detalle_evento)

    def test_correccion_valida_campos_duplicados_permisos_y_csrf(self):
        ruta = f"/api/usuarios/{self.solicitante.pk}/identificacion/"
        for persona in (self.tecnico, self.solicitante, None):
            r = self.cliente(persona).patch(ruta, {"rut": "22.222.222-2"}, format="json")
            self.assertIn(r.status_code, (401, 403))
        r = self.cliente(self.admin, csrf=True).patch(ruta, {"rut": "22.222.222-2"}, format="json")
        self.assertEqual(r.status_code, 403)
        cliente = self.cliente(self.admin)
        for datos in ({}, {"rut": ""}, {"rut": "12.345.678-0"}, {"rut": "texto"}):
            self.assertEqual(cliente.patch(ruta, datos, format="json").status_code, 400)
        self.otro.rut = "22222222-2"
        self.otro.save(update_fields=["rut"])
        self.assertEqual(cliente.patch(ruta, {"rut": "22.222.222-2"}, format="json").status_code, 409)
        self.assertEqual(cliente.patch("/api/usuarios/99999/identificacion/", {"rut": "11.111.111-1"}, format="json").status_code, 404)
        self.assertFalse(BitacoraAuditoria.objects.filter(accion="IDENTIFICACION_USUARIO_ACTUALIZADA").exists())
