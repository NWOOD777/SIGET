"""Activos opcionales del portal; persistencia real en una base temporal test_."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from unittest.mock import patch

from django.db import connection, connections
from django.urls import reverse
from django.utils import timezone

from activos.models import EstadoActivo
from asignaciones.models import Asignacion, EstadoAsignacion, EstadoSolicitudAsignacion, SolicitudAsignacion
from asignaciones.services import registrar_devolucion_asignacion
from siget.db import bloquear_operacion
from tickets.forms import TicketCreateForm
from tickets.models import Ticket
from usuarios.models import BitacoraAuditoria, Permiso, Rol, RolPermiso, UsuarioRol
from usuarios.tests.test_integracion_postgresql import PostgreSQLTestBase


class TicketActivoPortalPostgreSQLTests(PostgreSQLTestBase):
    def setUp(self):
        super().setUp()
        self.assertTrue(str(connection.settings_dict["NAME"]).startswith("test_"))
        self.propia = self.asignacion(self.solicitante)
        self.ajena = self.asignacion(self.otro)
        self.finalizada = self.asignacion(self.solicitante, finalizada=True)
        self.sin_asignacion = self.activo()
        self.url = reverse("tickets_web:nuevo")
        self.datos = {"asunto": "Falla de pantalla", "descripcion": "La pantalla parpadea."}

    def asignacion(self, usuario, finalizada=False):
        activo = self.activo()
        activo.id_estado_activo = EstadoActivo.objects.get(nombre="Disponible" if finalizada else "Asignado")
        activo.save(update_fields=["id_estado_activo"])
        fecha = timezone.now() - timedelta(days=2)
        solicitud = SolicitudAsignacion.objects.create(
            id_usuario=usuario, id_categoria=self.categoria,
            id_estado_solicitud=EstadoSolicitudAsignacion.objects.get(nombre="Atendida"),
            id_administrador_resolutor=self.admin,
            fecha_solicitud=fecha - timedelta(days=2), fecha_resolucion=fecha - timedelta(days=1),
            motivo="Equipo de trabajo",
        )
        return Asignacion.objects.create(
            id_solicitud=solicitud, id_activo=activo, id_tecnico_entrega=self.tecnico,
            id_estado_asignacion=EstadoAsignacion.objects.get(nombre="Finalizada" if finalizada else "Activa"),
            fecha_entrega=fecha, fecha_finalizacion=fecha + timedelta(days=1) if finalizada else None,
        )

    def test_formulario_solo_ofrece_asignaciones_activas_propias(self):
        form = TicketCreateForm(usuario=self.solicitante)
        queryset = form.campo_activo.queryset
        assert queryset is not None
        self.assertEqual(list(queryset), [self.propia.id_activo])
        sin_usuario = TicketCreateForm().campo_activo.queryset
        assert sin_usuario is not None
        self.assertEqual(list(sin_usuario), [])
        self.solicitante.activo = False
        inactivo = TicketCreateForm(usuario=self.solicitante).campo_activo.queryset
        assert inactivo is not None
        self.assertEqual(list(inactivo), [])

    def test_get_muestra_codigo_modelo_y_opcion_sin_equipo(self):
        response = self.cliente(self.solicitante).get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sin equipo específico")
        self.assertContains(response, f"{self.propia.id_activo.codigo_inventario} — {self.modelo.nombre}")
        for activo in (self.ajena.id_activo, self.finalizada.id_activo, self.sin_asignacion):
            self.assertNotContains(response, activo.codigo_inventario)

    def test_post_con_activo_propio_persiste_relaciones_y_auditoria(self):
        antes = timezone.now()
        response = self.cliente(self.solicitante).post(
            self.url, {**self.datos, "id_activo": self.propia.id_activo_id,
                       "id_usuario_solicitante": self.otro.pk, "id_prioridad": 999999,
                       "codigo_ticket": "MANUAL", "id_estado_ticket": 999999,
                       "id_tecnico_asignado": self.tecnico.pk}, follow=True,
        )
        ticket = Ticket.objects.get()
        self.assertEqual(response.redirect_chain, [(reverse("tickets_web:confirmacion", kwargs={"pk": ticket.pk}), 302)])
        self.assertContains(response, ticket.codigo_ticket)
        self.assertEqual(ticket.id_activo_id, self.propia.id_activo_id)
        self.assertEqual(ticket.id_usuario_solicitante, self.solicitante)
        self.assertEqual(ticket.id_estado_ticket.nombre, "Abierto")
        self.assertEqual(ticket.id_prioridad.nombre, "Medio")
        self.assertIsNone(ticket.id_tecnico_asignado)
        self.assertTrue(ticket.codigo_ticket.startswith("TCK-"))
        self.assertGreaterEqual(ticket.fecha_creacion, antes)
        self.assertLessEqual(ticket.fecha_creacion, timezone.now())
        auditoria = BitacoraAuditoria.objects.get(accion="TICKET_CREADO")
        self.assertEqual(auditoria.id_usuario, self.solicitante)
        self.assertEqual(auditoria.id_registro_afectado, ticket.pk)

    def test_post_sin_activo_persiste_null_tanto_omitido_como_vacio(self):
        cliente = self.cliente(self.solicitante)
        for numero, extras in enumerate(({}, {"id_activo": ""})):
            with self.subTest(extras=extras):
                response = cliente.post(self.url, {**self.datos, "asunto": f"Incidente general {numero}", **extras})
                self.assertEqual(response.status_code, 302)
        self.assertEqual(Ticket.objects.count(), 2)
        self.assertEqual(Ticket.objects.filter(id_activo__isnull=True).count(), 2)

    def test_rechaza_activos_ajenos_finalizados_sin_asignacion_e_ids_manipulados(self):
        cliente = self.cliente(self.solicitante)
        for identificador in (
            self.ajena.id_activo_id, self.finalizada.id_activo_id, self.sin_asignacion.pk,
            999999, -1, "no-es-un-id",
        ):
            with self.subTest(identificador=identificador):
                response = cliente.post(self.url, {**self.datos, "id_activo": identificador})
                self.assertEqual(response.status_code, 200)
                self.assertIn("id_activo", response.context["form"].errors)
                self.assertContains(response, self.datos["asunto"])
                self.assertContains(response, self.datos["descripcion"])
        self.assertFalse(Ticket.objects.exists())
        self.assertFalse(BitacoraAuditoria.objects.filter(accion="TICKET_CREADO").exists())

    def test_post_revalida_equipo_finalizado_despues_del_get(self):
        cliente = self.cliente(self.solicitante)
        self.assertContains(cliente.get(self.url), self.propia.id_activo.codigo_inventario)
        self.propia.id_estado_asignacion = EstadoAsignacion.objects.get(nombre="Finalizada")
        self.propia.fecha_finalizacion = timezone.now()
        self.propia.save(update_fields=["id_estado_asignacion", "fecha_finalizacion"])

        response = cliente.post(self.url, {**self.datos, "id_activo": self.propia.id_activo_id})
        self.assertEqual(response.status_code, 200)
        self.assertIn("id_activo", response.context["form"].errors)
        self.assertFalse(Ticket.objects.exists())

    def test_post_revalida_propietario_despues_del_get(self):
        cliente = self.cliente(self.solicitante)
        self.assertContains(cliente.get(self.url), self.propia.id_activo.codigo_inventario)
        solicitud = self.propia.id_solicitud
        solicitud.id_usuario = self.otro
        solicitud.save(update_fields=["id_usuario"])

        response = cliente.post(self.url, {**self.datos, "id_activo": self.propia.id_activo_id})
        self.assertEqual(response.status_code, 200)
        self.assertIn("id_activo", response.context["form"].errors)
        self.assertFalse(Ticket.objects.exists())

    def test_fecha_finalizacion_excluye_asignacion_aunque_conserve_estado_activa(self):
        self.propia.fecha_finalizacion = timezone.now()
        self.propia.save(update_fields=["fecha_finalizacion"])
        form = TicketCreateForm(data={**self.datos, "id_activo": self.propia.id_activo_id}, usuario=self.solicitante)
        self.assertFalse(form.is_valid())
        self.assertIn("id_activo", form.errors)

    def test_sin_asignaciones_activas_puede_crear_ticket_general(self):
        response = self.cliente(self.admin).post(self.url, self.datos)
        self.assertEqual(response.status_code, 403)
        # El otro solicitante conserva el rol, pero su asignación ya finalizó.
        self.ajena.id_estado_asignacion = EstadoAsignacion.objects.get(nombre="Finalizada")
        self.ajena.fecha_finalizacion = timezone.now()
        self.ajena.save(update_fields=["id_estado_asignacion", "fecha_finalizacion"])
        cliente = self.cliente(self.otro)
        self.assertContains(cliente.get(self.url), "Sin equipo específico")
        response = cliente.post(self.url, self.datos)
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(Ticket.objects.get().id_activo_id)

    def test_duplicado_bloqueado_para_mismo_activo_y_para_null(self):
        cliente = self.cliente(self.solicitante)
        for seleccion in (self.propia.id_activo_id, ""):
            with self.subTest(seleccion=seleccion):
                datos = {**self.datos, "id_activo": seleccion}
                self.assertEqual(cliente.post(self.url, datos).status_code, 302)
                response = cliente.post(self.url, {**datos, "asunto": "  FALLA DE PANTALLA  "})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].non_field_errors())
                self.assertContains(response, self.datos["descripcion"])
        self.assertEqual(Ticket.objects.count(), 2)

    def test_errores_del_servicio_conservan_activo_seleccionado(self):
        cliente = self.cliente(self.solicitante)
        datos = {**self.datos, "id_activo": self.propia.id_activo_id}
        self.assertEqual(cliente.post(self.url, datos).status_code, 302)
        response = cliente.post(self.url, datos)
        self.assertContains(response, f'value="{self.propia.id_activo_id}" selected')
        self.assertContains(response, self.datos["asunto"])
        self.assertEqual(Ticket.objects.count(), 1)

    def test_api_permite_activo_propio_y_sin_activo(self):
        cliente = self.cliente(self.solicitante)
        for numero, extras in enumerate(({"id_activo": self.propia.id_activo_id}, {}, {"id_activo": None})):
            with self.subTest(extras=extras):
                response = cliente.post("/api/tickets/", {**self.datos, "asunto": f"Incidente API {numero}", **extras}, format="json")
                self.assertEqual(response.status_code, 201, response.data)
                ticket = Ticket.objects.get(pk=response.data["id_ticket"])
                self.assertEqual(ticket.id_usuario_solicitante, self.solicitante)
                self.assertEqual(ticket.id_activo_id, extras.get("id_activo"))

    def test_api_rechaza_activos_no_autorizados_sin_efectos(self):
        cliente = self.cliente(self.solicitante)  # sesión con rol admin falsificado
        for identificador in (self.ajena.id_activo_id, self.finalizada.id_activo_id, self.sin_asignacion.pk, 999999):
            with self.subTest(identificador=identificador):
                response = cliente.post("/api/tickets/", {**self.datos, "id_activo": identificador}, format="json")
                self.assertEqual(response.status_code, 403, response.data)
                self.assertEqual(str(response.data["detail"]), "No tiene autorización para reportar ese activo.")
        self.assertFalse(Ticket.objects.exists())
        self.assertFalse(BitacoraAuditoria.objects.filter(accion="TICKET_CREADO").exists())

    def test_api_admin_y_tecnico_no_registran_tickets_manuales(self):
        for usuario in (self.admin, self.tecnico):
            for activo in (self.sin_asignacion, self.finalizada.id_activo, self.ajena.id_activo):
                with self.subTest(usuario=usuario.pk, activo=activo.pk):
                    response = self.cliente(usuario).post("/api/tickets/", {**self.datos, "id_activo": activo.pk}, format="json")
                    self.assertEqual(response.status_code, 403, response.data)
        self.assertFalse(Ticket.objects.exists())

    def test_api_roles_multiples_no_amplian_activos_del_solicitante(self):
        UsuarioRol.objects.create(usuario=self.solicitante, rol=Rol.objects.get(nombre="Técnico de soporte"))
        response = self.cliente(self.solicitante).post(
            "/api/tickets/", {**self.datos, "id_activo": self.ajena.id_activo_id}, format="json",
        )
        self.assertEqual(response.status_code, 403, response.data)

    def test_api_ticket_crear_sin_rol_interno_no_concede_activos_globales(self):
        rol = Rol.objects.create(nombre="Reportador de prueba")
        RolPermiso.objects.create(rol=rol, permiso=Permiso.objects.get(codigo="TICKET_CREAR"))
        UsuarioRol.objects.filter(usuario=self.solicitante).delete()
        UsuarioRol.objects.create(usuario=self.solicitante, rol=rol)
        cliente = self.cliente(self.solicitante)
        response = cliente.post("/api/tickets/", {**self.datos, "id_activo": self.ajena.id_activo_id}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Ticket.objects.exists())
        response = cliente.post("/api/tickets/", {**self.datos, "id_activo": self.propia.id_activo_id}, format="json")
        self.assertEqual(response.status_code, 403, response.data)
        response = cliente.post("/api/tickets/", {**self.datos, "asunto": "Incidente general"}, format="json")
        self.assertEqual(response.status_code, 403, response.data)

    def test_api_duplicados_siguen_bloqueados_con_activo_y_null(self):
        cliente = self.cliente(self.solicitante)
        for activo in (self.propia.id_activo_id, None):
            datos = {**self.datos, "id_activo": activo}
            self.assertEqual(cliente.post("/api/tickets/", datos, format="json").status_code, 201)
            response = cliente.post("/api/tickets/", datos, format="json")
            self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(Ticket.objects.count(), 2)
        self.assertEqual(BitacoraAuditoria.objects.filter(accion="TICKET_CREADO").count(), 2)

    def test_api_rechaza_fecha_finalizacion_aunque_estado_siga_activa(self):
        self.propia.fecha_finalizacion = timezone.now()
        self.propia.save(update_fields=["fecha_finalizacion"])
        response = self.cliente(self.solicitante).post(
            "/api/tickets/", {**self.datos, "id_activo": self.propia.id_activo_id}, format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Ticket.objects.exists())

    def test_ticket_automatico_de_devolucion_permite_asignacion_finalizada(self):
        devolucion = registrar_devolucion_asignacion(
            self.propia, self.tecnico, "Con falla técnica", observaciones="Falla al devolver",
        )
        self.propia.refresh_from_db()
        self.assertEqual(self.propia.id_estado_asignacion.nombre, "Finalizada")
        ticket = Ticket.objects.get()
        self.assertEqual(ticket.id_activo_id, self.propia.id_activo_id)
        self.assertEqual(ticket.id_usuario_solicitante, self.solicitante)
        self.assertEqual(devolucion.id_asignacion, self.propia)

    def carrera_devolucion_manual(self, canal, primero):
        """Fuerza ambos órdenes mediante eventos y bloqueos reales, sin sleeps."""
        asignacion = self.asignacion(self.solicitante)
        adquirido, esperando, liberar = Event(), Event(), Event()
        modulo = "tickets.views" if canal == "api" else "tickets.web_views"
        cliente = self.cliente(self.solicitante)
        def bloquear_manual(dominio, identificador=0):
            if dominio == 70403 and identificador == asignacion.id_activo_id and primero == "devolucion":
                esperando.set()
            bloquear_operacion(dominio, identificador)
            if dominio == 70403 and identificador == asignacion.id_activo_id and primero == "manual":
                adquirido.set()
                if not liberar.wait(10):
                    raise TimeoutError("No se liberó la creación manual")

        def bloquear_devolucion(dominio, identificador=0):
            if dominio == 70403 and identificador == asignacion.id_activo_id and primero == "manual":
                esperando.set()
            bloquear_operacion(dominio, identificador)
            if dominio == 70403 and identificador == asignacion.id_activo_id and primero == "devolucion":
                adquirido.set()
                if not liberar.wait(10):
                    raise TimeoutError("No se liberó la devolución")

        asunto = f"Incidente concurrente {canal} {primero}"
        def manual():
            try:
                datos = {**self.datos, "asunto": asunto, "id_activo": asignacion.id_activo_id}
                if canal == "api":
                    return cliente.post("/api/tickets/", datos, format="json").status_code
                return cliente.post(self.url, datos).status_code
            finally:
                connections.close_all()

        def devolver():
            try:
                registrar_devolucion_asignacion(
                    Asignacion.objects.get(pk=asignacion.pk), self.tecnico,
                    "Con falla técnica", observaciones="Falla concurrente",
                )
                return "devuelto"
            finally:
                connections.close_all()

        with (
            patch(f"{modulo}.bloquear_operacion", side_effect=bloquear_manual),
            patch("asignaciones.services.bloquear_operacion", side_effect=bloquear_devolucion),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            inicial = pool.submit(manual if primero == "manual" else devolver)
            try:
                self.assertTrue(adquirido.wait(10), "La primera operación no adquirió el bloqueo")
                segundo = pool.submit(devolver if primero == "manual" else manual)
                self.assertTrue(esperando.wait(10), "La segunda operación no intentó adquirir el bloqueo")
                self.assertFalse(segundo.done(), "La segunda operación debe esperar el bloqueo")
            finally:
                liberar.set()
            resultado_inicial = inicial.result(timeout=15)
            resultado_segundo = segundo.result(timeout=15)

        resultado_manual = resultado_inicial if primero == "manual" else resultado_segundo
        if primero == "manual":
            self.assertEqual(resultado_manual, 201 if canal == "api" else 302)
            self.assertEqual(Ticket.objects.filter(asunto=asunto).count(), 1)
        else:
            self.assertEqual(resultado_manual, 403 if canal == "api" else 200)
            self.assertFalse(Ticket.objects.filter(asunto=asunto).exists())
        asignacion.refresh_from_db()
        self.assertEqual(asignacion.id_estado_asignacion.nombre, "Finalizada")
        # La devolución genera un ticket o reutiliza el manual, nunca duplica.
        self.assertEqual(Ticket.objects.filter(id_activo=asignacion.id_activo).count(), 1)

    def test_devolucion_primero_impide_creacion_manual_api_y_portal(self):
        for canal in ("api", "portal"):
            with self.subTest(canal=canal):
                self.carrera_devolucion_manual(canal, "devolucion")

    def test_creacion_manual_primero_permite_devolucion_sin_duplicar_ticket(self):
        for canal in ("api", "portal"):
            with self.subTest(canal=canal):
                self.carrera_devolucion_manual(canal, "manual")
