"""Eliminación protegida, acceso de cuentas e historial con PostgreSQL real."""
from unittest.mock import Mock, patch

from activos.models import Activo, EstadoActivo
from asignaciones.models import HistorialEstadoActivo
from tickets.models import Ticket
from tickets.services import crear_ticket
from usuarios.models import BitacoraAuditoria, Usuario, UsuarioRol
from usuarios.services import Auth0ManagementError, eliminar_usuario_auth0
from usuarios.tests.test_integracion_postgresql import PostgreSQLTestBase


class AdministracionRegistrosPostgreSQLTests(PostgreSQLTestBase):
    def test_eliminar_activo_sin_movimientos_audita_y_no_reutiliza_codigo(self):
        activo = self.activo()
        codigo = activo.codigo_inventario
        pk = activo.pk
        cliente = self.cliente(self.admin)
        r = cliente.delete(f"/api/activos/{pk}/")
        self.assertEqual(r.status_code, 204, getattr(r, "data", None))
        self.assertFalse(Activo.objects.filter(pk=pk).exists())
        self.assertTrue(BitacoraAuditoria.objects.filter(accion="ACTIVO_ELIMINADO", id_registro_afectado=pk).exists())
        r = cliente.post("/api/activos/", {"numero_serie": "NUEVO-123", "id_modelo": self.modelo.pk, "id_ubicacion": self.ubicacion.pk}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertNotEqual(r.data["codigo_inventario"], codigo)

    def test_eliminar_activo_no_existe_devuelve_404(self):
        self.assertEqual(self.cliente(self.admin).delete("/api/activos/99999/").status_code, 404)

    def test_eliminar_activo_asignado_se_bloquea(self):
        activo, _ = self.entregar()
        self.assertEqual(self.cliente(self.admin).delete(f"/api/activos/{activo.pk}/").status_code, 409)
        self.assertTrue(Activo.objects.filter(pk=activo.pk).exists())

    def test_eliminar_activo_con_ticket_no_desvincula_el_ticket(self):
        activo = self.activo()
        ticket = crear_ticket(solicitante=self.solicitante, asunto="Incidente", descripcion="Descripción de prueba", id_activo=activo.pk)
        r = self.cliente(self.admin).delete(f"/api/activos/{activo.pk}/")
        self.assertEqual(r.status_code, 409, r.data)
        self.assertEqual(Ticket.objects.get(pk=ticket.pk).id_activo_id, activo.pk)

    def test_historial_conserva_cambio_administrativo_y_bloquea_el_borrado(self):
        activo = self.activo()
        cliente = self.cliente(self.admin)
        estado = EstadoActivo.objects.get(nombre="En revisión")
        r = cliente.patch(f"/api/activos/{activo.pk}/", {"id_estado_activo": estado.pk}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        cambio = HistorialEstadoActivo.objects.get(id_activo=activo)
        assert cambio.id_usuario is not None
        self.assertEqual(cambio.id_usuario.pk, self.admin.pk)
        self.assertEqual(cambio.id_estado_activo.pk, estado.pk)
        r = cliente.get("/api/activos/historial/", {"search": activo.codigo_inventario})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["movimientos"][0]["tipo"], "cambio_estado")
        self.assertEqual(cliente.delete(f"/api/activos/{activo.pk}/").status_code, 409)
        self.assertTrue(HistorialEstadoActivo.objects.filter(pk=cambio.pk).exists())

    def test_historial_de_equipo_sin_movimientos_no_inventa_eventos(self):
        activo = self.activo()
        r = self.cliente(self.admin).get("/api/activos/historial/", {"search": activo.codigo_inventario})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["total_movimientos"], 0)

    def test_eliminar_usuario_sin_actividad_elimina_roles_e_identidad_y_audita(self):
        pk = self.otro.pk
        with patch("usuarios.administracion.eliminar_usuario_auth0", return_value=True) as externa:
            r = self.cliente(self.admin).delete(f"/api/usuarios/{pk}/")
        self.assertEqual(r.status_code, 204, getattr(r, "data", None))
        externa.assert_called_once_with(self.otro.identificador_externo)
        self.assertFalse(Usuario.objects.filter(pk=pk).exists())
        self.assertFalse(UsuarioRol.objects.filter(usuario_id=pk).exists())
        self.assertTrue(BitacoraAuditoria.objects.filter(accion="USUARIO_ELIMINADO", id_registro_afectado=pk).exists())

    def test_fallo_auth0_revierte_eliminacion_roles_y_auditoria_local(self):
        pk = self.otro.pk
        with patch("usuarios.administracion.eliminar_usuario_auth0", side_effect=Auth0ManagementError("No disponible")):
            r = self.cliente(self.admin).delete(f"/api/usuarios/{pk}/")
        self.assertEqual(r.status_code, 502, r.data)
        self.assertTrue(Usuario.objects.filter(pk=pk, activo=True).exists())
        self.assertTrue(UsuarioRol.objects.filter(usuario_id=pk).exists())
        self.assertFalse(BitacoraAuditoria.objects.filter(accion="USUARIO_ELIMINADO").exists())

    def test_usuario_con_actividad_no_se_elimina_pero_puede_desactivarse(self):
        self.entregar()
        pk = self.tecnico.pk
        cliente_tecnico = self.cliente(self.tecnico)
        with patch("usuarios.administracion.eliminar_usuario_auth0") as externa:
            r = self.cliente(self.admin).delete(f"/api/usuarios/{pk}/")
        self.assertEqual(r.status_code, 409, r.data)
        externa.assert_not_called()
        r = self.cliente(self.admin).patch(f"/api/usuarios/{pk}/", {"activo": False}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(Usuario.objects.get(pk=pk).activo)
        self.assertTrue(UsuarioRol.objects.filter(usuario_id=pk).exists())
        self.assertIn(cliente_tecnico.get("/api/activos/").status_code, (401, 403))
        self.assertTrue(BitacoraAuditoria.objects.filter(accion="USUARIO_DESACTIVADO").exists())
        r = self.cliente(self.admin).patch(f"/api/usuarios/{pk}/", {"activo": True}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(cliente_tecnico.get("/api/activos/").status_code, 200)

    def test_no_puede_eliminar_ni_desactivar_su_propia_cuenta(self):
        cliente = self.cliente(self.admin)
        pk = self.admin.pk
        with patch("usuarios.administracion.eliminar_usuario_auth0") as externa:
            self.assertEqual(cliente.delete(f"/api/usuarios/{pk}/").status_code, 409)
        externa.assert_not_called()
        self.assertEqual(cliente.patch(f"/api/usuarios/{pk}/", {"activo": False}, format="json").status_code, 409)
        self.assertTrue(Usuario.objects.get(pk=pk).activo)

    def test_rbac_no_confia_en_roles_de_sesion(self):
        activo = self.activo()
        with patch("usuarios.administracion.eliminar_usuario_auth0") as externa:
            for usuario in (None, self.tecnico, self.solicitante):
                cliente = self.cliente(usuario)
                self.assertIn(cliente.delete(f"/api/activos/{activo.pk}/").status_code, (401, 403))
                self.assertIn(cliente.delete(f"/api/usuarios/{self.otro.pk}/").status_code, (401, 403))
                self.assertIn(cliente.patch(f"/api/usuarios/{self.otro.pk}/", {"activo": False}, format="json").status_code, (401, 403))
        externa.assert_not_called()
        self.assertTrue(Activo.objects.filter(pk=activo.pk).exists())
        self.assertTrue(Usuario.objects.get(pk=self.otro.pk).activo)

    def test_estado_de_usuario_exige_booleano_y_usuario_existente(self):
        cliente = self.cliente(self.admin)
        self.assertEqual(cliente.patch(f"/api/usuarios/{self.otro.pk}/", {"activo": "invalido"}, format="json").status_code, 400)
        self.assertEqual(cliente.patch("/api/usuarios/99999/", {"activo": False}, format="json").status_code, 404)
        self.assertEqual(cliente.delete("/api/usuarios/99999/").status_code, 404)

    def test_escrituras_desde_sesion_web_exigen_csrf(self):
        activo = self.activo()
        cliente = self.cliente(self.admin, csrf=True)
        self.assertEqual(cliente.delete(f"/api/activos/{activo.pk}/").status_code, 403)
        self.assertEqual(cliente.delete(f"/api/usuarios/{self.otro.pk}/").status_code, 403)
        self.assertEqual(cliente.patch(f"/api/usuarios/{self.otro.pk}/", {"activo": False}, format="json").status_code, 403)

    def test_identidad_externa_inexistente_permite_reintentar_la_baja(self):
        with patch("usuarios.services.obtener_token_management_api", return_value="token-prueba"), patch("usuarios.services.requests.delete", return_value=Mock(status_code=404)):
            self.assertTrue(eliminar_usuario_auth0("auth0|prueba-inexistente"))
