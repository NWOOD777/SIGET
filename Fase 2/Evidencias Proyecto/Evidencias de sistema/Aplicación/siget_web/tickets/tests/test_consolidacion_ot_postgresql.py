"""Regresión de concurrencia OT y caracterización de comportamientos pendientes.

Los casos pendientes están omitidos expresamente, no son regresiones deliberadas.
La sincronización instrumental solo controla el orden de SQL; no reemplaza servicios.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from unittest.mock import patch

from django.db import connection, connections
from rest_framework.exceptions import ValidationError
from notificaciones.models import Notificacion

from activos.models import EstadoActivo
from asignaciones.models import HistorialEstadoActivo
from ordenes_trabajo.models import Diagnostico, EstadoOrdenTrabajo, OrdenTrabajo
from ordenes_trabajo.services import (
    crear_orden_trabajo, iniciar_reparacion, pausar_orden_trabajo,
    reanudar_orden_trabajo,
)
from tickets.services import crear_ticket
from tickets.tests.test_estados_tickets import EstadoFixture
from usuarios.models import BitacoraAuditoria


class ConsolidacionOTFixture(EstadoFixture):
    def setUp(self):
        super().setUp()
        # También acota la conexión principal si una implementación futura cambia los bloqueos.
        with connection.cursor() as cursor:
            cursor.execute("SET lock_timeout = '4s'")
            cursor.execute("SET statement_timeout = '8s'")
        self.activo_ot = self.activo()
        self.activo_ot.id_estado_activo = EstadoActivo.objects.get(nombre="En revisión")
        self.activo_ot.save(update_fields=["id_estado_activo"])
        self.ticket.id_activo = self.activo_ot
        self.ticket.save(update_fields=["id_activo"])

    def crear_ot(self, ticket=None):
        return crear_orden_trabajo(
            (ticket or self.ticket).pk, self.tecnico, "Falla de prueba", "Diagnóstico inicial"
        )

    def segunda_ot(self):
        activo = self.activo()
        activo.id_estado_activo = EstadoActivo.objects.get(nombre="En revisión")
        activo.save(update_fields=["id_estado_activo"])
        ticket = crear_ticket(self.otro, "Otra falla", "Descripción", id_activo=activo.pk)
        return self.crear_ot(ticket)


class CaracterizacionIntegracionOTTests(ConsolidacionOTFixture):
    def test_dos_tickets_del_mismo_activo_rechaza_segunda_ot_sin_efectos(self):
        primera = self.crear_ot()
        otro_ticket = crear_ticket(
            self.otro, "Otro incidente", "Descripción", id_activo=self.activo_ot.pk
        )
        antes = (Diagnostico.objects.count(), BitacoraAuditoria.objects.count(), Notificacion.objects.count())
        with self.assertRaises(ValidationError) as error:
            self.crear_ot(otro_ticket)
        self.assertIn("id_activo", error.exception.detail)
        self.assertEqual(OrdenTrabajo.objects.count(), 1)
        self.assertEqual(OrdenTrabajo.objects.get().pk, primera.pk)
        self.assertEqual((Diagnostico.objects.count(), BitacoraAuditoria.objects.count(), Notificacion.objects.count()), antes)

    def carrera_controlada(self, primero, segundo, accion, rollback=False):
        tomado, intentando, continuar = Event(), Event(), Event()
        from ordenes_trabajo.services import registrar_auditoria as real

        def auditar(**datos):
            if datos["accion"] == accion and not tomado.is_set():
                tomado.set()
                if not continuar.wait(10):
                    raise TimeoutError("No se liberó la transacción")
                if rollback:
                    raise ValidationError("Rollback instrumental")
            return real(**datos)

        def ejecutar(operacion, observar=False):
            db = connections["default"]
            self.assertEqual(db.settings_dict["NAME"], "test_siget_db")

            def observar_sql(execute, sql, params, many, context):
                if "FOR UPDATE" in sql or "pg_advisory_xact_lock" in sql:
                    intentando.set()
                return execute(sql, params, many, context)

            try:
                with db.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '4s'")
                    cursor.execute("SET statement_timeout = '8s'")
                if observar:
                    with db.execute_wrapper(observar_sql):
                        operacion()
                else:
                    operacion()
                return 200
            except ValidationError:
                return 400
            finally:
                db.close()

        with patch("ordenes_trabajo.services.registrar_auditoria", side_effect=auditar), ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(ejecutar, primero)
            try:
                self.assertTrue(tomado.wait(10))
                b = pool.submit(ejecutar, segundo, True)
                self.assertTrue(intentando.wait(10))
                self.assertFalse(b.done())
            finally:
                continuar.set()
            return a.result(timeout=15), b.result(timeout=15)

    def test_reanudar_diagnostico_conserva_fase_y_activo_en_revision(self):
        orden = self.crear_ot()
        pausar_orden_trabajo(orden.pk, self.tecnico, "Esperando información")
        reanudar_orden_trabajo(orden.pk, self.tecnico)
        orden.refresh_from_db()
        self.activo_ot.refresh_from_db()
        self.assertEqual(orden.id_estado_ot.nombre, "En Diagnóstico")
        self.assertEqual(self.activo_ot.id_estado_activo.nombre, "En revisión")
        self.assertIsNone(orden.justificacion_pausa)
        for accion in ("OT_PAUSADA", "OT_REANUDADA"):
            self.assertEqual(BitacoraAuditoria.objects.filter(
                accion=accion, id_registro_afectado=orden.pk,
            ).count(), 1)

    def test_estados_vigentes_bloquean_duplicado_y_completada_no_lo_bloquea(self):
        orden = self.crear_ot()
        otro = crear_ticket(self.otro, "Nueva falla", "Descripción", id_activo=self.activo_ot.pk)
        for nombre in ("En Diagnóstico", "En Reparación", "Pausada"):
            with self.subTest(estado=nombre):
                orden.id_estado_ot = EstadoOrdenTrabajo.objects.get(nombre=nombre)
                orden.save(update_fields=["id_estado_ot"])
                with self.assertRaises(ValidationError) as error:
                    self.crear_ot(otro)
                self.assertIn("id_activo", error.exception.detail)
        orden.id_estado_ot = EstadoOrdenTrabajo.objects.get(nombre="Completada")
        orden.save(update_fields=["id_estado_ot"])
        self.assertEqual(self.crear_ot(otro).id_ticket_id, otro.pk)
        with self.assertRaises(ValidationError) as error:
            self.crear_ot()
        self.assertIn("id_ticket", error.exception.detail)

    def test_rollback_creacion_concurrente_y_inicio_sin_efectos_parciales(self):
        otro = crear_ticket(self.otro, "Otra falla", "Descripción", id_activo=self.activo_ot.pk)
        antes = (BitacoraAuditoria.objects.count(), Notificacion.objects.count())
        resultados = self.carrera_controlada(
            self.crear_ot, lambda: self.crear_ot(otro), "OT_CREADA", rollback=True,
        )
        self.assertEqual(resultados, (400, 200))
        orden = OrdenTrabajo.objects.get()
        self.assertEqual(orden.id_ticket_id, otro.pk)
        self.assertEqual(Diagnostico.objects.count(), 1)
        self.assertEqual((BitacoraAuditoria.objects.count(), Notificacion.objects.count()), (antes[0]+1, antes[1]))
        historial = HistorialEstadoActivo.objects.count()
        with patch("ordenes_trabajo.services.registrar_auditoria", side_effect=ValidationError("Fallo de auditoría")):
            with self.assertRaises(ValidationError):
                iniciar_reparacion(orden.pk, self.tecnico)
        orden.refresh_from_db()
        self.activo_ot.refresh_from_db()
        self.assertEqual(orden.id_estado_ot.nombre, "En Diagnóstico")
        self.assertEqual(self.activo_ot.id_estado_activo.nombre, "En revisión")
        self.assertEqual(HistorialEstadoActivo.objects.count(), historial)
        self.assertEqual((BitacoraAuditoria.objects.count(), Notificacion.objects.count()), (antes[0]+1, antes[1]))

    def test_inicio_y_pausa_concurrentes_serializan_ambos_ordenes(self):
        for repeticion in range(3):
            for pausa_primero in (True, False):
                with self.subTest(repeticion=repeticion, pausa_primero=pausa_primero):
                    orden = self.segunda_ot()
                    iniciar = lambda: iniciar_reparacion(orden.pk, self.tecnico)
                    pausar = lambda: pausar_orden_trabajo(orden.pk, self.tecnico, "Pausa concurrente")
                    if pausa_primero:
                        resultados = self.carrera_controlada(pausar, iniciar, "OT_PAUSADA")
                        self.assertEqual(resultados, (200, 400))
                    else:
                        resultados = self.carrera_controlada(iniciar, pausar, "REPARACION_INICIADA")
                        self.assertEqual(resultados, (200, 200))
                    orden.refresh_from_db()
                    activo = orden.id_ticket.id_activo
                    activo.refresh_from_db()
                    self.assertEqual(orden.id_estado_ot.nombre, "Pausada")
                    self.assertEqual(activo.id_estado_activo.nombre, "En revisión" if pausa_primero else "En reparación")
                    self.assertEqual(BitacoraAuditoria.objects.filter(accion="REPARACION_INICIADA", id_registro_afectado=orden.pk).count(), int(not pausa_primero))
                    self.assertEqual(BitacoraAuditoria.objects.filter(accion="OT_PAUSADA", id_registro_afectado=orden.pk).count(), 1)

    def test_pausa_y_reanudacion_ot_distintas_con_limites_de_bloqueo(self):
        """D: ambas operaciones deben confirmar; cualquier conflicto falla la prueba."""
        primera = self.crear_ot()
        iniciar_reparacion(primera.pk, self.tecnico)
        segunda = self.segunda_ot()
        pausar_orden_trabajo(segunda.pk, self.tecnico, "Pausa previa")
        barrera = Barrier(2, timeout=10)

        def ejecutar(pk, pausar):
            db = connections["default"]
            self.assertEqual(db.settings_dict["NAME"], "test_siget_db")
            observado = False

            def despues_de_bloquear(execute, sql, params, many, context):
                nonlocal observado
                resultado = execute(sql, params, many, context)
                if not observado and 'FROM "orden_trabajo"' in sql and "FOR UPDATE" in sql:
                    observado = True
                    barrera.wait()
                return resultado

            try:
                with db.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '4s'")
                    cursor.execute("SET statement_timeout = '8s'")
                with db.execute_wrapper(despues_de_bloquear):
                    if pausar:
                        pausar_orden_trabajo(pk, self.tecnico, "Pausa simultánea")
                    else:
                        reanudar_orden_trabajo(pk, self.tecnico)
                return "ok"
            finally:
                db.close()

        for repeticion in range(3):
            with self.subTest(repeticion=repeticion):
                antes = BitacoraAuditoria.objects.count()
                with ThreadPoolExecutor(max_workers=2) as pool:
                    a = pool.submit(ejecutar, primera.pk, True)
                    b = pool.submit(ejecutar, segunda.pk, False)
                    resultados = (a.result(timeout=20), b.result(timeout=20))
                self.assertEqual(resultados, ("ok", "ok"))
                primera.refresh_from_db()
                segunda.refresh_from_db()
                self.assertEqual(primera.id_estado_ot.nombre, "Pausada")
                self.assertEqual(segunda.id_estado_ot.nombre, "En Diagnóstico")
                self.assertEqual(BitacoraAuditoria.objects.count(), antes + 2)
                reanudar_orden_trabajo(primera.pk, self.tecnico)
                pausar_orden_trabajo(segunda.pk, self.tecnico, "Pausa previa")

    def test_esperado_rechazar_segunda_ot_vigente_por_activo(self):
        for repeticion in range(3):
            with self.subTest(repeticion=repeticion):
                activo = self.activo()
                activo.id_estado_activo = EstadoActivo.objects.get(nombre="En revisión")
                activo.save(update_fields=["id_estado_activo"])
                a = crear_ticket(self.solicitante, "Incidente A", "Descripción", id_activo=activo.pk)
                b = crear_ticket(self.otro, "Incidente B", "Descripción", id_activo=activo.pk)
                antes = (OrdenTrabajo.objects.count(), Diagnostico.objects.count(), BitacoraAuditoria.objects.count(), Notificacion.objects.count())
                resultados = self.carrera_controlada(lambda: self.crear_ot(a), lambda: self.crear_ot(b), "OT_CREADA")
                self.assertEqual(resultados, (200, 400))
                self.assertEqual((OrdenTrabajo.objects.count(), Diagnostico.objects.count(), BitacoraAuditoria.objects.count(), Notificacion.objects.count()), (antes[0]+1, antes[1]+1, antes[2]+1, antes[3]))
                self.assertEqual(OrdenTrabajo.objects.filter(id_ticket__id_activo=activo).count(), 1)

    def test_esperado_reanudar_con_estado_de_activo_coherente(self):
        orden = self.crear_ot()
        pausar_orden_trabajo(orden.pk, self.tecnico, "Espera")
        reanudar_orden_trabajo(orden.pk, self.tecnico)
        orden.refresh_from_db()
        self.activo_ot.refresh_from_db()
        self.assertEqual(orden.id_estado_ot.nombre, "En Diagnóstico")
        self.assertEqual(self.activo_ot.id_estado_activo.nombre, "En revisión")
        iniciar_reparacion(orden.pk, self.tecnico)
        pausar_orden_trabajo(orden.pk, self.tecnico, "Repuesto")
        reanudar_orden_trabajo(orden.pk, self.tecnico)
        orden.refresh_from_db()
        self.activo_ot.refresh_from_db()
        self.assertEqual(orden.id_estado_ot.nombre, "En Reparación")
        self.assertEqual(self.activo_ot.id_estado_activo.nombre, "En reparación")

    def test_esperado_inicio_no_sobrescribe_pausa_concurrente(self):
        orden = self.crear_ot()
        resultados = self.carrera_controlada(
            lambda: pausar_orden_trabajo(orden.pk, self.tecnico, "Pausa"),
            lambda: iniciar_reparacion(orden.pk, self.tecnico), "OT_PAUSADA", rollback=True,
        )
        self.assertEqual(resultados, (400, 200))
        orden.refresh_from_db()
        self.assertEqual(orden.id_estado_ot.nombre, "En Reparación")
        self.assertFalse(BitacoraAuditoria.objects.filter(accion="OT_PAUSADA").exists())
        self.assertIsNone(orden.justificacion_pausa)

    def test_esperado_ot_distintas_sin_contencion_del_catalogo(self):
        orden = self.crear_ot()
        sql_bloqueos = []

        def observar(execute, sql, params, many, context):
            if "FOR UPDATE" in sql:
                sql_bloqueos.append(sql)
            return execute(sql, params, many, context)

        with connection.execute_wrapper(observar):
            iniciar_reparacion(orden.pk, self.tecnico)
            pausar_orden_trabajo(orden.pk, self.tecnico, "Espera")
            reanudar_orden_trabajo(orden.pk, self.tecnico)
        self.assertTrue(sql_bloqueos)
        for sql in sql_bloqueos:
            self.assertTrue('FOR UPDATE OF "orden_trabajo"' in sql or 'FOR UPDATE OF "activo"' in sql, sql)


class ContratosHTTPOTTests(ConsolidacionOTFixture):
    def post(self, sufijo="", datos=None):
        return self.cliente(self.tecnico).post(
            "/api/ordenes-trabajo/" + sufijo, datos or {}, format="json"
        )

    def test_creacion_campos_ausentes_vacios_e_identificadores_invalidos(self):
        casos = [{}]
        casos += [{"id_ticket": v} for v in (None, "", "abc", -1, 1.5, [], {}, True)]
        casos += [
            {"id_ticket": self.ticket.pk},
            {"id_ticket": self.ticket.pk, "descripcion_falla": " ", "procedimiento_inicial": "Revisión"},
            {"id_ticket": self.ticket.pk, "descripcion_falla": "Falla", "procedimiento_inicial": " "},
            {"id_ticket": self.ticket.pk, "descripcion_falla": "Falla", "procedimiento_inicial": "Revisión", "es_reparable": "true"},
        ]
        antes = BitacoraAuditoria.objects.count()
        for datos in casos:
            with self.subTest(datos=datos):
                self.assertEqual(self.post(datos=datos).status_code, 400)
        self.assertFalse(OrdenTrabajo.objects.exists())
        self.assertFalse(Diagnostico.objects.exists())
        self.assertEqual(BitacoraAuditoria.objects.count(), antes)

    def test_textos_con_tipo_incorrecto_devuelven_400_sin_efectos(self):
        base = {"id_ticket": self.ticket.pk, "descripcion_falla": "Falla", "procedimiento_inicial": "Revisión"}
        for campo in ("descripcion_falla", "procedimiento_inicial"):
            for valor in (7, ["texto"], {"texto": "valor"}):
                with self.subTest(campo=campo, valor=valor):
                    respuesta = self.post(datos={**base, campo: valor})
                    self.assertEqual(respuesta.status_code, 400)
                    self.assertIn(campo, respuesta.data)
        self.assertFalse(OrdenTrabajo.objects.exists())
        orden = self.crear_ot()
        antes = (BitacoraAuditoria.objects.count(), Notificacion.objects.count())
        for ruta, datos in (
            (f"{orden.pk}/pausar/", {"justificacion": 7}),
            (f"{orden.pk}/reasignar/", {"id_tecnico_responsable": self.segundo.pk, "observaciones": ["motivo"]}),
        ):
            with self.subTest(ruta=ruta):
                self.assertEqual(self.post(ruta, datos).status_code, 400)
        self.assertEqual(OrdenTrabajo.objects.count(), 1)
        self.assertFalse(BitacoraAuditoria.objects.filter(accion="OT_PAUSADA").exists())
        self.assertFalse(BitacoraAuditoria.objects.filter(accion="OT_REASIGNADA").exists())
        self.assertEqual((BitacoraAuditoria.objects.count(), Notificacion.objects.count()), antes)

    def test_identificador_unicode_digit_no_convertible_devuelve_400(self):
        respuesta = self.post(datos={"id_ticket": "²"})
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("id_ticket", respuesta.data)
        self.assertFalse(OrdenTrabajo.objects.exists())

    def test_pausa_y_reasignacion_exigen_datos(self):
        orden = self.crear_ot()
        for datos in ({}, {"justificacion": " "}, {"justificacion": None}):
            self.assertEqual(self.post(f"{orden.pk}/pausar/", datos).status_code, 400)
        for datos in ({}, {"id_tecnico_responsable": "abc"},
                      {"id_tecnico_responsable": self.segundo.pk},
                      {"id_tecnico_responsable": self.segundo.pk, "observaciones": " "}):
            self.assertEqual(self.post(f"{orden.pk}/reasignar/", datos).status_code, 400)
        orden.refresh_from_db()
        self.assertEqual(orden.id_estado_ot.nombre, "En Diagnóstico")
        self.assertEqual(orden.id_tecnico_responsable_id, self.tecnico.pk)

    def test_ot_inexistente_historial_404_mutaciones_400(self):
        """F: congela la diferencia actual para no cambiar contratos inadvertidamente."""
        pk = 999999
        self.assertFalse(OrdenTrabajo.objects.filter(pk=pk).exists())
        self.assertEqual(self.cliente(self.tecnico).get(
            f"/api/ordenes-trabajo/{pk}/historial/"
        ).status_code, 404)
        for accion, datos in (
            ("iniciar-reparacion", {}), ("reanudar", {}),
            ("pausar", {"justificacion": "Prueba"}),
            ("reasignar", {"id_tecnico_responsable": self.segundo.pk, "observaciones": "Prueba"}),
        ):
            with self.subTest(accion=accion):
                respuesta = self.post(f"{pk}/{accion}/", datos)
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn("id_orden", respuesta.data)

    def test_listado_creacion_tecnicos_historial_y_operaciones_conservan_formato(self):
        respuesta = self.post(datos={"id_ticket": self.ticket.pk, "descripcion_falla": "Falla", "procedimiento_inicial": "Revisión"})
        self.assertEqual(respuesta.status_code, 201)
        campos = {"id_orden", "codigo_ot", "id_ticket", "codigo_ticket", "id_activo",
                  "codigo_inventario", "estado", "falla_reportada", "diagnostico",
                  "procedimiento_inicial", "es_reparable", "fecha_inicio", "fecha_termino",
                  "justificacion_pausa", "id_tecnico_responsable", "tecnico_responsable"}
        self.assertEqual(set(respuesta.data), campos)
        pk = respuesta.data["id_orden"]
        cliente = self.cliente(self.tecnico)
        listado = cliente.get("/api/ordenes-trabajo/")
        self.assertEqual(listado.status_code, 200)
        self.assertIsInstance(listado.data, list)
        self.assertEqual(set(listado.data[0]), campos)
        tecnicos = cliente.get("/api/ordenes-trabajo/tecnicos-disponibles/")
        self.assertEqual(tecnicos.status_code, 200)
        self.assertEqual(set(tecnicos.data[0]), {"id_usuario", "nombre", "correo"})
        for accion, datos in (
            ("iniciar-reparacion", {}), ("pausar", {"justificacion": "Espera"}),
            ("reanudar", {}),
            ("reasignar", {"id_tecnico_responsable": self.segundo.pk, "observaciones": "Turno"}),
        ):
            resultado = self.post(f"{pk}/{accion}/", datos)
            self.assertEqual(resultado.status_code, 200, resultado.data)
            self.assertEqual(set(resultado.data), campos)
        historial = cliente.get(f"/api/ordenes-trabajo/{pk}/historial/")
        self.assertEqual(historial.status_code, 200)
        self.assertEqual(set(historial.data[0]), {"id_auditoria", "fecha", "accion", "usuario", "detalles"})
        for usuario in (self.admin, self.solicitante):
            self.assertEqual(self.cliente(usuario).get("/api/ordenes-trabajo/").status_code, 403)

    def test_esperado_entradas_mal_tipadas_siempre_400_sin_efectos(self):
        orden = self.crear_ot()
        antes = (OrdenTrabajo.objects.values().get(pk=orden.pk), Diagnostico.objects.count(),
                 BitacoraAuditoria.objects.count(), Notificacion.objects.count())
        invalidos = (None, "", " ", -1, 0, 2147483648, 10**100, True, False,
                     1.0, 1.5, "1.0", "²", "١", "１", "9"*5000, [], {})
        for valor in invalidos:
            with self.subTest(valor=str(valor)[:40]):
                datos = {"id_ticket": valor, "descripcion_falla": "Falla", "procedimiento_inicial": "Revisión"}
                respuesta = self.post(datos=datos)
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn("id_ticket", respuesta.data)
                respuesta = self.post(f"{orden.pk}/reasignar/", {
                    "id_tecnico_responsable": valor, "observaciones": "Cambio",
                })
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn("id_tecnico_responsable", respuesta.data)
        self.assertEqual((OrdenTrabajo.objects.values().get(pk=orden.pk), Diagnostico.objects.count(),
                          BitacoraAuditoria.objects.count(), Notificacion.objects.count()), antes)

    def test_rutas_invalidas_y_fuera_de_rango_no_producen_errores_internos(self):
        cliente = self.cliente(self.tecnico)
        for identificador in ("-1", "abc", "²", "١", "True"):
            for accion in ("historial", "iniciar-reparacion", "pausar", "reasignar", "reanudar"):
                with self.subTest(identificador=identificador, accion=accion):
                    ruta = f"/api/ordenes-trabajo/{identificador}/{accion}/"
                    respuesta = cliente.get(ruta) if accion == "historial" else cliente.post(ruta, {}, format="json")
                    self.assertEqual(respuesta.status_code, 404)
        for identificador in (0, 2147483648, 10**100):
            for accion in ("historial", "iniciar-reparacion", "pausar", "reasignar", "reanudar"):
                with self.subTest(identificador=identificador, accion=accion):
                    ruta = f"/api/ordenes-trabajo/{identificador}/{accion}/"
                    respuesta = cliente.get(ruta) if accion == "historial" else cliente.post(ruta, {}, format="json")
                    self.assertEqual(respuesta.status_code, 400)
                    self.assertIn("id_orden", respuesta.data)

    def test_cuerpos_no_objeto_rechazados_en_todas_las_escrituras(self):
        import json
        orden = self.crear_ot()
        antes = (OrdenTrabajo.objects.values().get(pk=orden.pk), BitacoraAuditoria.objects.count(), Notificacion.objects.count())
        for sufijo in ("", f"{orden.pk}/iniciar-reparacion/", f"{orden.pk}/pausar/",
                       f"{orden.pk}/reasignar/", f"{orden.pk}/reanudar/"):
            for cuerpo in (None, [], [1], "texto", 7, True):
                with self.subTest(sufijo=sufijo, cuerpo=cuerpo):
                    respuesta = self.cliente(self.tecnico).post(
                        "/api/ordenes-trabajo/" + sufijo,
                        data=json.dumps(cuerpo), content_type="application/json",
                    )
                    self.assertEqual(respuesta.status_code, 400)
        self.assertEqual((OrdenTrabajo.objects.values().get(pk=orden.pk), BitacoraAuditoria.objects.count(), Notificacion.objects.count()), antes)

    def test_sin_cuerpo_y_campos_extra_conservan_compatibilidad_pyside(self):
        respuesta = self.post(datos={
            "id_ticket": str(self.ticket.pk), "descripcion_falla": "  Falla  ",
            "procedimiento_inicial": "  Revisión  ", "campo_extra": "ignorado",
        })
        self.assertEqual(respuesta.status_code, 201)
        self.assertTrue(respuesta.data["es_reparable"])
        self.assertEqual(respuesta.data["diagnostico"], "Falla")
        pk = respuesta.data["id_orden"]
        cliente = self.cliente(self.tecnico)
        self.assertEqual(cliente.post(f"/api/ordenes-trabajo/{pk}/iniciar-reparacion/").status_code, 200)
        self.assertEqual(self.post(f"{pk}/pausar/", {"justificacion": "Espera"}).status_code, 200)
        self.assertEqual(cliente.post(f"/api/ordenes-trabajo/{pk}/reanudar/").status_code, 200)
