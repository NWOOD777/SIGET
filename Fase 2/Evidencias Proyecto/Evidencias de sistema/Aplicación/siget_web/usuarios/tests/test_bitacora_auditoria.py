"""
Pruebas de integración con PostgreSQL de la bitácora de auditoría.
Valida el endpoint /api/auditoria/, autorización RBAC estricta (permiso AUDITORIA_CONSULTAR),
orden cronológico estable, filtros por usuario y activo con resolución real de relaciones,
aislamiento de identificadores, inmutabilidad y paginación.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db import connection
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from activos.models import Activo, CategoriaActivo, EstadoActivo, Marca, ModeloActivo, Ubicacion
from asignaciones.models import (
    Asignacion,
    DevolucionActivo,
    EstadoAsignacion,
    EstadoSolicitudAsignacion,
    SolicitudAsignacion,
)
from ordenes_trabajo.models import EstadoOrdenTrabajo, OrdenTrabajo
from siget.testing import cargar_esquema_pruebas
from tickets.models import ComentarioTicket, EstadoTicket, EvaluacionCSAT, PrioridadTicket, Ticket
from usuarios.models import BitacoraAuditoria, Permiso, Rol, RolPermiso, Usuario, UsuarioRol
from usuarios.services import registrar_auditoria


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"], SIGET_PUBLIC_URL="")
class BitacoraAuditoriaPostgreSQLE2ETests(TransactionTestCase):
    """
    Pruebas de integración sobre base de datos PostgreSQL real.
    """

    @classmethod
    def _fixture_setup(cls):
        getattr(super(), "_fixture_setup")()
        cargar_esquema_pruebas()

    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")

        # Usuarios de prueba con roles canónicos
        self.admin = self._crear_usuario(1, "Administrador del sistema", "admin@siget.cl", "Admin", "General")
        self.tecnico = self._crear_usuario(2, "Técnico de soporte", "tecnico@siget.cl", "Tecnico", "Soporte")
        self.solicitante = self._crear_usuario(3, "Usuario solicitante", "solicitante@siget.cl", "Usuario", "Solicitante")

        # Activo maestro y dependencias definidas por la propia prueba
        self.categoria, _ = CategoriaActivo.objects.get_or_create(
            nombre="Notebook",
            defaults={"descripcion": "Computador portátil corporativo"},
        )
        self.marca, _ = Marca.objects.get_or_create(nombre="Lenovo")
        self.modelo, _ = ModeloActivo.objects.get_or_create(
            id_categoria=self.categoria,
            id_marca=self.marca,
            nombre="ThinkPad T14",
        )
        self.ubicacion, _ = Ubicacion.objects.get_or_create(
            nombre_area="Departamento TI",
            edificio="Edificio Central",
            piso="Piso 2",
        )
        self.estado_disponible = EstadoActivo.objects.get(nombre="Disponible")
        self.estado_asignado = EstadoActivo.objects.get(nombre="Asignado")

        self.activo1 = Activo.objects.create(
            codigo_inventario="ACT-TEST-001",
            numero_serie="SERIE-001",
            id_modelo=self.modelo,
            id_ubicacion=self.ubicacion,
            id_estado_activo=self.estado_disponible,
            valor_adquisicion=1200000,
        )

        self.activo2 = Activo.objects.create(
            codigo_inventario="ACT-TEST-002",
            numero_serie="SERIE-002",
            id_modelo=self.modelo,
            id_ubicacion=self.ubicacion,
            id_estado_activo=self.estado_disponible,
            valor_adquisicion=1300000,
        )

    def _crear_usuario(self, n: int, rol_nombre: str, correo: str, nombres: str, apellidos: str) -> Usuario:
        u = Usuario.objects.create(
            identificador_externo=f"auth0|auditoria_{n}",
            proveedor_identidad="Auth0",
            rut=f"{n:08d}-k",
            nombres=nombres,
            apellidos=apellidos,
            correo=correo,
            activo=True,
        )
        rol = Rol.objects.get(nombre=rol_nombre)
        UsuarioRol.objects.create(usuario=u, rol=rol)
        return u

    def _cliente(self, usuario: Usuario | None = None) -> Any:
        c = APIClient()
        if usuario is not None:
            session = c.session
            session["siget_usuario_id"] = usuario.pk
            session.save()
        return c

    # =========================================================================
    # Administrador autorizado, orden cronológico y datos del evento
    # =========================================================================

    def test_01_administrador_autorizado_puede_consultar_bitacora_y_recibe_orden_cronologico(self):
        ahora = timezone.now()
        e1 = registrar_auditoria(
            usuario=self.admin,
            modulo="USUARIOS",
            accion="APROVISIONAR_USUARIO",
            entidad_afectada="usuario",
            id_registro_afectado=self.solicitante.pk,
            detalle_evento="Usuario solicitante creado.",
            direccion_ip="192.168.1.100",
        )
        # Forzar fechas distintas
        BitacoraAuditoria.objects.filter(pk=e1.pk).update(fecha_evento=ahora - timedelta(minutes=10))

        e2 = registrar_auditoria(
            usuario=self.admin,
            modulo="ACTIVOS",
            accion="ACTIVO_CREADO",
            entidad_afectada="activo",
            id_registro_afectado=self.activo1.pk,
            detalle_evento="Activo ACT-TEST-001 creado.",
            direccion_ip="192.168.1.100",
        )
        BitacoraAuditoria.objects.filter(pk=e2.pk).update(fecha_evento=ahora - timedelta(minutes=5))

        e3 = registrar_auditoria(
            usuario=self.admin,
            modulo="ACTIVOS",
            accion="ACTIVO_MODIFICADO",
            entidad_afectada="activo",
            id_registro_afectado=self.activo1.pk,
            detalle_evento="Activo ACT-TEST-001 modificado.",
            direccion_ip="192.168.1.100",
        )
        BitacoraAuditoria.objects.filter(pk=e3.pk).update(fecha_evento=ahora)

        cliente = self._cliente(self.admin)
        resp = cliente.get("/api/auditoria/")
        self.assertEqual(resp.status_code, 200)

        data = resp.json()
        self.assertIn("results", data)
        self.assertIn("count", data)
        self.assertGreaterEqual(data["count"], 3)

        ids = [item["id_auditoria"] for item in data["results"][:3]]
        # Más recientes primero
        self.assertEqual(ids, [e3.pk, e2.pk, e1.pk])

        # Verificar estructura completa de campos del evento
        primer_evento = data["results"][0]
        self.assertEqual(primer_evento["id_auditoria"], e3.pk)
        self.assertEqual(primer_evento["usuario"], "Admin General")
        self.assertEqual(primer_evento["usuario_correo"], "admin@siget.cl")
        self.assertEqual(primer_evento["direccion_ip"], "192.168.1.100")
        self.assertEqual(primer_evento["modulo"], "ACTIVOS")
        self.assertEqual(primer_evento["accion"], "ACTIVO_MODIFICADO")
        self.assertEqual(primer_evento["entidad_afectada"], "activo")
        self.assertEqual(primer_evento["id_registro_afectado"], self.activo1.pk)
        self.assertEqual(primer_evento["recurso"], f"activo #{self.activo1.pk}")
        self.assertIn("fecha_evento", primer_evento)
        self.assertIn("detalle_evento", primer_evento)

    def test_02_tecnico_y_solicitante_reciben_403(self):
        cliente_tecnico = self._cliente(self.tecnico)
        resp_tec = cliente_tecnico.get("/api/auditoria/")
        self.assertEqual(resp_tec.status_code, 403)

        cliente_solicitante = self._cliente(self.solicitante)
        resp_sol = cliente_solicitante.get("/api/auditoria/")
        self.assertEqual(resp_sol.status_code, 403)

    def test_03_usuario_anonimo_e_inactivo_y_permisos_revocados(self):
        # 1. Anónimo sin sesión
        cliente_anon = self._cliente(None)
        resp_anon = cliente_anon.get("/api/auditoria/")
        self.assertIn(resp_anon.status_code, (401, 403))

        # 2. Administrador inactivo
        self.admin.activo = False
        self.admin.save(update_fields=["activo"])
        cliente_inactivo = self._cliente(self.admin)
        resp_inactivo = cliente_inactivo.get("/api/auditoria/")
        self.assertEqual(resp_inactivo.status_code, 403)
        self.admin.activo = True
        self.admin.save(update_fields=["activo"])

        # 3. Administrador con permiso AUDITORIA_CONSULTAR revocado
        rol_admin = Rol.objects.get(nombre="Administrador del sistema")
        permiso_audit = Permiso.objects.get(codigo="AUDITORIA_CONSULTAR")
        RolPermiso.objects.filter(rol=rol_admin, permiso=permiso_audit).delete()

        cliente_admin_sin_permiso = self._cliente(self.admin)
        resp_sin_perm = cliente_admin_sin_permiso.get("/api/auditoria/")
        self.assertEqual(resp_sin_perm.status_code, 403)

    def test_04_orden_estable_con_fechas_iguales(self):
        ahora = timezone.now()
        e_a = registrar_auditoria(
            usuario=self.admin,
            modulo="SISTEMA",
            accion="TEST_A",
            entidad_afectada="config",
            id_registro_afectado=1,
            detalle_evento="Evento A",
        )
        e_b = registrar_auditoria(
            usuario=self.admin,
            modulo="SISTEMA",
            accion="TEST_B",
            entidad_afectada="config",
            id_registro_afectado=2,
            detalle_evento="Evento B",
        )
        BitacoraAuditoria.objects.filter(pk__in=[e_a.pk, e_b.pk]).update(fecha_evento=ahora)

        cliente = self._cliente(self.admin)
        resp = cliente.get("/api/auditoria/")
        self.assertEqual(resp.status_code, 200)

        results = resp.json()["results"]
        pos_b = next(i for i, r in enumerate(results) if r["id_auditoria"] == e_b.pk)
        pos_a = next(i for i, r in enumerate(results) if r["id_auditoria"] == e_a.pk)
        # e_b tiene id_auditoria mayor, debe aparecer antes que e_a
        self.assertLess(pos_b, pos_a)

    def test_05_usuario_e_ip_nulos_sin_inventar_valores(self):
        evento = registrar_auditoria(
            usuario=None,
            modulo="SISTEMA_AUTO",
            accion="TAREA_AUTOMATICA",
            entidad_afectada="sistema",
            id_registro_afectado=None,
            detalle_evento="Limpieza periódica ejecutada por el sistema.",
            direccion_ip=None,
        )

        cliente = self._cliente(self.admin)
        resp = cliente.get(f"/api/auditoria/{evento.pk}/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertIsNone(data["id_usuario"])
        self.assertIsNone(data["usuario"])
        self.assertIsNone(data["usuario_correo"])
        self.assertNotIn("usuario_rut", data)
        self.assertIsNone(data["direccion_ip"])
        self.assertIsNone(data["id_registro_afectado"])
        self.assertEqual(data["recurso"], "sistema")

    # =========================================================================
    # Búsqueda por identificador de usuario y activo
    # =========================================================================

    def test_06_filtro_por_usuario(self):
        e_admin = registrar_auditoria(
            usuario=self.admin,
            modulo="RBAC",
            accion="ASIGNAR_ROLES",
            entidad_afectada="usuario_rol",
            id_registro_afectado=self.tecnico.pk,
            detalle_evento="Roles asignados.",
        )
        e_tec = registrar_auditoria(
            usuario=self.tecnico,
            modulo="ASIGNACIONES",
            accion="ENTREGA_REGISTRADA",
            entidad_afectada="asignacion",
            id_registro_afectado=10,
            detalle_evento="Entrega registrada.",
        )

        cliente = self._cliente(self.admin)

        # 1. Por ID de usuario
        resp_id = cliente.get(f"/api/auditoria/?usuario={self.tecnico.pk}")
        self.assertEqual(resp_id.status_code, 200)
        ids_res = [r["id_auditoria"] for r in resp_id.json()["results"]]
        self.assertIn(e_tec.pk, ids_res)
        self.assertNotIn(e_admin.pk, ids_res)

        # 2. Por correo
        resp_correo = cliente.get(f"/api/auditoria/?usuario={self.admin.correo}")
        self.assertEqual(resp_correo.status_code, 200)
        ids_res_correo = [r["id_auditoria"] for r in resp_correo.json()["results"]]
        self.assertIn(e_admin.pk, ids_res_correo)
        self.assertNotIn(e_tec.pk, ids_res_correo)

        # 3. Por id_usuario específico
        resp_param = cliente.get(f"/api/auditoria/?id_usuario={self.tecnico.pk}")
        self.assertEqual(resp_param.status_code, 200)
        ids_res_param = [r["id_auditoria"] for r in resp_param.json()["results"]]
        self.assertIn(e_tec.pk, ids_res_param)
        self.assertNotIn(e_admin.pk, ids_res_param)

    def test_07_filtro_por_activo_con_eventos_directos_e_indirectos(self):
        """
        Al filtrar por número de inventario de un activo, se deben recuperar
        todas las modificaciones de estado e intervenciones registradas:
        - Activo directo
        - Asignaciones y devoluciones
        - Solicitudes vinculadas mediante asignaciones reales
        - Tickets del activo
        - Comentarios y CSAT asociados a esos tickets
        - Órdenes de trabajo del ticket
        """
        # 1. Evento directo de activo
        e_activo = registrar_auditoria(
            usuario=self.admin,
            modulo="ACTIVOS",
            accion="ACTIVO_MODIFICADO",
            entidad_afectada="activo",
            id_registro_afectado=self.activo1.pk,
            detalle_evento=f"Modificado {self.activo1.codigo_inventario}.",
        )

        # 2. Solicitud y Asignación real del activo 1
        solicitud = SolicitudAsignacion.objects.create(
            id_usuario=self.solicitante,
            id_categoria=self.categoria,
            id_estado_solicitud=EstadoSolicitudAsignacion.objects.get(pk=1),
            motivo="Proyecto A",
            motivo_rechazo=None,
        )
        e_solicitud = registrar_auditoria(
            usuario=self.solicitante,
            modulo="ASIGNACIONES",
            accion="SOLICITUD_CREADA",
            entidad_afectada="solicitud_asignacion",
            id_registro_afectado=solicitud.pk,
            detalle_evento=f"Solicitud #{solicitud.pk}.",
        )

        asignacion = Asignacion.objects.create(
            id_solicitud=solicitud,
            id_activo=self.activo1,
            id_tecnico_entrega=self.tecnico,
            id_estado_asignacion=EstadoAsignacion.objects.get(pk=1),
        )
        e_asignacion = registrar_auditoria(
            usuario=self.tecnico,
            modulo="ASIGNACIONES",
            accion="ENTREGA_REGISTRADA",
            entidad_afectada="asignacion",
            id_registro_afectado=asignacion.pk,
            detalle_evento=f"Entrega #{asignacion.pk}.",
        )

        # 3. Devolución de esa asignación
        devolucion = DevolucionActivo.objects.create(
            id_asignacion=asignacion,
            id_tecnico_receptor=self.tecnico,
            id_estado_activo_resultante=self.estado_disponible,
            condicion_fisica="Buen estado",
        )
        e_devolucion = registrar_auditoria(
            usuario=self.tecnico,
            modulo="ASIGNACIONES",
            accion="DEVOLUCION_REGISTRADA",
            entidad_afectada="devolucion_activo",
            id_registro_afectado=devolucion.pk,
            detalle_evento=f"Devolución #{devolucion.pk}.",
        )

        # 4. Ticket asociado al activo 1
        ticket = Ticket.objects.create(
            codigo_ticket="TCK-AUD-001",
            asunto="Falla de pantalla",
            descripcion="Pantalla parpadea",
            id_usuario_solicitante=self.solicitante,
            id_tecnico_asignado=self.tecnico,
            id_activo=self.activo1,
            id_estado_ticket=EstadoTicket.objects.get(pk=1),
            id_prioridad=PrioridadTicket.objects.get(pk=1),
        )
        e_ticket = registrar_auditoria(
            usuario=self.solicitante,
            modulo="SERVICE_DESK",
            accion="TICKET_CREADO",
            entidad_afectada="ticket",
            id_registro_afectado=ticket.pk,
            detalle_evento=f"Ticket {ticket.codigo_ticket}.",
        )

        # 5. Comentario y CSAT del ticket
        comentario = ComentarioTicket.objects.create(
            id_ticket=ticket,
            id_usuario=self.tecnico,
            mensaje="Diagnóstico inicial completado.",
        )
        e_comentario = registrar_auditoria(
            usuario=self.tecnico,
            modulo="SERVICE_DESK",
            accion="TICKET_ATENDIDO",
            entidad_afectada="comentario_ticket",
            id_registro_afectado=comentario.pk,
            detalle_evento=f"Atención en {ticket.codigo_ticket}.",
        )

        csat = EvaluacionCSAT.objects.create(
            id_ticket=ticket,
            id_usuario=self.solicitante,
            calificacion_estrellas=5,
            comentario="Excelente atención",
        )
        e_csat = registrar_auditoria(
            usuario=self.solicitante,
            modulo="SERVICE_DESK",
            accion="TICKET_CSAT_REGISTRADO",
            entidad_afectada="evaluacion_csat",
            id_registro_afectado=csat.pk,
            detalle_evento=f"Evaluación en {ticket.codigo_ticket}.",
        )

        # 6. Orden de trabajo del ticket
        ot = OrdenTrabajo.objects.create(
            codigo_ot="OT-AUD-001",
            id_ticket=ticket,
            id_tecnico_responsable=self.tecnico,
            id_estado_ot=EstadoOrdenTrabajo.objects.get(pk=1),
            fecha_inicio=timezone.now(),
        )
        e_ot = registrar_auditoria(
            usuario=self.tecnico,
            modulo="ORDENES_TRABAJO",
            accion="OT_CREADA",
            entidad_afectada="orden_trabajo",
            id_registro_afectado=ot.pk,
            detalle_evento=f"OT {ot.codigo_ot}.",
        )

        # 7. Evento ajeno del activo 2 (no debe aparecer)
        e_activo2 = registrar_auditoria(
            usuario=self.admin,
            modulo="ACTIVOS",
            accion="ACTIVO_MODIFICADO",
            entidad_afectada="activo",
            id_registro_afectado=self.activo2.pk,
            detalle_evento="Activo 2 modificado.",
        )

        cliente = self._cliente(self.admin)
        resp = cliente.get(f"/api/auditoria/?activo={self.activo1.codigo_inventario}")
        self.assertEqual(resp.status_code, 200)

        encontrados = {r["id_auditoria"] for r in resp.json()["results"]}
        esperados = {
            e_activo.pk,
            e_solicitud.pk,
            e_asignacion.pk,
            e_devolucion.pk,
            e_ticket.pk,
            e_comentario.pk,
            e_csat.pk,
            e_ot.pk,
        }

        self.assertTrue(esperados.issubset(encontrados))
        self.assertNotIn(e_activo2.pk, encontrados)

    def test_08_dos_entidades_con_igual_id_sin_contaminacion_de_resultados(self):
        """
        Verifica que si una Asignacion del activo 1 y un Ticket del activo 2
        comparten el mismo ID numérico (ej. 99), no se produzca contaminación.
        """
        id_compartido = 9999

        sol_1 = SolicitudAsignacion.objects.create(
            id_usuario=self.solicitante,
            id_categoria=self.categoria,
            id_estado_solicitud=EstadoSolicitudAsignacion.objects.get(pk=1),
            motivo="Solicitud de asignación para activo 1",
        )

        # Evento de asignación para activo 1 con id_registro_afectado = 9999
        asig_1 = Asignacion.objects.create(
            id_asignacion=id_compartido,
            id_solicitud=sol_1,
            id_activo=self.activo1,
            id_tecnico_entrega=self.tecnico,
            id_estado_asignacion=EstadoAsignacion.objects.get(pk=1),
        )
        e_asig_1 = registrar_auditoria(
            usuario=self.tecnico,
            modulo="ASIGNACIONES",
            accion="ENTREGA_REGISTRADA",
            entidad_afectada="asignacion",
            id_registro_afectado=asig_1.pk,
            detalle_evento="Asignación activo 1",
        )

        # Evento de ticket para activo 2 con id_registro_afectado = 9999
        ticket_2 = Ticket.objects.create(
            id_ticket=id_compartido,
            codigo_ticket="TCK-COMPARTIDO-9999",
            asunto="Problema activo 2",
            descripcion="Falla",
            id_usuario_solicitante=self.solicitante,
            id_tecnico_asignado=self.tecnico,
            id_activo=self.activo2,
            id_estado_ticket=EstadoTicket.objects.get(pk=1),
            id_prioridad=PrioridadTicket.objects.get(pk=1),
        )
        e_ticket_2 = registrar_auditoria(
            usuario=self.solicitante,
            modulo="SERVICE_DESK",
            accion="TICKET_CREADO",
            entidad_afectada="ticket",
            id_registro_afectado=ticket_2.pk,
            detalle_evento="Ticket activo 2",
        )

        cliente = self._cliente(self.admin)

        # Consultar activo 1: debe contener e_asig_1 y NO e_ticket_2
        resp1 = cliente.get(f"/api/auditoria/?activo={self.activo1.codigo_inventario}")
        self.assertEqual(resp1.status_code, 200)
        ids1 = {r["id_auditoria"] for r in resp1.json()["results"]}
        self.assertIn(e_asig_1.pk, ids1)
        self.assertNotIn(e_ticket_2.pk, ids1)

        # Consultar activo 2: debe contener e_ticket_2 y NO e_asig_1
        resp2 = cliente.get(f"/api/auditoria/?activo={self.activo2.codigo_inventario}")
        self.assertEqual(resp2.status_code, 200)
        ids2 = {r["id_auditoria"] for r in resp2.json()["results"]}
        self.assertIn(e_ticket_2.pk, ids2)
        self.assertNotIn(e_asig_1.pk, ids2)

    def test_09_solicitudes_no_vinculadas_mediante_asignacion_real_no_se_asocian(self):
        """
        Una solicitud general de la misma categoría no debe asociarse a un activo
        a menos que haya sido materializada en una asignación real de ese equipo.
        """
        solicitud_libre = SolicitudAsignacion.objects.create(
            id_usuario=self.solicitante,
            id_categoria=self.categoria,
            id_estado_solicitud=EstadoSolicitudAsignacion.objects.get(pk=1),
            motivo="Solicitud sin activo asignado",
        )
        e_sol_libre = registrar_auditoria(
            usuario=self.solicitante,
            modulo="ASIGNACIONES",
            accion="SOLICITUD_CREADA",
            entidad_afectada="solicitud_asignacion",
            id_registro_afectado=solicitud_libre.pk,
            detalle_evento="Solicitud sin activo asignado",
        )

        cliente = self._cliente(self.admin)
        resp = cliente.get(f"/api/auditoria/?activo={self.activo1.codigo_inventario}")
        self.assertEqual(resp.status_code, 200)

        ids = {r["id_auditoria"] for r in resp.json()["results"]}
        self.assertNotIn(e_sol_libre.pk, ids)

    def test_10_filtro_combinado_usuario_y_activo(self):
        e1 = registrar_auditoria(
            usuario=self.admin,
            modulo="ACTIVOS",
            accion="ACTIVO_MODIFICADO",
            entidad_afectada="activo",
            id_registro_afectado=self.activo1.pk,
            detalle_evento="Modificado por admin",
        )
        e2 = registrar_auditoria(
            usuario=self.tecnico,
            modulo="ACTIVOS",
            accion="ACTIVO_MODIFICADO",
            entidad_afectada="activo",
            id_registro_afectado=self.activo1.pk,
            detalle_evento="Modificado por tecnico",
        )

        cliente = self._cliente(self.admin)
        # Combinar activo1 + admin
        resp = cliente.get(f"/api/auditoria/?activo={self.activo1.codigo_inventario}&usuario={self.admin.pk}")
        self.assertEqual(resp.status_code, 200)

        ids = [r["id_auditoria"] for r in resp.json()["results"]]
        self.assertIn(e1.pk, ids)
        self.assertNotIn(e2.pk, ids)

    # =========================================================================
    # Búsqueda sin coincidencias y validaciones de entrada
    # =========================================================================

    def test_11_busqueda_sin_coincidencias_retorna_resultado_vacio(self):
        cliente = self._cliente(self.admin)
        resp = cliente.get("/api/auditoria/?activo=ACT-INEXISTENTE-999")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["count"], 0)
        self.assertEqual(data["total_pages"], 0)
        self.assertEqual(data["results"], [])

    def test_12_paginacion_y_validaciones_de_filtro(self):
        # Crear 5 eventos
        for i in range(5):
            registrar_auditoria(
                usuario=self.admin,
                modulo="TEST_PAGE",
                accion="PAGINAR",
                entidad_afectada="test",
                id_registro_afectado=i,
                detalle_evento=f"Página evento {i}",
            )

        cliente = self._cliente(self.admin)

        # 1. Página válida
        resp = cliente.get("/api/auditoria/?modulo=TEST_PAGE&page=1&page_size=2")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 5)
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["page_size"], 2)
        self.assertEqual(data["total_pages"], 3)
        self.assertEqual(len(data["results"]), 2)

        # 2. Página inválida (no numérica o menor a 1)
        resp_inv = cliente.get("/api/auditoria/?page=0")
        self.assertEqual(resp_inv.status_code, 400)
        self.assertIn("page", resp_inv.json())

        resp_text = cliente.get("/api/auditoria/?page=abc")
        self.assertEqual(resp_text.status_code, 400)

        # 3. Tamaño de página inválido
        resp_size = cliente.get("/api/auditoria/?page_size=200")
        self.assertEqual(resp_size.status_code, 400)
        self.assertIn("page_size", resp_size.json())

        # 4. Página mayor a total_pages
        resp_over = cliente.get("/api/auditoria/?modulo=TEST_PAGE&page=10&page_size=2")
        self.assertEqual(resp_over.status_code, 400)
        self.assertIn("page", resp_over.json())

        # 5. id_usuario no numérico
        resp_uid = cliente.get("/api/auditoria/?id_usuario=no_es_id")
        self.assertEqual(resp_uid.status_code, 400)
        self.assertIn("id_usuario", resp_uid.json())

    # =========================================================================
    # La API rechaza los métodos de modificación y eliminación.
    # =========================================================================

    def test_13_metodos_escritura_rechazados_e_inmutabilidad_en_postgresql(self):
        evento = registrar_auditoria(
            usuario=self.admin,
            modulo="SEGURIDAD",
            accion="EVENTO_INMUTABLE",
            entidad_afectada="activo",
            id_registro_afectado=self.activo1.pk,
            detalle_evento="Detalle original inviolable.",
        )

        cliente = self._cliente(self.admin)

        # 1. Intentar POST en /api/auditoria/
        resp_post = cliente.post("/api/auditoria/", {"detalle_evento": "Inyección no autorizada"}, format="json")
        self.assertEqual(resp_post.status_code, 405)

        # 2. Intentar PUT en /api/auditoria/{id}/
        resp_put = cliente.put(f"/api/auditoria/{evento.pk}/", {"detalle_evento": "Modificación alterada"}, format="json")
        self.assertEqual(resp_put.status_code, 405)

        # 3. Intentar PATCH en /api/auditoria/{id}/
        resp_patch = cliente.patch(f"/api/auditoria/{evento.pk}/", {"accion": "ALTERADA"}, format="json")
        self.assertEqual(resp_patch.status_code, 405)

        # 4. Intentar DELETE en /api/auditoria/{id}/
        resp_del = cliente.delete(f"/api/auditoria/{evento.pk}/")
        self.assertEqual(resp_del.status_code, 405)

        # 5. Comprobar que en PostgreSQL el registro permanece 100% inalterado
        evento_bd = BitacoraAuditoria.objects.get(pk=evento.pk)
        self.assertEqual(evento_bd.detalle_evento, "Detalle original inviolable.")
        self.assertEqual(evento_bd.accion, "EVENTO_INMUTABLE")

    def test_14_consulta_sin_efectos_secundarios_ni_eventos_recursivos(self):
        cantidad_inicial = BitacoraAuditoria.objects.count()

        cliente = self._cliente(self.admin)
        for _ in range(3):
            resp = cliente.get("/api/auditoria/")
            self.assertEqual(resp.status_code, 200)

        cantidad_final = BitacoraAuditoria.objects.count()
        self.assertEqual(cantidad_inicial, cantidad_final)


    def test_codigo_inventario_numerico_no_se_confunde_con_id_activo(self):
        self.activo2.codigo_inventario = str(self.activo1.pk)
        self.activo2.save(update_fields=["codigo_inventario"])
        eventos = [registrar_auditoria(
            self.admin, "ACTIVOS", "ACTIVO_MODIFICADO", "activo", activo.pk, "Cambio de prueba"
        ) for activo in (self.activo1, self.activo2)]
        cliente = self._cliente(self.admin)
        for parametro in ("activo", "codigo_inventario"):
            with self.subTest(parametro=parametro):
                respuesta = cliente.get("/api/auditoria/", {parametro: self.activo2.codigo_inventario})
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual([e["id_auditoria"] for e in respuesta.json()["results"]], [eventos[1].pk])

    def test_id_usuario_no_incluye_coincidencias_parciales_de_rut(self):
        self.tecnico.rut = "12345678-9"
        self.tecnico.save(update_fields=["rut"])
        for actor in (self.admin, self.tecnico):
            registrar_auditoria(actor, "ACTIVOS", "CAMBIO", "activo", self.activo1.pk, "Cambio de prueba")
        respuesta = self._cliente(self.admin).get("/api/auditoria/", {"usuario": str(self.admin.pk)})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual({e["id_usuario"] for e in respuesta.json()["results"]}, {self.admin.pk})

    def test_identificadores_invalidos_retornan_400(self):
        cliente = self._cliente(self.admin)
        for parametro in ("id_usuario", "usuario"):
            for valor in ("²", "١", "0", "2147483648", "9" * 5000):
                with self.subTest(parametro=parametro, valor=valor[:20]):
                    respuesta = cliente.get("/api/auditoria/", {parametro: valor})
                    self.assertEqual(respuesta.status_code, 400)
                    self.assertIn(parametro, respuesta.json())
        for valor in ("-1", "1.5", "abc"):
            self.assertEqual(cliente.get("/api/auditoria/", {"id_usuario": valor}).status_code, 400)


    def test_opciones_actor_busca_nombre_completo_y_no_expone_rut(self):
        registrar_auditoria(self.admin, "USUARIOS", "CAMBIO", "usuario", self.admin.pk, "Prueba")
        c = self._cliente(self.admin)
        for texto in ("Admin General", self.admin.correo):
            respuesta = c.get("/api/auditoria/opciones/", {"tipo": "usuario", "search": texto})
            self.assertEqual(respuesta.status_code, 200)
            self.assertEqual(respuesta.json()["results"], [{"id": self.admin.pk, "etiqueta": f"Admin General ({self.admin.correo})"}])
        self.assertNotIn("rut", str(respuesta.json()))
        self.assertEqual(self._cliente(self.tecnico).get("/api/auditoria/opciones/", {"tipo": "usuario"}).status_code, 403)

    def test_opciones_equipo_busca_campos_y_devuelve_codigo_exacto(self):
        for texto in (self.activo1.codigo_inventario, self.activo1.numero_serie, self.modelo.nombre, self.marca.nombre):
            respuesta = self._cliente(self.admin).get("/api/auditoria/opciones/", {"tipo": "activo", "search": texto})
            self.assertEqual(respuesta.status_code, 200)
            self.assertIn(self.activo1.codigo_inventario, [v["codigo"] for v in respuesta.json()["results"]])
        self.assertEqual(self._cliente(self.admin).get("/api/auditoria/opciones/", {"tipo": "activo", "search": "NO_EXISTE"}).json()["results"], [])

    def test_opciones_limite_permisos_validacion_y_solo_lectura(self):
        for i in range(21):
            Activo.objects.create(codigo_inventario=f"LIM-{i:03}", numero_serie=f"LIM-SERIE-{i}",
                                  id_modelo=self.modelo, id_ubicacion=self.ubicacion,
                                  id_estado_activo=self.estado_disponible, valor_adquisicion=1)
        c = self._cliente(self.admin)
        count = BitacoraAuditoria.objects.count()
        respuesta = c.get("/api/auditoria/opciones/", {"tipo": "activo", "search": "LIM-"})
        self.assertEqual(len(respuesta.json()["results"]), 20)
        self.assertTrue(respuesta.json()["has_more"])
        self.assertEqual(c.get("/api/auditoria/opciones/", {"tipo": "invalid"}).status_code, 400)
        self.assertEqual(c.get("/api/auditoria/opciones/", {"tipo": "activo", "search": "a" * 121}).status_code, 400)
        self.assertEqual(c.post("/api/auditoria/opciones/", {}).status_code, 405)
        RolPermiso.objects.filter(rol__nombre="Administrador del sistema", permiso__codigo="AUDITORIA_CONSULTAR").delete()
        self.assertEqual(c.get("/api/auditoria/opciones/", {"tipo": "activo"}).status_code, 403)
        self.assertEqual(BitacoraAuditoria.objects.count(), count)
