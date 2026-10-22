"""Pruebas de integración con PostgreSQL y simulación de la API de Auth0."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Any, cast
from unittest.mock import Mock, patch

from django.db import DatabaseError, connection, connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from activos.models import Activo, CategoriaActivo, EstadoActivo, Marca, ModeloActivo, Ubicacion
from asignaciones.models import Asignacion, DevolucionActivo, SolicitudAsignacion
from asignaciones.services import (
    aprobar_solicitud_asignacion,
    crear_solicitud_asignacion,
    rechazar_solicitud_asignacion,
    registrar_entrega_asignacion,
)
from siget.testing import cargar_esquema_pruebas
from tickets.models import Ticket
from tickets.services import crear_ticket
from usuarios.models import BitacoraAuditoria, Permiso, Rol, RolPermiso, Usuario, UsuarioRol
from usuarios.services import UsuarioInactivoError, vincular_o_obtener_usuario


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"], SIGET_PUBLIC_URL="")
class PostgreSQLTestBase(TransactionTestCase):
    @classmethod
    def _fixture_setup(cls):
        getattr(super(), "_fixture_setup")()
        # flush de Django no administra los modelos managed=False.
        cargar_esquema_pruebas()

    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        self.admin = self.usuario(1, "Administrador del sistema")
        self.tecnico = self.usuario(2, "Técnico de soporte")
        self.solicitante = self.usuario(3, "Usuario solicitante")
        self.otro = self.usuario(4, "Usuario solicitante")
        self.categoria = CategoriaActivo.objects.get(nombre="Notebook")
        self.modelo = ModeloActivo.objects.create(id_categoria=self.categoria, id_marca=Marca.objects.get(pk=1), nombre="Modelo de prueba")
        self.ubicacion = Ubicacion.objects.get(pk=1)
        self.secuencia = 0

    def usuario(self, n, rol):
        u = Usuario.objects.create(identificador_externo=f"audit|{n}", proveedor_identidad="Auth0", rut=f"{n:08d}-0", nombres="Prueba", apellidos=str(n), correo=f"prueba{n}@example.invalid")
        UsuarioRol.objects.create(usuario=u, rol=Rol.objects.get(nombre=rol))
        return u

    def cliente(self, usuario=None, csrf=False) -> Any:
        c = APIClient(enforce_csrf_checks=csrf)
        if usuario:
            session = c.session
            session["siget_usuario_id"] = usuario.pk
            session["roles"] = ["Administrador del sistema"]  # No debe otorgar privilegios.
            session.save()
        return c

    def activo(self):
        self.secuencia += 1
        return Activo.objects.create(codigo_inventario=f"ACT-{self.secuencia:04d}", numero_serie=f"SERIE-{self.secuencia}", id_modelo=self.modelo, id_ubicacion=self.ubicacion, id_estado_activo=EstadoActivo.objects.get(nombre="Disponible"), valor_adquisicion=100)

    def preparar_entrega(self):
        activo = self.activo()
        r = self.cliente(self.solicitante).post("/api/solicitudes-asignacion/", {"id_categoria": self.categoria.pk, "motivo": "Actividades de prueba"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        sid = r.data["id_solicitud"]
        r = self.cliente(self.admin).post(f"/api/solicitudes-asignacion/{sid}/aprobar/", {}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        return activo, sid

    def entregar(self):
        activo, sid = self.preparar_entrega()
        r = self.cliente(self.tecnico).post(f"/api/solicitudes-asignacion/{sid}/entregar/", {"id_activo": activo.pk}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        return activo, r.data["id_asignacion"]


class IntegracionPostgreSQLTests(PostgreSQLTestBase):
    def test_ddl_y_catalogos_reales(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' AND table_name NOT LIKE 'django_%' AND table_name NOT LIKE 'auth_%'")
            self.assertEqual(cursor.fetchone()[0], 34)
        self.assertEqual(Rol.objects.count(), 3)
        self.assertTrue(Permiso.objects.exists())
        self.assertEqual(self.cliente(self.solicitante).get("/api/tickets/sla/").status_code, 200)

    def test_ciclo_asignacion_devolucion_persistido(self):
        activo, aid = self.entregar()
        r = self.cliente(self.tecnico).post(f"/api/asignaciones/{aid}/devolucion/", {"condicion_fisica": "Buen estado"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        activo.refresh_from_db()
        self.assertEqual(activo.id_estado_activo.nombre, "Disponible")
        self.assertEqual(Asignacion.objects.get(pk=aid).id_estado_asignacion.nombre, "Finalizada")
        self.assertEqual(DevolucionActivo.objects.count(), 1)
        self.assertEqual(BitacoraAuditoria.objects.count(), 4)

    def test_solicitud_sin_stock_y_categoria_invalida(self):
        c = self.cliente(self.solicitante)
        for categoria in [self.categoria.pk, 99999]:
            r = c.post("/api/solicitudes-asignacion/", {"id_categoria": categoria, "motivo": "Sin stock"}, format="json")
            self.assertEqual(r.status_code, 400)
        self.assertFalse(SolicitudAsignacion.objects.exists())

    def test_admin_no_crea_solicitudes_ni_entrega(self):
        activo, sid = self.preparar_entrega()
        c = self.cliente(self.admin)
        self.assertEqual(c.post("/api/solicitudes-asignacion/", {"id_categoria": self.categoria.pk, "motivo": "No autorizado"}, format="json").status_code, 403)
        self.assertEqual(c.post(f"/api/solicitudes-asignacion/{sid}/entregar/", {"id_activo": activo.pk}, format="json").status_code, 403)
        self.assertFalse(Asignacion.objects.exists())

    def test_admin_no_devuelve_y_solicitante_no_aprueba(self):
        activo, aid = self.entregar()
        self.assertEqual(self.cliente(self.admin).post(f"/api/asignaciones/{aid}/devolucion/", {"condicion_fisica": "Buen estado"}, format="json").status_code, 403)
        sid = getattr(Asignacion.objects.get(pk=aid), "id_solicitud_id")
        self.assertEqual(self.cliente(self.solicitante).post(f"/api/solicitudes-asignacion/{sid}/aprobar/", {}, format="json").status_code, 403)

    def test_entrega_directa_valida_y_datos_invalidos(self):
        activo, sid = self.preparar_entrega()
        c = self.cliente(self.tecnico)
        for payload in [{"id_solicitud": "abc", "id_activo": activo.pk}, {"id_solicitud": sid, "id_activo": "abc"}, {"id_solicitud": sid, "id_activo": activo.pk, "fecha_devolucion_prevista": "no-fecha"}, [], {"id_solicitud": -1, "id_activo": activo.pk}]:
            self.assertEqual(c.post("/api/asignaciones/", payload, format="json").status_code, 400)
        r = c.post("/api/asignaciones/", {"id_solicitud": sid, "id_activo": activo.pk}, format="json")
        self.assertEqual(r.status_code, 201, r.data)

    def test_fecha_de_entrega_incoherente_rechazada_sin_escrituras(self):
        activo, sid = self.preparar_entrega()
        for path in ["/api/asignaciones/", f"/api/solicitudes-asignacion/{sid}/entregar/"]:
            r = self.cliente(self.tecnico).post(path, {"id_solicitud": sid, "id_activo": activo.pk, "fecha_devolucion_prevista": "2000-01-01T12:00:00Z"}, format="json")
            self.assertEqual(r.status_code, 400, r.data)
        self.assertFalse(Asignacion.objects.exists())

    def test_resolucion_con_instancia_desactualizada_no_sobrescribe(self):
        self.activo()
        s = crear_solicitud_asignacion(self.solicitante, self.categoria.pk, "Prueba")
        previa = SolicitudAsignacion.objects.get(pk=s.pk)
        aprobar_solicitud_asignacion(s, self.admin)
        from rest_framework.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            rechazar_solicitud_asignacion(previa, self.admin, "Lectura anterior")
        self.assertEqual(SolicitudAsignacion.objects.get(pk=s.pk).id_estado_solicitud.nombre, "Aprobada")

    def test_devolucion_reutiliza_ticket_previo(self):
        activo, aid = self.entregar()
        t = crear_ticket(self.solicitante, "Falla previa", "No enciende", id_activo=activo.pk)
        r = self.cliente(self.tecnico).post(f"/api/asignaciones/{aid}/devolucion/", {"condicion_fisica": "Con falla técnica"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Ticket.objects.count(), 1)
        self.assertIn(t.codigo_ticket, BitacoraAuditoria.objects.get(accion="DEVOLUCION_REGISTRADA").detalle_evento)

    def test_devolucion_rechaza_ticket_ajeno_y_cerrado(self):
        activo, aid = self.entregar()
        ajeno = crear_ticket(self.otro, "Ajeno", "Otro usuario")
        c = self.cliente(self.tecnico)
        r = c.post(f"/api/asignaciones/{aid}/devolucion/", {"condicion_fisica": "Con falla técnica", "id_ticket_asociado": ajeno.pk}, format="json")
        self.assertEqual(r.status_code, 400, r.data)
        self.assertFalse(DevolucionActivo.objects.exists())
        self.assertIsNone(Asignacion.objects.get(pk=aid).fecha_finalizacion)
        from tickets.models import EstadoTicket
        cerrado = crear_ticket(self.solicitante, "Cerrado", "Anterior", id_activo=activo.pk)
        cerrado.id_estado_ticket = EstadoTicket.objects.get(nombre="Cerrado")
        cerrado.save()
        r = c.post(f"/api/asignaciones/{aid}/devolucion/", {"condicion_fisica": "Con falla técnica", "id_ticket_asociado": cerrado.pk}, format="json")
        self.assertEqual(r.status_code, 400, r.data)
        self.assertFalse(DevolucionActivo.objects.exists())

    def test_devolucion_con_dano_crea_ticket_y_conserva_observacion(self):
        activo, aid = self.entregar()
        r = self.cliente(self.tecnico).post(f"/api/asignaciones/{aid}/devolucion/", {"condicion_fisica": "Con daño físico", "observaciones": "Pantalla dañada"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(getattr(Ticket.objects.get(), "id_activo_id"), activo.pk)
        self.assertEqual(DevolucionActivo.objects.get().observaciones, "Pantalla dañada")
        activo.refresh_from_db()
        self.assertEqual(activo.id_estado_activo.nombre, "En revisión")

    def test_csrf_token_ausente_invalido_origen_ajeno_y_valido(self):
        c = self.cliente(self.solicitante, csrf=True)
        payload = {"asunto": "Incidente", "descripcion": "Descripción"}
        self.assertEqual(c.post("/api/tickets/", payload).status_code, 403)
        self.assertEqual(c.post("/api/tickets/", payload, HTTP_X_CSRFTOKEN="invalido").status_code, 403)
        c.get("/")
        token = c.cookies["csrftoken"].value
        self.assertEqual(c.post("/api/tickets/", payload, HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN="https://example.invalid").status_code, 403)
        self.assertEqual(c.post("/api/tickets/", payload, HTTP_X_CSRFTOKEN=token).status_code, 201)

    def test_aislamiento_y_anonimos(self):
        activo, aid = self.entregar()
        sid = getattr(Asignacion.objects.get(pk=aid), "id_solicitud_id")
        t = crear_ticket(self.solicitante, "Privado", "Incidente")
        c = self.cliente(self.otro)
        for path in [f"/api/asignaciones/{aid}/", f"/api/solicitudes-asignacion/{sid}/", f"/api/tickets/{t.pk}/"]:
            self.assertEqual(c.get(path).status_code, 403)
        for path in ["/api/asignaciones/", "/api/tickets/", "/api/solicitudes-asignacion/"]:
            self.assertEqual(c.get(path, {"usuario": self.solicitante.pk}).data, [])
            self.assertEqual(self.cliente().get(path).status_code, 403)

    def test_rollback_real_si_falla_auditoria_entrega(self):
        activo, sid = self.preparar_entrega()
        with patch("asignaciones.services.registrar_auditoria", side_effect=DatabaseError("Fallo inducido")):
            with self.assertRaises(DatabaseError):
                registrar_entrega_asignacion(SolicitudAsignacion.objects.get(pk=sid), activo.pk, self.tecnico)
        self.assertFalse(Asignacion.objects.exists())
        activo.refresh_from_db()
        self.assertEqual(activo.id_estado_activo.nombre, "Disponible")

    def test_tickets_distinguen_incidentes_y_bloquean_repetidos(self):
        a, _ = self.entregar()
        c = self.cliente(self.solicitante)
        for asunto in ["Pantalla", "VPN"]:
            self.assertEqual(c.post("/api/tickets/", {"asunto": asunto, "descripcion": asunto, "id_activo": a.pk}, format="json").status_code, 201)
        self.assertEqual(c.post("/api/tickets/", {"asunto": "VPN", "descripcion": "Repetido", "id_activo": a.pk}, format="json").status_code, 400)

    def test_activo_registro_edicion_y_auditoria(self):
        c = self.cliente(self.admin)
        payload = {"numero_serie": "NUEVO", "id_modelo": self.modelo.pk, "id_ubicacion": self.ubicacion.pk, "valor_adquisicion": 100}
        r = c.post("/api/activos/", payload, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        a = Activo.objects.get(pk=r.data["id_activo"])
        codigo = a.codigo_inventario
        r = c.patch(f"/api/activos/{a.pk}/", {"codigo_inventario": "NO-CAMBIAR", "id_activo": 999, "numero_serie": "NUEVO-EDITADO"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        a.refresh_from_db()
        self.assertEqual(a.codigo_inventario, codigo)
        self.assertEqual(a.numero_serie, "NUEVO-EDITADO")
        self.assertEqual(BitacoraAuditoria.objects.filter(entidad_afectada="activo").count(), 2)

    def test_activo_rechaza_garantia_antes_de_compra_en_creacion_y_patch(self):
        c = self.cliente(self.admin)
        payload = {"numero_serie": "FECHAS", "id_modelo": self.modelo.pk, "id_ubicacion": self.ubicacion.pk, "fecha_compra": "2026-10-10", "fecha_garantia": "2026-10-09"}
        self.assertEqual(c.post("/api/activos/", payload, format="json").status_code, 400)
        a = self.activo()
        a.fecha_compra = timezone.localdate()
        a.save()
        r = c.patch(f"/api/activos/{a.pk}/", {"fecha_garantia": "2000-01-01"}, format="json")
        self.assertEqual(r.status_code, 400, r.data)

    def test_activo_duplicado_campos_obligatorios_y_rbac(self):
        a = self.activo()
        payload = {"numero_serie": a.numero_serie, "id_modelo": self.modelo.pk, "id_ubicacion": self.ubicacion.pk}
        self.assertEqual(self.cliente(self.admin).post("/api/activos/", payload, format="json").status_code, 400)
        self.assertEqual(self.cliente(self.admin).post("/api/activos/", {}, format="json").status_code, 400)
        for u in [self.tecnico, self.solicitante]:
            self.assertEqual(self.cliente(u).post("/api/activos/", payload, format="json").status_code, 403)
            self.assertEqual(self.cliente(u).patch(f"/api/activos/{a.pk}/", {"numero_serie": "HACK"}, format="json").status_code, 403)

    def test_activo_asignado_no_se_libera_mediante_patch(self):
        a, aid = self.entregar()
        r = self.cliente(self.admin).patch(f"/api/activos/{a.pk}/", {"id_estado_activo": EstadoActivo.objects.get(nombre="Disponible").pk}, format="json")
        self.assertEqual(r.status_code, 400, r.data)
        a.refresh_from_db()
        self.assertEqual(a.id_estado_activo.nombre, "Asignado")

    def test_inventario_busquedas_filtros_y_sin_resultados(self):
        a = self.activo()
        c = self.cliente(self.admin)
        for params in [{"search": a.numero_serie}, {"search": a.codigo_inventario}, {"tipo": self.categoria.nombre, "estado": "Disponible", "ubicacion": self.ubicacion.pk}]:
            r = c.get("/api/activos/", params)
            self.assertEqual(r.status_code, 200)
            self.assertEqual([v["id_activo"] for v in r.data], [a.pk])
        self.assertEqual(c.get("/api/activos/", {"search": "INEXISTENTE"}).data, [])

    def test_aprovisionamiento_postgresql_y_rbac_con_frontera_auth0_simulada(self):
        payload = {"nombres": "Nuevo", "apellidos": "Usuario", "correo": "nuevo@example.invalid", "rut": "12.345.678-5", "rol": "Usuario solicitante"}
        with patch("usuarios.services.crear_usuario_auth0", return_value={"user_id": "auth0|nuevo"}) as externo, patch("usuarios.services.solicitar_recuperacion_acceso", return_value=True):
            r = self.cliente(self.admin).post("/api/usuarios/aprovisionar/", payload, format="json")
            self.assertEqual(r.status_code, 201, r.data)
            nuevo = Usuario.objects.get(correo=payload["correo"])
            self.assertEqual(nuevo.identificador_externo, "auth0|nuevo")
            self.assertEqual(UsuarioRol.objects.get(usuario=nuevo).rol.nombre, payload["rol"])
            self.assertEqual(self.cliente(self.admin).post("/api/usuarios/aprovisionar/", payload, format="json").status_code, 409)
            externo.assert_called_once()

    def test_roles_permisos_efectivos_y_prohibicion_de_escalada(self):
        c = self.cliente(self.admin)
        rol = Rol.objects.get(nombre="Usuario solicitante")
        permiso = Permiso.objects.get(codigo="OT_GESTIONAR")
        r = c.post(f"/api/usuarios/roles/{rol.pk}/permisos/", {"id_permiso": permiso.pk}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(RolPermiso.objects.filter(rol=rol, permiso=permiso).exists())
        r = c.get(f"/api/usuarios/{self.solicitante.pk}/acceso/")
        self.assertIn("OT_GESTIONAR", [p["codigo"] for p in r.data["permisos_efectivos"]])
        self.assertEqual(c.delete(f"/api/usuarios/roles/{rol.pk}/permisos/{permiso.pk}/").status_code, 200)
        self.assertTrue(Permiso.objects.filter(pk=permiso.pk).exists())
        self.assertEqual(self.cliente(self.tecnico).post(f"/api/usuarios/{self.tecnico.pk}/roles/", {"roles": ["Administrador del sistema"]}, format="json").status_code, 403)

    def test_metodos_de_permisos_rbac_respetan_su_ruta(self):
        c = self.cliente(self.admin)
        rol = Rol.objects.get(nombre="Usuario solicitante")
        permiso = Permiso.objects.get(codigo="CATALOGO_CONSULTAR")
        lista = f"/api/usuarios/roles/{rol.pk}/permisos/"
        detalle = f"{lista}{permiso.pk}/"
        self.assertEqual(c.delete(lista).status_code, 405)
        self.assertEqual(c.post(detalle, {"id_permiso": permiso.pk}, format="json").status_code, 405)
        self.assertTrue(RolPermiso.objects.filter(rol=rol, permiso=permiso).exists())
        self.assertEqual(c.options(lista)["Allow"], "POST, OPTIONS")
        self.assertEqual(c.options(detalle)["Allow"], "DELETE, OPTIONS")

    def test_retiro_del_unico_rol_y_cambios_de_rol(self):
        c = self.cliente(self.admin)
        rol = Rol.objects.get(nombre="Usuario solicitante")
        self.assertEqual(c.delete(f"/api/usuarios/{self.solicitante.pk}/roles/{rol.pk}/").status_code, 400)
        r = c.post(f"/api/usuarios/{self.otro.pk}/roles/", {"roles": ["Técnico de soporte"]}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(UsuarioRol.objects.get(usuario=self.otro).rol.nombre, "Técnico de soporte")
        r = c.post(f"/api/usuarios/{self.otro.pk}/roles/", {"roles": ["Técnico de soporte", "Usuario solicitante"]}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(c.delete(f"/api/usuarios/{self.otro.pk}/roles/{rol.pk}/").status_code, 200)
        self.assertEqual(UsuarioRol.objects.get(usuario=self.otro).rol.nombre, "Técnico de soporte")

    def test_aprovisionamiento_revierte_sql_y_compensa_auth0(self):
        payload = {"nombres": "Nuevo", "apellidos": "Usuario", "correo": "rollback@example.invalid", "rut": "12.345.678-5", "rol": "Usuario solicitante"}
        with patch("usuarios.services.crear_usuario_auth0", return_value={"user_id": "auth0|rollback"}), patch("usuarios.services.registrar_auditoria", side_effect=DatabaseError("Fallo SQL inducido")), patch("usuarios.services.eliminar_usuario_auth0", return_value=True) as compensar:
            r = self.cliente(self.admin).post("/api/usuarios/aprovisionar/", payload, format="json")
        self.assertEqual(r.status_code, 500)
        self.assertFalse(Usuario.objects.filter(correo=payload["correo"]).exists())
        compensar.assert_called_once_with("auth0|rollback")

    def test_compensacion_fallida_no_se_informa_como_exitosa(self):
        payload = {"nombres": "Nuevo", "apellidos": "Usuario", "correo": "rollback@example.invalid", "rut": "12.345.678-5", "rol": "Usuario solicitante"}
        with patch("usuarios.services.crear_usuario_auth0", return_value={"user_id": "auth0|rollback"}), patch("usuarios.services.registrar_auditoria", side_effect=DatabaseError("Fallo SQL inducido")), patch("usuarios.services.eliminar_usuario_auth0", side_effect=Exception("No disponible")):
            r = self.cliente(self.admin).post("/api/usuarios/aprovisionar/", payload, format="json")
        self.assertEqual(r.status_code, 500)
        self.assertIn("No se pudo revertir", r.data["error"])
        self.assertFalse(Usuario.objects.filter(correo=payload["correo"]).exists())

    def test_cabecera_forwarded_no_corrompe_la_ip_de_auditoria(self):
        r = self.cliente(self.solicitante).post("/api/tickets/", {"asunto": "Falla", "descripcion": "Prueba"}, format="json", HTTP_X_FORWARDED_FOR="valor-invalido, otra-ip")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(BitacoraAuditoria.objects.get().direccion_ip, "127.0.0.1")

    def test_callback_sin_claims_validados_no_crea_sesion(self):
        oauth = Mock()
        oauth.auth0.authorize_access_token.return_value = {"access_token": "no-es-identidad"}
        c = self.cliente()
        with patch("usuarios.views.get_oauth", return_value=oauth):
            r = c.get("/auth/callback/?code=prueba")
        self.assertEqual(r.status_code, 400)
        self.assertNotIn("siget_usuario_id", c.session)
        oauth.auth0.parse_id_token.assert_not_called()

    def test_inactivo_no_se_revincula_ni_accede(self):
        self.solicitante.activo = False
        self.solicitante.save()
        previo = self.solicitante.identificador_externo
        with self.assertRaises(UsuarioInactivoError):
            vincular_o_obtener_usuario({"sub": "auth0|otro", "email": self.solicitante.correo, "email_verified": True})
        self.solicitante.refresh_from_db()
        self.assertEqual(self.solicitante.identificador_externo, previo)
        self.assertEqual(self.cliente(self.solicitante).get("/api/tickets/").status_code, 403)

    def test_web_acceso_recuperacion_y_cierre_de_sesion(self):
        anonimo = self.cliente()
        self.assertEqual(anonimo.get("/").status_code, 200)
        self.assertEqual(anonimo.get("/auth/recover/").status_code, 200)
        self.assertEqual(self.cliente(self.admin).get("/").status_code, 403)
        c = self.cliente(self.solicitante)
        self.assertEqual(c.get("/").status_code, 200)
        r = c.get("/auth/logout/")
        self.assertEqual(r.status_code, 302)
        self.assertNotIn("siget_usuario_id", c.session)

    @override_settings(SIGET_PUBLIC_URL="http://localhost:8000")
    def test_login_alinea_host_antes_de_crear_estado_oauth(self):
        with patch("usuarios.views.get_oauth") as oauth:
            r = self.cliente().get("/auth/login/")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], "http://localhost:8000/auth/login/")
        oauth.assert_not_called()

    def competir(self, funcion):
        barrera = Barrier(2, timeout=10)
        def ejecutar(n):
            try:
                barrera.wait()
                return funcion(n)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(ejecutar, [1, 2]))

    def test_tickets_simultaneos_generan_codigos_distintos(self):
        def crear(n):
            u = Usuario.objects.get(pk=self.solicitante.pk if n == 1 else self.otro.pk)
            return crear_ticket(u, f"Incidente {n}", "Descripción").codigo_ticket
        codigos = self.competir(crear)
        self.assertEqual(len(set(codigos)), 2)
        self.assertEqual(Ticket.objects.count(), 2)

    def test_solicitudes_simultaneas_no_duplican(self):
        self.activo()
        def crear(n):
            from rest_framework.exceptions import ValidationError
            try:
                u = Usuario.objects.get(pk=self.solicitante.pk)
                crear_solicitud_asignacion(u, self.categoria.pk, "Misma solicitud")
                return "creada"
            except ValidationError:
                return "rechazada"
        self.assertCountEqual(self.competir(crear), ["creada", "rechazada"])
        self.assertEqual(SolicitudAsignacion.objects.count(), 1)

    def test_activos_simultaneos_generan_codigos_distintos(self):
        def crear(n):
            from activos.serializers import ActivoSerializer
            s = ActivoSerializer(data={"numero_serie": f"CONC-{n}", "id_modelo": self.modelo.pk, "id_ubicacion": self.ubicacion.pk})
            s.is_valid(raise_exception=True)
            return cast(Activo, s.save()).codigo_inventario
        self.assertEqual(len(set(self.competir(crear))), 2)

    def test_correlativo_activo_despues_de_9999_y_codigo_ajeno(self):
        a = self.activo()
        a.codigo_inventario = "ACT-9999"
        a.save()
        c = self.cliente(self.admin)
        payload = {"numero_serie": "SERIE-10000", "id_modelo": self.modelo.pk, "id_ubicacion": self.ubicacion.pk}
        r = c.post("/api/activos/", payload, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["codigo_inventario"], "ACT-10000")
