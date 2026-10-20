"""Aceptación de E3-H9 sobre REST y PostgreSQL; solo se escribe en la base test_."""

import json
from datetime import datetime, timedelta

from django.db import connection
from django.utils import timezone

from activos.models import Activo, EstadoActivo, ModeloActivo
from asignaciones.models import (
    Asignacion,
    DevolucionActivo,
    EstadoAsignacion,
    EstadoSolicitudAsignacion,
    HistorialEstadoActivo,
    SolicitudAsignacion,
)
from usuarios.models import BitacoraAuditoria, Permiso, Rol, RolPermiso, UsuarioRol
from usuarios.tests.test_integracion_postgresql import PostgreSQLTestBase


class ConsultarAsignacionesPostgreSQLTests(PostgreSQLTestBase):
    def setUp(self):
        super().setUp()
        self.assertTrue(str(connection.settings_dict["NAME"]).startswith("test_"))
        self.solicitante.nombres = "Alicia"
        self.solicitante.apellidos = "Fuentes"
        self.solicitante.save(update_fields=["nombres", "apellidos"])
        self.modelo_otro = ModeloActivo.objects.create(
            id_categoria=self.categoria, id_marca=self.modelo.id_marca, nombre="Modelo alternativo",
        )
        self.primera = self.asignacion(self.solicitante, "Activa", 3)
        self.finalizada = self.asignacion(self.solicitante, "Finalizada", 2, self.modelo_otro)
        self.ajena = self.asignacion(self.otro, "Activa", 1, self.modelo_otro)

    def asignacion(self, usuario, estado, dias, modelo=None):
        activo = self.activo()
        activo.id_modelo = modelo or self.modelo
        activo.id_estado_activo = EstadoActivo.objects.get(
            nombre="Asignado" if estado == "Activa" else "Disponible",
        )
        activo.save(update_fields=["id_modelo", "id_estado_activo"])
        fecha = timezone.now() - timedelta(days=dias)
        solicitud = SolicitudAsignacion.objects.create(
            id_usuario=usuario, id_categoria=self.categoria,
            id_estado_solicitud=EstadoSolicitudAsignacion.objects.get(nombre="Atendida"),
            id_administrador_resolutor=self.admin,
            fecha_solicitud=fecha - timedelta(days=2),
            fecha_resolucion=fecha - timedelta(days=1), motivo="Equipo para trabajo",
        )
        return Asignacion.objects.create(
            id_solicitud=solicitud, id_activo=activo, id_tecnico_entrega=self.tecnico,
            id_estado_asignacion=EstadoAsignacion.objects.get(nombre=estado),
            fecha_entrega=fecha, fecha_devolucion_prevista=None,
            fecha_finalizacion=fecha + timedelta(hours=1) if estado == "Finalizada" else None,
        )

    def listado(self, parametros=None, usuario=None):
        response = self.cliente(usuario or self.admin).get("/api/asignaciones/", parametros or {})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsInstance(response.data, list)
        return response

    def ids(self, parametros=None, usuario=None):
        return [item["id_asignacion"] for item in self.listado(parametros, usuario).data]

    def test_administrador_y_tecnico_consultan_todos_ordenados_por_entrega(self):
        for usuario in (self.admin, self.tecnico):
            with self.subTest(usuario=usuario.pk):
                self.assertEqual(self.ids(usuario=usuario), [self.ajena.pk, self.finalizada.pk, self.primera.pk])

    def test_busqueda_por_usuario_id_correo_rut_nombres_y_apellidos(self):
        for criterio in (
            str(self.solicitante.pk), self.solicitante.correo.upper(), self.solicitante.rut,
            "alicia", "FUENTES",
        ):
            with self.subTest(criterio=criterio):
                self.assertEqual(self.ids({"usuario": criterio}), [self.finalizada.pk, self.primera.pk])

    def test_busqueda_por_equipo_id_codigo_serie_modelo_y_alias_activo(self):
        activo = self.primera.id_activo
        for parametro in ("equipo", "activo"):
            for criterio in (str(activo.pk), activo.codigo_inventario.lower(), activo.numero_serie.lower(), self.modelo.nombre):
                with self.subTest(parametro=parametro, criterio=criterio):
                    self.assertEqual(self.ids({parametro: criterio}), [self.primera.pk])

    def test_equipo_tiene_precedencia_sobre_alias_activo(self):
        self.assertEqual(self.ids({"equipo": self.primera.id_activo_id, "activo": self.ajena.id_activo_id}), [self.primera.pk])

    def test_estados_activa_y_finalizada_por_identificador_y_nombre(self):
        for estado, esperados in (
            (self.primera.id_estado_asignacion, [self.ajena.pk, self.primera.pk]),
            (self.finalizada.id_estado_asignacion, [self.finalizada.pk]),
        ):
            for criterio in (str(estado.pk), estado.nombre.swapcase()):
                with self.subTest(criterio=criterio):
                    self.assertEqual(self.ids({"estado": criterio}), esperados)

    def test_combinacion_de_usuario_equipo_y_estado(self):
        filtros = {"usuario": self.solicitante.correo, "equipo": self.modelo_otro.nombre, "estado": "Finalizada"}
        self.assertEqual(self.ids(filtros), [self.finalizada.pk])
        self.assertEqual(self.ids({**filtros, "estado": "Activa"}), [])

    def test_busqueda_general_por_equipo_usuario_e_identificador(self):
        for criterio, esperados in (
            (self.primera.id_activo.codigo_inventario, [self.primera.pk]),
            (self.primera.id_activo.numero_serie, [self.primera.pk]),
            (self.solicitante.correo, [self.finalizada.pk, self.primera.pk]),
            (self.solicitante.rut, [self.finalizada.pk, self.primera.pk]),
            ("ALICIA", [self.finalizada.pk, self.primera.pk]),
            ("Fuentes", [self.finalizada.pk, self.primera.pk]),
        ):
            with self.subTest(criterio=criterio):
                self.assertEqual(self.ids({"search": criterio}), esperados)
        # Un id también puede coincidir con datos del equipo o usuario: acotar
        # por equipo evita asumir que el buscador numérico es exclusivamente ID.
        self.assertEqual(self.ids({"search": str(self.primera.pk), "equipo": self.primera.id_activo_id}), [self.primera.pk])

    def test_sin_coincidencias_y_filtros_vacios(self):
        for parametro in ("usuario", "equipo", "activo", "estado", "search"):
            with self.subTest(parametro=parametro):
                self.assertEqual(self.ids({parametro: "NO-EXISTE-XYZ"}), [])
        self.assertEqual(self.ids({"usuario": " ", "equipo": " ", "estado": " ", "search": " "}), self.ids())

    def test_solicitante_no_amplia_alcance_manipulando_filtros(self):
        self.assertEqual(self.ids(usuario=self.solicitante), [self.finalizada.pk, self.primera.pk])
        self.assertEqual(self.ids({"usuario": self.otro.pk}, self.solicitante), [self.finalizada.pk, self.primera.pk])
        for filtros in (
            {"equipo": self.ajena.id_activo_id}, {"search": self.otro.correo},
            {"usuario": self.otro.pk, "equipo": self.ajena.id_activo_id, "estado": "Activa"},
        ):
            with self.subTest(filtros=filtros):
                self.assertEqual(self.ids(filtros, self.solicitante), [])

    def test_detalle_propio_administrativo_tecnico_y_rechazo_ajeno(self):
        url = f"/api/asignaciones/{self.primera.pk}/"
        for usuario in (self.admin, self.tecnico, self.solicitante):
            with self.subTest(usuario=usuario.pk):
                response = self.cliente(usuario).get(url)
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual(response.data["id_asignacion"], self.primera.pk)
        self.assertEqual(self.cliente(self.otro).get(url).status_code, 403)
        self.assertEqual(self.cliente(self.admin).get("/api/asignaciones/999999/").status_code, 404)

    def test_anonimo_inactivo_y_sin_privilegios_rechazados_en_los_tres_get(self):
        urls = ("/api/asignaciones/", f"/api/asignaciones/{self.primera.pk}/", "/api/asignaciones/estados/")
        self.admin.activo = False
        self.admin.save(update_fields=["activo"])
        # Cuenta sin roles ni permisos; la sesión del helper finge rol admin.
        UsuarioRol.objects.filter(usuario=self.otro).delete()
        for usuario in (None, self.admin, self.otro):
            cliente = self.cliente(usuario)
            for url in urls:
                with self.subTest(usuario=getattr(usuario, "pk", None), url=url):
                    self.assertEqual(cliente.get(url).status_code, 403)

    def test_permiso_catalogo_no_otorga_consulta_administrativa_global(self):
        rol = Rol.objects.create(nombre="Consulta de catálogo de prueba")
        permiso = Permiso.objects.get(codigo="CATALOGO_CONSULTAR")
        RolPermiso.objects.get_or_create(rol=rol, permiso=permiso)
        UsuarioRol.objects.filter(usuario=self.solicitante).delete()
        UsuarioRol.objects.create(usuario=self.solicitante, rol=rol)
        # Sin ninguno de los tres roles oficiales, el permiso habilita solo
        # la consulta propia, no el alcance administrativo.
        self.assertEqual(self.ids(usuario=self.solicitante), [self.finalizada.pk, self.primera.pk])
        self.assertEqual(self.cliente(self.solicitante).get(f"/api/asignaciones/{self.ajena.pk}/").status_code, 403)

    def test_catalogo_de_estados_y_contrato_json(self):
        response = self.cliente(self.admin).get("/api/asignaciones/estados/")
        self.assertEqual(response.status_code, 200)
        estados = json.loads(response.content)
        self.assertIsInstance(estados, list)
        self.assertTrue({"Activa", "Finalizada"}.issubset({item["nombre"] for item in estados}))
        self.assertEqual([item["id_estado_asignacion"] for item in estados], sorted(item["id_estado_asignacion"] for item in estados))
        for estado in estados:
            self.assertEqual(set(estado), {"id_estado_asignacion", "nombre", "descripcion"})

    def test_contrato_rest_listado_detalle_fechas_y_estados_independientes(self):
        listado = self.listado()
        self.assertTrue(listado["Content-Type"].startswith("application/json"))
        filas = json.loads(listado.content)
        esperados = {
            "id_asignacion", "id_solicitud", "solicitud", "id_activo", "activo",
            "id_tecnico_entrega", "tecnico_entrega", "id_estado_asignacion", "estado",
            "fecha_entrega", "fecha_devolucion_prevista", "fecha_finalizacion",
        }
        for asignacion in (self.primera, self.finalizada):
            detalle = self.cliente(self.admin).get(f"/api/asignaciones/{asignacion.pk}/")
            self.assertEqual(detalle.status_code, 200)
            dato = json.loads(detalle.content)
            self.assertEqual(set(dato), esperados)
            self.assertEqual(dato, next(fila for fila in filas if fila["id_asignacion"] == asignacion.pk))
            self.assertIsInstance(dato["id_asignacion"], int)
            self.assertEqual(dato["solicitud"]["solicitante"]["id_usuario"], self.solicitante.pk)
            self.assertEqual(dato["tecnico_entrega"]["id_usuario"], self.tecnico.pk)
            self.assertEqual(dato["activo"]["codigo_inventario"], asignacion.id_activo.codigo_inventario)
            self.assertEqual(dato["activo"]["modelo"], asignacion.id_activo.id_modelo.nombre)
            self.assertIsNotNone(datetime.fromisoformat(dato["fecha_entrega"].replace("Z", "+00:00")).tzinfo)
            self.assertIsNone(dato["fecha_devolucion_prevista"])
            if asignacion == self.primera:
                self.assertEqual(dato["estado"]["nombre"], "Activa")
                self.assertIsNone(dato["fecha_finalizacion"])
            else:
                self.assertEqual(dato["estado"]["nombre"], "Finalizada")
                self.assertEqual(dato["activo"]["estado"], "Disponible")
                self.assertIsNotNone(datetime.fromisoformat(dato["fecha_finalizacion"].replace("Z", "+00:00")).tzinfo)

    def test_get_no_modifica_datos_de_negocio_ni_crea_auditoria(self):
        modelos = (Asignacion, SolicitudAsignacion, Activo, DevolucionActivo, HistorialEstadoActivo, BitacoraAuditoria)
        def instantanea():
            return {modelo._meta.label: list(modelo.objects.order_by("pk").values()) for modelo in modelos}

        antes = instantanea()
        self.listado()
        self.listado({"usuario": self.solicitante.pk, "estado": "Activa"})
        self.cliente(self.admin).get(f"/api/asignaciones/{self.primera.pk}/")
        self.cliente(self.admin).get("/api/asignaciones/estados/")
        self.assertEqual(instantanea(), antes)
