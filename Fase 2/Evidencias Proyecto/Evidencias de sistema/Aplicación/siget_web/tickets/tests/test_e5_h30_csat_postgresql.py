"""Pruebas de integración sobre PostgreSQL (test_siget_db) para E5-H30 — Calificación de servicio (CSAT)."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier, Event
from unittest.mock import patch

from django.db import DatabaseError, IntegrityError, connection, connections, transaction
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from activos.models import EstadoActivo
from ordenes_trabajo.models import EstadoOrdenTrabajo
from ordenes_trabajo.services import crear_orden_trabajo
from tickets.models import EstadoTicket, EvaluacionCSAT, Ticket
from tickets.selectors import (
    indicadores_csat_por_tecnico,
    listar_indicadores_csat_tecnicos,
    obtener_evaluacion_csat_ticket,
)
from tickets.services import (
    MENSAJE_CSAT_DUPLICADO,
    MENSAJE_CSAT_NO_CERRADO,
    asignar_ticket,
    cambiar_estado_ticket,
    consultar_evaluacion_csat,
    crear_ticket,
    registrar_evaluacion_csat,
)
from usuarios.models import BitacoraAuditoria, Permiso, Rol, RolPermiso, UsuarioRol
from usuarios.tests.test_integracion_postgresql import PostgreSQLTestBase


@override_settings(
    SIGET_PUBLIC_URL="https://siget.example.invalid",
    RESEND_FROM_EMAIL="SIGET <avisos@example.invalid>",
)
class EvaluacionCSATPostgreSQLTests(PostgreSQLTestBase):
    def setUp(self):
        super().setUp()
        self.assertEqual(connection.settings_dict["NAME"], "test_siget_db")
        self.estados = {e.nombre: e for e in EstadoTicket.objects.all()}
        self.segundo_tecnico = self.usuario(5, "Técnico de soporte")
        self.http_patch = patch("notificaciones.resend_client.requests.post")
        self.http = self.http_patch.start()
        self.addCleanup(self.http_patch.stop)

    def _crear_ticket_en_estado(
        self,
        estado_objetivo: str = "Cerrado",
        *,
        solicitante=None,
        tecnico=None,
        asunto: str = "Incidente de soporte",
    ) -> Ticket:
        """
        Recorre el flujo real de E5-H14 hasta alcanzar el estado solicitado
        (Abierto -> En Proceso -> En Espera / Resuelto -> Cerrado).
        """
        autor = solicitante or self.solicitante
        responsable = tecnico or self.tecnico
        ticket = crear_ticket(autor, asunto, "Detalle técnico del incidente reportado")
        asignar_ticket(
            id_ticket=ticket.pk,
            administrador=self.admin,
            id_tecnico_asignado=responsable.pk,
            motivo="Asignación inicial para atención",
        )
        if estado_objetivo == "Abierto":
            ticket.refresh_from_db()
            return ticket

        secuencia: list[str] = ["En Proceso"]
        if estado_objetivo == "En Espera":
            secuencia.append("En Espera")
        elif estado_objetivo == "Resuelto":
            secuencia.append("Resuelto")
        elif estado_objetivo == "Cerrado":
            secuencia.extend(["Resuelto", "Cerrado"])

        for paso in secuencia:
            ticket = cambiar_estado_ticket(
                id_ticket=ticket.pk,
                tecnico=responsable,
                id_estado_ticket=self.estados[paso].pk,
                mensaje=f"Avance a estado {paso}",
            )
        return ticket

    def _url_csat_api(self, pk: int) -> str:
        return reverse("ticket-csat", kwargs={"pk": pk})

    def _url_detalle_web(self, pk: int) -> str:
        return reverse("tickets_web:detalle", kwargs={"pk": pk})

    def _auditorias_csat(self):
        return BitacoraAuditoria.objects.filter(accion="TICKET_CSAT_REGISTRADO")

    def test_envio_valido_con_comentario_y_sin_comentario_sin_ot(self):
        ticket_con_comentario = self._crear_ticket_en_estado("Cerrado", asunto="Soporte con comentario")
        ticket_sin_comentario = self._crear_ticket_en_estado("Cerrado", asunto="Soporte sin comentario")

        antes = timezone.now()
        resp_con = self.cliente(self.solicitante).post(
            self._url_csat_api(ticket_con_comentario.pk),
            {"calificacion_estrellas": 5, "comentario": "  Excelente atención del técnico.  "},
            format="json",
        )
        self.assertEqual(resp_con.status_code, 201, resp_con.data)
        eval_con = EvaluacionCSAT.objects.get(id_ticket=ticket_con_comentario)
        self.assertEqual(eval_con.calificacion_estrellas, 5)
        self.assertEqual(eval_con.comentario, "Excelente atención del técnico.")
        self.assertEqual(eval_con.id_usuario_id, self.solicitante.pk)
        self.assertGreaterEqual(eval_con.fecha_evaluacion, antes)
        self.assertEqual(resp_con.data["id_evaluacion"], eval_con.pk)
        self.assertEqual(resp_con.data["id_ticket"], ticket_con_comentario.pk)
        self.assertEqual(resp_con.data["codigo_ticket"], ticket_con_comentario.codigo_ticket)
        self.assertEqual(resp_con.data["id_usuario"], self.solicitante.pk)
        self.assertEqual(resp_con.data["calificacion_estrellas"], 5)
        self.assertEqual(resp_con.data["comentario"], "Excelente atención del técnico.")

        resp_sin = self.cliente(self.solicitante).post(
            self._url_csat_api(ticket_sin_comentario.pk),
            {"calificacion_estrellas": 4, "comentario": "   \n\t  "},
            format="json",
        )
        self.assertEqual(resp_sin.status_code, 201, resp_sin_comentario := resp_sin.data)
        eval_sin = EvaluacionCSAT.objects.get(id_ticket=ticket_sin_comentario)
        self.assertEqual(eval_sin.calificacion_estrellas, 4)
        self.assertIsNone(eval_sin.comentario)
        self.assertIsNone(resp_sin_comentario["comentario"])
        self.assertEqual(self._auditorias_csat().count(), 2)
        self.http.assert_not_called()

    def test_ticket_con_ot_cerrada_tambien_puede_evaluarse_al_cerrar_ticket(self):
        activo = self.activo()
        activo.id_estado_activo = EstadoActivo.objects.get(nombre="En revisión")
        activo.save(update_fields=["id_estado_activo"])
        ticket = crear_ticket(self.solicitante, "Reparación física", "No enciende", id_activo=activo.pk)
        asignar_ticket(
            id_ticket=ticket.pk,
            administrador=self.admin,
            id_tecnico_asignado=self.tecnico.pk,
            motivo="Revisión en taller",
        )
        cambiar_estado_ticket(
            id_ticket=ticket.pk,
            tecnico=self.tecnico,
            id_estado_ticket=self.estados["En Proceso"].pk,
            mensaje="En diagnóstico de taller",
        )
        ot = crear_orden_trabajo(ticket.pk, self.tecnico, "Fuente dañada", "Reemplazo de fuente")
        ot.id_estado_ot = EstadoOrdenTrabajo.objects.get(nombre="Completada")
        ot.save(update_fields=["id_estado_ot"])
        cambiar_estado_ticket(
            id_ticket=ticket.pk,
            tecnico=self.tecnico,
            id_estado_ticket=self.estados["Resuelto"].pk,
            mensaje="Equipo reparado",
        )
        cambiar_estado_ticket(
            id_ticket=ticket.pk,
            tecnico=self.tecnico,
            id_estado_ticket=self.estados["Cerrado"].pk,
            mensaje="Cierre definitivo",
        )

        resp = self.cliente(self.solicitante).post(
            self._url_csat_api(ticket.pk),
            {"calificacion_estrellas": 5, "comentario": "Equipo reparado correctamente"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(EvaluacionCSAT.objects.filter(id_ticket=ticket, calificacion_estrellas=5).exists())

    def test_valores_limite_1_y_5_y_conversion_de_formulario(self):
        for puntuacion in (1, 5, "1", "5"):
            with self.subTest(puntuacion=repr(puntuacion)):
                ticket = self._crear_ticket_en_estado("Cerrado")
                resp = self.cliente(self.solicitante).post(
                    self._url_csat_api(ticket.pk),
                    {"calificacion_estrellas": puntuacion},
                    format="json",
                )
                self.assertEqual(resp.status_code, 201, resp.data)
                evaluacion = EvaluacionCSAT.objects.get(id_ticket=ticket)
                self.assertEqual(evaluacion.calificacion_estrellas, int(puntuacion))
                self.assertIsNone(evaluacion.comentario)

    def test_puntuaciones_invalidas_y_campos_manipulados(self):
        ticket = self._crear_ticket_en_estado("Cerrado")
        url = self._url_csat_api(ticket.pk)
        auditorias_base = self._auditorias_csat().count()

        invalidos = (
            {},
            {"calificacion_estrellas": None},
            {"calificacion_estrellas": ""},
            {"calificacion_estrellas": "   "},
            {"calificacion_estrellas": True},
            {"calificacion_estrellas": False},
            {"calificacion_estrellas": 0},
            {"calificacion_estrellas": 6},
            {"calificacion_estrellas": -1},
            {"calificacion_estrellas": 3.0},
            {"calificacion_estrellas": 4.5},
            {"calificacion_estrellas": "3.0"},
            {"calificacion_estrellas": "4,5"},
            {"calificacion_estrellas": "cinco"},
            {"calificacion_estrellas": 5, "comentario": 12345},
        )
        for payload in invalidos:
            with self.subTest(payload=payload):
                resp = self.cliente(self.solicitante).post(url, payload, format="json")
                self.assertEqual(resp.status_code, 400)
                self.assertFalse(EvaluacionCSAT.objects.filter(id_ticket=ticket).exists())
                self.assertEqual(self._auditorias_csat().count(), auditorias_base)

        for valor_directo in (None, True, False, 0, 6, 3.0, Decimal("3.0"), "3.0"):
            with self.subTest(servicio_valor=repr(valor_directo)):
                with self.assertRaises(ValidationError):
                    registrar_evaluacion_csat(
                        id_ticket=ticket.pk,
                        solicitante=self.solicitante,
                        calificacion_estrellas=valor_directo,
                    )

        # Campos manipulados en el cuerpo deben ser ignorados por completo
        otro_ticket = self._crear_ticket_en_estado("Cerrado", solicitante=self.otro)
        antes = timezone.now()
        resp_manipulado = self.cliente(self.solicitante).post(
            url,
            {
                "calificacion_estrellas": 3,
                "comentario": "Atención correcta",
                "id_evaluacion": 999999,
                "id_ticket": otro_ticket.pk,
                "id_usuario": self.admin.pk,
                "id_tecnico_asignado": self.segundo_tecnico.pk,
                "rol": "Administrador del sistema",
                "fecha_evaluacion": "1999-01-01T00:00:00Z",
            },
            format="json",
        )
        self.assertEqual(resp_manipulado.status_code, 201, resp_manipulado.data)
        evaluacion = EvaluacionCSAT.objects.get(id_ticket=ticket)
        self.assertEqual(evaluacion.id_ticket_id, ticket.pk)
        self.assertEqual(evaluacion.id_usuario_id, self.solicitante.pk)
        self.assertGreaterEqual(evaluacion.fecha_evaluacion, antes)
        self.assertFalse(EvaluacionCSAT.objects.filter(id_ticket=otro_ticket).exists())

    def test_ticket_propio_frente_a_ticket_ajeno(self):
        ticket_propio = self._crear_ticket_en_estado("Cerrado", solicitante=self.solicitante)
        url_api = self._url_csat_api(ticket_propio.pk)
        url_web = self._url_detalle_web(ticket_propio.pk)

        # Otro solicitante no puede evaluar ni consultar el ticket ajeno
        resp_post_ajeno = self.cliente(self.otro).post(
            url_api, {"calificacion_estrellas": 1, "comentario": "Intento ajeno"}, format="json"
        )
        self.assertEqual(resp_post_ajeno.status_code, 403)
        self.assertFalse(EvaluacionCSAT.objects.filter(id_ticket=ticket_propio).exists())

        with self.assertRaises(PermissionDenied):
            registrar_evaluacion_csat(
                id_ticket=ticket_propio.pk,
                solicitante=self.otro,
                calificacion_estrellas=1,
            )

        # En portal web el ticket ajeno responde 404 en GET y POST
        self.assertEqual(self.cliente(self.otro).get(url_web).status_code, 404)
        self.assertEqual(
            self.cliente(self.otro).post(url_web, {"calificacion_estrellas": "5"}).status_code,
            404,
        )

        # El solicitante dueño sí puede evaluar y luego consultar
        resp_propio = self.cliente(self.solicitante).post(
            url_api, {"calificacion_estrellas": 5, "comentario": "Ticket propio"}, format="json"
        )
        self.assertEqual(resp_propio.status_code, 201)

        # Incluso después de evaluado, otro solicitante recibe 403 al consultar por API
        self.assertEqual(self.cliente(self.otro).get(url_api).status_code, 403)
        with self.assertRaises(PermissionDenied):
            consultar_evaluacion_csat(id_ticket=ticket_propio.pk, solicitante=self.otro)

    def test_usuario_anonimo_inactivo_y_roles_no_autorizados(self):
        ticket = self._crear_ticket_en_estado("Cerrado")
        url_api = self._url_csat_api(ticket.pk)
        url_web = self._url_detalle_web(ticket.pk)

        # Anónimo, Administrador y Técnico son rechazados en API y Web
        for actor in (None, self.admin, self.tecnico):
            with self.subTest(actor=getattr(actor, "correo", "anonimo")):
                self.assertEqual(
                    self.cliente(actor).post(url_api, {"calificacion_estrellas": 5}, format="json").status_code,
                    403,
                )
                self.assertEqual(self.cliente(actor).get(url_api).status_code, 403)
                self.assertEqual(self.cliente(actor).get(url_web).status_code, 403)
                self.assertEqual(
                    self.cliente(actor).post(url_web, {"calificacion_estrellas": "5"}).status_code,
                    403,
                )
                with self.assertRaises(PermissionDenied):
                    registrar_evaluacion_csat(
                        id_ticket=ticket.pk, solicitante=actor, calificacion_estrellas=5
                    )

        # Solicitante inactivo rechazado
        self.solicitante.activo = False
        self.solicitante.save(update_fields=["activo"])
        self.assertEqual(
            self.cliente(self.solicitante).post(url_api, {"calificacion_estrellas": 5}, format="json").status_code,
            403,
        )
        self.assertEqual(self.cliente(self.solicitante).get(url_api).status_code, 403)
        self.assertEqual(self.cliente(self.solicitante).get(url_web).status_code, 403)
        with self.assertRaises(PermissionDenied):
            registrar_evaluacion_csat(
                id_ticket=ticket.pk, solicitante=self.solicitante, calificacion_estrellas=5
            )
        self.solicitante.activo = True
        self.solicitante.save(update_fields=["activo"])

        # Usuario sin rol de solicitante o con permisos manipulados en otros roles es rechazado
        rol_tecnico = Rol.objects.get(nombre="Técnico de soporte")
        RolPermiso.objects.get_or_create(
            rol=rol_tecnico, permiso=Permiso.objects.get(codigo="TICKET_CREAR")
        )
        self.assertEqual(
            self.cliente(self.tecnico).post(url_api, {"calificacion_estrellas": 5}, format="json").status_code,
            403,
        )

        rol_solicitante = Rol.objects.get(nombre="Usuario solicitante")
        UsuarioRol.objects.filter(usuario=self.solicitante, rol=rol_solicitante).delete()
        self.assertEqual(
            self.cliente(self.solicitante).post(url_api, {"calificacion_estrellas": 5}, format="json").status_code,
            403,
        )
        UsuarioRol.objects.get_or_create(usuario=self.solicitante, rol=rol_solicitante)
        self.assertFalse(EvaluacionCSAT.objects.exists())

    def test_todos_los_estados_anteriores_a_cerrado_incluido_resuelto_son_bloqueados(self):
        auditorias_base = self._auditorias_csat().count()
        for estado in ("Abierto", "En Proceso", "En Espera", "Resuelto"):
            with self.subTest(estado=estado):
                ticket = self._crear_ticket_en_estado(estado, asunto=f"Ticket en {estado}")
                self.assertEqual(ticket.id_estado_ticket.nombre, estado)
                resp = self.cliente(self.solicitante).post(
                    self._url_csat_api(ticket.pk),
                    {"calificacion_estrellas": 5, "comentario": "Intento anticipado"},
                    format="json",
                )
                self.assertEqual(resp.status_code, 400, resp.data)
                self.assertEqual(str(resp.data["detail"]), MENSAJE_CSAT_NO_CERRADO)
                self.assertFalse(EvaluacionCSAT.objects.filter(id_ticket=ticket).exists())

                # En el portal web muestra explicación y bloquea el envío POST
                detalle_get = self.cliente(self.solicitante).get(self._url_detalle_web(ticket.pk))
                self.assertEqual(detalle_get.status_code, 200)
                self.assertNotContains(detalle_get, 'name="calificacion_estrellas"')
                self.assertContains(detalle_get, estado)

                detalle_post = self.cliente(self.solicitante).post(
                    self._url_detalle_web(ticket.pk),
                    {"calificacion_estrellas": "5", "comentario": "Intento web"},
                )
                self.assertEqual(detalle_post.status_code, 200)
                self.assertContains(detalle_post, MENSAJE_CSAT_NO_CERRADO)
                self.assertFalse(EvaluacionCSAT.objects.filter(id_ticket=ticket).exists())

        self.assertEqual(self._auditorias_csat().count(), auditorias_base)

    def test_ticket_inexistente_devuelve_404(self):
        url_api = self._url_csat_api(999999)
        url_web = self._url_detalle_web(999999)

        self.assertEqual(self.cliente(self.solicitante).get(url_api).status_code, 404)
        self.assertEqual(
            self.cliente(self.solicitante).post(url_api, {"calificacion_estrellas": 5}, format="json").status_code,
            404,
        )
        self.assertEqual(self.cliente(self.solicitante).get(url_web).status_code, 404)
        self.assertEqual(
            self.cliente(self.solicitante).post(url_web, {"calificacion_estrellas": "5"}).status_code,
            404,
        )
        with self.assertRaises(NotFound):
            registrar_evaluacion_csat(
                id_ticket=999999, solicitante=self.solicitante, calificacion_estrellas=5
            )
        with self.assertRaises(NotFound):
            consultar_evaluacion_csat(id_ticket=999999, solicitante=self.solicitante)

    def test_evaluacion_previa_en_solo_lectura_y_rechazo_de_segundo_envio(self):
        ticket = self._crear_ticket_en_estado("Cerrado")
        url_api = self._url_csat_api(ticket.pk)

        # Antes de evaluar, GET devuelve 404 sin crear eventos
        self.assertEqual(self.cliente(self.solicitante).get(url_api).status_code, 404)
        self.assertEqual(self._auditorias_csat().count(), 0)

        # Primer envío exitoso
        primera = self.cliente(self.solicitante).post(
            url_api,
            {"calificacion_estrellas": 5, "comentario": "Comentario original"},
            format="json",
        )
        self.assertEqual(primera.status_code, 201)
        self.assertEqual(self._auditorias_csat().count(), 1)

        # Consulta posterior en solo lectura: no duplica evaluación ni auditoría
        for _ in range(2):
            consulta = self.cliente(self.solicitante).get(url_api)
            self.assertEqual(consulta.status_code, 200)
            self.assertEqual(consulta.data["calificacion_estrellas"], 5)
            self.assertEqual(consulta.data["comentario"], "Comentario original")
        self.assertEqual(EvaluacionCSAT.objects.filter(id_ticket=ticket).count(), 1)
        self.assertEqual(self._auditorias_csat().count(), 1)

        # Segundo envío por API es rechazado y conserva la evaluación original intacta
        segunda = self.cliente(self.solicitante).post(
            url_api,
            {"calificacion_estrellas": 1, "comentario": "Intento de sobrescritura"},
            format="json",
        )
        self.assertEqual(segunda.status_code, 400)
        self.assertEqual(str(segunda.data["detail"]), MENSAJE_CSAT_DUPLICADO)

        # Métodos de edición o eliminación no están habilitados (405)
        for metodo in ("put", "patch", "delete"):
            respuesta_metodo = getattr(self.cliente(self.solicitante), metodo)(
                url_api, {"calificacion_estrellas": 2}, format="json"
            )
            self.assertEqual(respuesta_metodo.status_code, 405)

        evaluacion = EvaluacionCSAT.objects.get(id_ticket=ticket)
        self.assertEqual(evaluacion.calificacion_estrellas, 5)
        self.assertEqual(evaluacion.comentario, "Comentario original")
        self.assertEqual(self._auditorias_csat().count(), 1)

    def test_dos_envios_concurrentes_persisten_una_sola_evaluacion(self):
        ticket = self._crear_ticket_en_estado("Cerrado")
        url_api = self._url_csat_api(ticket.pk)
        bloqueado = Event()
        intentando = Event()
        liberar = Event()
        real_auditoria = __import__(
            "tickets.services", fromlist=["registrar_auditoria"]
        ).registrar_auditoria

        def auditar_con_pausa(**kwargs):
            if kwargs.get("accion") == "TICKET_CSAT_REGISTRADO":
                bloqueado.set()
                if not liberar.wait(10):
                    raise TimeoutError("No se liberó la primera transacción CSAT")
            return real_auditoria(**kwargs)

        def enviar(estrellas: int, comentario: str, es_segundo: bool = False) -> tuple[int, dict]:
            try:
                if es_segundo:
                    intentando.set()
                resp = self.cliente(self.solicitante).post(
                    url_api,
                    {"calificacion_estrellas": estrellas, "comentario": comentario},
                    format="json",
                )
                return resp.status_code, resp.data
            finally:
                connections.close_all()

        with (
            patch("tickets.services.registrar_auditoria", side_effect=auditar_con_pausa),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            futuro_1 = pool.submit(enviar, 5, "Primer envío concurrente", False)
            try:
                self.assertTrue(bloqueado.wait(10))
                futuro_2 = pool.submit(enviar, 1, "Segundo envío concurrente", True)
                self.assertTrue(intentando.wait(10))
                self.assertFalse(futuro_2.done())
            finally:
                liberar.set()

            estado_1, datos_1 = futuro_1.result(timeout=15)
            estado_2, datos_2 = futuro_2.result(timeout=15)

        self.assertEqual(sorted([estado_1, estado_2]), [201, 400])
        error_data = datos_2 if estado_2 == 400 else datos_1
        self.assertEqual(str(error_data["detail"]), MENSAJE_CSAT_DUPLICADO)
        self.assertEqual(EvaluacionCSAT.objects.filter(id_ticket=ticket).count(), 1)
        evaluacion = EvaluacionCSAT.objects.get(id_ticket=ticket)
        self.assertEqual(evaluacion.calificacion_estrellas, 5)
        self.assertEqual(evaluacion.comentario, "Primer envío concurrente")
        self.assertEqual(self._auditorias_csat().count(), 1)

    def test_respaldo_unique_integrity_error_dentro_de_transaccion_es_controlado(self):
        ticket = self._crear_ticket_en_estado("Cerrado")
        barrera = Barrier(2)

        # Verifica que si IntegrityError salta por la restricción UNIQUE (p. ej. si dos hilos
        # pasaran la validación previa), el savepoint interno limpia la transacción y devuelve 400.
        with patch.object(
            EvaluacionCSAT.objects,
            "create",
            side_effect=IntegrityError("duplicate key value violates unique constraint"),
        ):
            with transaction.atomic():
                resp = self.cliente(self.solicitante).post(
                    self._url_csat_api(ticket.pk),
                    {"calificacion_estrellas": 4, "comentario": "Prueba IntegrityError"},
                    format="json",
                )
                self.assertEqual(resp.status_code, 400)
                self.assertEqual(str(resp.data["detail"]), MENSAJE_CSAT_DUPLICADO)
                # La transacción exterior sigue siendo utilizable sin TransactionManagementError
                self.assertFalse(EvaluacionCSAT.objects.filter(id_ticket=ticket).exists())
        self.assertIsNotNone(barrera)

    def test_atomicidad_entre_evaluacion_y_auditoria(self):
        ticket = self._crear_ticket_en_estado("Cerrado")
        url_api = self._url_csat_api(ticket.pk)
        auditorias_base = self._auditorias_csat().count()

        # 1. Si falla registrar_auditoria, se revierte la inserción de EvaluacionCSAT
        with patch(
            "tickets.services.registrar_auditoria",
            side_effect=DatabaseError("Fallo simulado en bitácora de auditoría"),
        ):
            with self.assertRaises(DatabaseError):
                self.cliente(self.solicitante).post(
                    url_api,
                    {"calificacion_estrellas": 5, "comentario": "Debe revertirse"},
                    format="json",
                )
        self.assertFalse(EvaluacionCSAT.objects.filter(id_ticket=ticket).exists())
        self.assertEqual(self._auditorias_csat().count(), auditorias_base)

        # 2. Si una transacción exterior hace rollback, se revierten evaluación y auditoría
        with self.assertRaises(RuntimeError), transaction.atomic():
            registrar_evaluacion_csat(
                id_ticket=ticket.pk,
                solicitante=self.solicitante,
                calificacion_estrellas=4,
                comentario="Rollback exterior",
            )
            raise RuntimeError("Rollback deliberado")

        self.assertFalse(EvaluacionCSAT.objects.filter(id_ticket=ticket).exists())
        self.assertEqual(self._auditorias_csat().count(), auditorias_base)

        # 3. En ejecución exitosa se confirma tanto la evaluación como la auditoría
        evaluacion = registrar_evaluacion_csat(
            id_ticket=ticket.pk,
            solicitante=self.solicitante,
            calificacion_estrellas=5,
            comentario="Confirmada",
            ip_origen="127.0.0.1",
        )
        evento = self._auditorias_csat().get()
        self.assertEqual(evento.id_usuario, self.solicitante)
        self.assertEqual(evento.entidad_afectada, "evaluacion_csat")
        self.assertEqual(evento.id_registro_afectado, evaluacion.pk)
        self.assertIn(ticket.codigo_ticket, evento.detalle_evento)
        self.assertIn("Calificación: 5/5", evento.detalle_evento)

    def test_puntuacion_demasiado_larga_se_rechaza_sin_guardar_evaluacion(self):
        ticket = self._crear_ticket_en_estado("Cerrado")
        datos = {"calificacion_estrellas": "9" * 5000}
        auditorias_previas = self._auditorias_csat().count()

        respuesta_api = self.cliente(self.solicitante).post(
            self._url_csat_api(ticket.pk), datos, format="json",
        )
        self.assertEqual(respuesta_api.status_code, 400)
        self.assertIn("calificacion_estrellas", respuesta_api.data)

        respuesta_web = self.cliente(self.solicitante).post(
            self._url_detalle_web(ticket.pk), datos,
        )
        self.assertContains(respuesta_web, "Ingrese un número entero válido entre 1 y 5.")
        self.assertFalse(EvaluacionCSAT.objects.filter(id_ticket=ticket).exists())
        self.assertEqual(self._auditorias_csat().count(), auditorias_previas)
        self.http.assert_not_called()

    def test_filtro_tecnico_no_convertible_devuelve_error_de_validacion(self):
        url = reverse("ticket-indicadores-csat")
        for usuario in (self.admin, self.tecnico):
            for valor in ("²", "9" * 5000):
                with self.subTest(usuario=usuario.pk, longitud=len(valor)):
                    respuesta = self.cliente(usuario).get(url, {"tecnico": valor})
                    self.assertEqual(respuesta.status_code, 400)
                    self.assertIn("tecnico", respuesta.data)
        self.assertFalse(EvaluacionCSAT.objects.exists())
        self.http.assert_not_called()

    def test_indicadores_del_tecnico_calculados_y_actualizados_dinamicamente(self):
        url_lista = reverse("ticket-indicadores-csat")
        url_detalle_tec1 = reverse(
            "ticket-indicadores-csat-detalle", kwargs={"id_tecnico": self.tecnico.pk}
        )
        url_detalle_tec2 = reverse(
            "ticket-indicadores-csat-detalle", kwargs={"id_tecnico": self.segundo_tecnico.pk}
        )

        # Sin evaluaciones: cantidad 0 y promedio None (sin puntuación ficticia)
        inicial = indicadores_csat_por_tecnico(self.tecnico.pk)
        self.assertEqual(inicial["cantidad_evaluaciones"], 0)
        self.assertIsNone(inicial["promedio_estrellas"])

        resp_inicial = self.cliente(self.tecnico).get(url_lista)
        self.assertEqual(resp_inicial.status_code, 200)
        self.assertEqual(resp_inicial.data["id_tecnico"], self.tecnico.pk)
        self.assertEqual(resp_inicial.data["cantidad_evaluaciones"], 0)
        self.assertIsNone(resp_inicial.data["promedio_estrellas"])

        # Primera evaluación (5 estrellas) para self.tecnico modifica el indicador
        t1 = self._crear_ticket_en_estado("Cerrado", tecnico=self.tecnico)
        registrar_evaluacion_csat(
            id_ticket=t1.pk,
            solicitante=self.solicitante,
            calificacion_estrellas=5,
            comentario="Primera calificación",
        )
        tras_una = indicadores_csat_por_tecnico(self.tecnico.pk)
        self.assertEqual(tras_una["cantidad_evaluaciones"], 1)
        self.assertEqual(tras_una["promedio_estrellas"], 5.0)

        # Segunda evaluación (2 estrellas) para self.tecnico actualiza cantidad=2 y promedio=3.5
        t2 = self._crear_ticket_en_estado("Cerrado", tecnico=self.tecnico)
        registrar_evaluacion_csat(
            id_ticket=t2.pk,
            solicitante=self.solicitante,
            calificacion_estrellas=2,
        )
        tras_dos = indicadores_csat_por_tecnico(self.tecnico.pk)
        self.assertEqual(tras_dos["cantidad_evaluaciones"], 2)
        self.assertEqual(tras_dos["promedio_estrellas"], 3.5)

        # El segundo técnico sigue en 0 evaluaciones y promedio None
        ind_tec2 = indicadores_csat_por_tecnico(self.segundo_tecnico.pk)
        self.assertEqual(ind_tec2["cantidad_evaluaciones"], 0)
        self.assertIsNone(ind_tec2["promedio_estrellas"])

        # Permisos API de indicadores:
        # - Administrador puede listar todos o consultar un técnico específico
        resp_admin_lista = self.cliente(self.admin).get(url_lista)
        self.assertEqual(resp_admin_lista.status_code, 200)
        por_id = {item["id_tecnico"]: item for item in resp_admin_lista.data}
        self.assertEqual(por_id[self.tecnico.pk]["cantidad_evaluaciones"], 2)
        self.assertEqual(por_id[self.tecnico.pk]["promedio_estrellas"], 3.5)
        self.assertEqual(por_id[self.segundo_tecnico.pk]["cantidad_evaluaciones"], 0)
        self.assertIsNone(por_id[self.segundo_tecnico.pk]["promedio_estrellas"])

        resp_admin_filtro = self.cliente(self.admin).get(f"{url_lista}?tecnico={self.tecnico.pk}")
        self.assertEqual(resp_admin_filtro.status_code, 200)
        self.assertEqual(resp_admin_filtro.data["promedio_estrellas"], 3.5)

        resp_admin_detalle = self.cliente(self.admin).get(url_detalle_tec2)
        self.assertEqual(resp_admin_detalle.status_code, 200)
        self.assertEqual(resp_admin_detalle.data["cantidad_evaluaciones"], 0)

        # - Técnico solo puede consultar sus propios indicadores
        self.assertEqual(self.cliente(self.tecnico).get(url_detalle_tec1).status_code, 200)
        self.assertEqual(self.cliente(self.tecnico).get(url_detalle_tec2).status_code, 403)
        self.assertEqual(
            self.cliente(self.tecnico).get(f"{url_lista}?tecnico={self.segundo_tecnico.pk}").status_code,
            403,
        )

        # - Solicitante y anónimo no tienen acceso al endpoint de indicadores
        self.assertEqual(self.cliente(self.solicitante).get(url_lista).status_code, 403)
        self.assertEqual(self.cliente(self.solicitante).get(url_detalle_tec1).status_code, 403)
        self.assertEqual(self.cliente().get(url_lista).status_code, 403)
        self.assertEqual(len(listar_indicadores_csat_tecnicos()), 2)

    def test_flujo_real_formulario_web_csrf_prg_y_escape_de_comentarios(self):
        ticket = self._crear_ticket_en_estado("Cerrado")
        url_detalle = self._url_detalle_web(ticket.pk)

        # 1. Protección CSRF activa en el portal web
        cliente_csrf = self.cliente(self.solicitante, csrf=True)
        sin_token = cliente_csrf.post(
            url_detalle,
            {"calificacion_estrellas": "5", "comentario": "Intento sin CSRF"},
        )
        self.assertEqual(sin_token.status_code, 403)
        self.assertFalse(EvaluacionCSAT.objects.filter(id_ticket=ticket).exists())

        # 2. Obtención del formulario en GET con token CSRF
        get_form = cliente_csrf.get(url_detalle)
        self.assertEqual(get_form.status_code, 200)
        self.assertContains(get_form, 'name="calificacion_estrellas"')
        csrf_token = cliente_csrf.cookies["csrftoken"].value

        # 3. Envío con puntuación inválida en Web devuelve errores claros sin persistir
        post_invalido = cliente_csrf.post(
            url_detalle,
            {
                "csrfmiddlewaretoken": csrf_token,
                "calificacion_estrellas": "3.5",
                "comentario": "Puntuación decimal",
            },
        )
        self.assertEqual(post_invalido.status_code, 200)
        self.assertContains(post_invalido, "Ingrese un número entero válido entre 1 y 5.")
        self.assertFalse(EvaluacionCSAT.objects.filter(id_ticket=ticket).exists())

        # 4. Envío válido aplica patrón POST/Redirect/GET y escapa HTML peligroso
        comentario_xss = '<script>alert("csat")</script>\nGracias por la gestión'
        post_valido = cliente_csrf.post(
            url_detalle,
            {
                "csrfmiddlewaretoken": csrf_token,
                "calificacion_estrellas": "5",
                "comentario": comentario_xss,
            },
        )
        self.assertEqual(post_valido.status_code, 302)
        self.assertEqual(post_valido["Location"], url_detalle)

        evaluacion = obtener_evaluacion_csat_ticket(ticket)
        self.assertIsNotNone(evaluacion)
        assert evaluacion is not None
        self.assertEqual(evaluacion.calificacion_estrellas, 5)
        self.assertEqual(evaluacion.comentario, comentario_xss)

        # Primera carga tras redirect muestra confirmación/agradecimiento y vista solo lectura
        primera_vista = cliente_csrf.get(url_detalle)
        self.assertEqual(primera_vista.status_code, 200)
        self.assertContains(
            primera_vista,
            "¡Muchas gracias por calificar nuestro servicio! Tu evaluación fue registrada exitosamente.",
        )
        self.assertContains(primera_vista, "Evaluación registrada en modo de solo lectura.")
        self.assertContains(primera_vista, "5 de 5 estrellas")
        self.assertContains(primera_vista, "&lt;script&gt;alert(&quot;csat&quot;)&lt;/script&gt;")
        self.assertNotContains(primera_vista, '<script>alert("csat")</script>')
        self.assertNotContains(primera_vista, 'name="calificacion_estrellas"')

        # Segunda carga (refresco de página) mantiene solo lectura sin repetir el banner ni reenviar
        segunda_vista = cliente_csrf.get(url_detalle)
        self.assertEqual(segunda_vista.status_code, 200)
        self.assertNotContains(
            segunda_vista,
            "¡Muchas gracias por calificar nuestro servicio! Tu evaluación fue registrada exitosamente.",
        )
        self.assertContains(segunda_vista, "Evaluación registrada en modo de solo lectura.")
        self.assertEqual(EvaluacionCSAT.objects.filter(id_ticket=ticket).count(), 1)

        # Un segundo POST manual sobre el formulario web ya evaluado es rechazado
        segundo_post = cliente_csrf.post(
            url_detalle,
            {
                "csrfmiddlewaretoken": csrf_token,
                "calificacion_estrellas": "1",
                "comentario": "Reenvío forzado",
            },
        )
        self.assertEqual(segundo_post.status_code, 200)
        self.assertContains(segundo_post, MENSAJE_CSAT_DUPLICADO)
        self.assertEqual(EvaluacionCSAT.objects.filter(id_ticket=ticket).count(), 1)
