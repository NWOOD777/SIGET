"""
Pruebas unitarias para los mantenedores administrativos de categorías, marcas,
modelos y ubicaciones.
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock, patch

from django.db import DatabaseError
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import ValidationError

from activos.models import Activo, CategoriaActivo, Marca, ModeloActivo, Ubicacion
from activos.serializers import (
    CategoriaActivoSerializer,
    MarcaSerializer,
    ModeloActivoSerializer,
    UbicacionSerializer,
)
from activos.views import (
    CategoriaActivoListView,
    MarcaListView,
    ModeloActivoDetailView,
    ModeloActivoListView,
    UbicacionListView,
)

from .helpers import (
    ActivosTestBase,
    crear_request_con_sesion,
    obtener_data_dict,
    obtener_data_list,
)


class CatalogosMantenedoresUnitTests(ActivosTestBase):
    """Pruebas unitarias de vistas y serializadores para los 4 catálogos maestros."""

    def test_rutas_registradas_para_listado_y_detalle(self):
        self.assertEqual(reverse("activos:categorias"), "/api/activos/categorias/")
        self.assertEqual(
            reverse("activos:categoria_detail", args=[1]),
            "/api/activos/categorias/1/",
        )
        self.assertEqual(reverse("activos:marcas"), "/api/activos/marcas/")
        self.assertEqual(
            reverse("activos:marca_detail", args=[1]),
            "/api/activos/marcas/1/",
        )
        self.assertEqual(reverse("activos:modelos"), "/api/activos/modelos/")
        self.assertEqual(
            reverse("activos:modelo_detail", args=[1]),
            "/api/activos/modelos/1/",
        )
        self.assertEqual(reverse("activos:ubicaciones"), "/api/activos/ubicaciones/")
        self.assertEqual(
            reverse("activos:ubicacion_detail", args=[1]),
            "/api/activos/ubicaciones/1/",
        )

    def test_rbac_rechaza_escritura_a_tecnico_solicitante_y_anonimo(self):
        vistas = [
            (CategoriaActivoListView.as_view(), "/api/activos/categorias/"),
            (MarcaListView.as_view(), "/api/activos/marcas/"),
            (ModeloActivoListView.as_view(), "/api/activos/modelos/"),
            (UbicacionListView.as_view(), "/api/activos/ubicaciones/"),
        ]
        for vista, ruta in vistas:
            req_anon = crear_request_con_sesion(self.factory, "POST", ruta, usuario_id=None, data={"nombre": "X"})
            with patch("activos.permissions.obtener_usuario_actual", return_value=None):
                self.assertEqual(vista(req_anon).status_code, status.HTTP_403_FORBIDDEN)

            req_tec = crear_request_con_sesion(self.factory, "POST", ruta, usuario_id=2, data={"nombre": "X"})
            with (
                patch(
                    "activos.permissions.obtener_usuario_actual",
                    return_value=self.tecnico_user,
                ),
                patch("activos.permissions.es_administrador", return_value=False),
            ):
                self.assertEqual(vista(req_tec).status_code, status.HTTP_403_FORBIDDEN)

            req_sol = crear_request_con_sesion(self.factory, "POST", ruta, usuario_id=3, data={"nombre": "X"})
            with (
                patch(
                    "activos.permissions.obtener_usuario_actual",
                    return_value=self.solicitante_user,
                ),
                patch("activos.permissions.es_administrador", return_value=False),
            ):
                self.assertEqual(vista(req_sol).status_code, status.HTTP_403_FORBIDDEN)

    @patch.object(CategoriaActivo.objects, "all")
    @patch.object(Marca.objects, "all")
    @patch.object(Ubicacion.objects, "all")
    @patch.object(ModeloActivo.objects, "select_related")
    def test_get_permitido_para_tecnico_y_solicitante(
        self,
        mock_mod_sr,
        mock_ubic_all,
        mock_marca_all,
        mock_cat_all,
    ):
        mock_cat_all.return_value = []
        mock_marca_all.return_value = []
        mock_ubic_all.return_value = []
        mock_mod_sr.return_value.all.return_value = []

        for usuario in (self.tecnico_user, self.solicitante_user):
            with (
                patch(
                    "activos.permissions.obtener_usuario_actual",
                    return_value=usuario,
                ),
                patch("activos.permissions.es_administrador", return_value=False),
                patch("activos.permissions.usuario_tiene_rol", return_value=False),
                patch("activos.permissions.usuario_tiene_permiso", return_value=True),
            ):
                for vista, ruta in (
                    (CategoriaActivoListView.as_view(), "/api/activos/categorias/"),
                    (MarcaListView.as_view(), "/api/activos/marcas/"),
                    (ModeloActivoListView.as_view(), "/api/activos/modelos/"),
                    (UbicacionListView.as_view(), "/api/activos/ubicaciones/"),
                ):
                    req = crear_request_con_sesion(self.factory, "GET", ruta, usuario_id=usuario.id_usuario)
                    resp = vista(req)
                    self.assertEqual(resp.status_code, status.HTTP_200_OK)
                    self.assertEqual(obtener_data_list(resp), [])

    @patch.object(CategoriaActivo.objects, "all")
    def test_normalizacion_y_duplicados_en_categoria_serializer(self, mock_all):
        existente = CategoriaActivo(id_categoria=1, nombre="Notebook", descripcion="Portátil")
        mock_all.return_value = [existente]

        # Duplicado por mayúsculas y espacios exteriores/interiores
        s_dup = CategoriaActivoSerializer(data={"nombre": "  notebook  "})
        self.assertFalse(s_dup.is_valid())
        self.assertIn("nombre", s_dup.errors)

        # Solo espacios rechazado
        s_vacio = CategoriaActivoSerializer(data={"nombre": "    "})
        self.assertFalse(s_vacio.is_valid())
        self.assertIn("nombre", s_vacio.errors)

        # Edición del propio registro excluye su propio PK
        mock_qs = MagicMock()
        mock_qs.exclude.return_value = []
        mock_all.return_value = mock_qs
        s_edit = CategoriaActivoSerializer(
            existente,
            data={"nombre": "  Notebook  ", "descripcion": "  Actualizada  "},
            partial=True,
        )
        self.assertTrue(s_edit.is_valid(), s_edit.errors)
        datos_validados = cast(dict[str, Any], s_edit.validated_data)
        self.assertEqual(datos_validados["nombre"], "Notebook")
        self.assertEqual(datos_validados["descripcion"], "Actualizada")

    @patch.object(Ubicacion.objects, "all")
    def test_ubicacion_identidad_funcional_area_edificio_piso(self, mock_all):
        existente = Ubicacion(
            id_ubicacion=1,
            nombre_area="Departamento TI",
            edificio="Edificio Central",
            piso="Piso 2",
        )
        mock_all.return_value = [existente]

        # Misma área en distinto edificio es válida
        s_otro_edificio = UbicacionSerializer(
            data={
                "nombre_area": "Departamento TI",
                "edificio": "Edificio Norte",
                "piso": "Piso 2",
            }
        )
        self.assertTrue(s_otro_edificio.is_valid(), s_otro_edificio.errors)

        # Misma combinación (área, edificio, piso) con distinta capitalización es rechazada
        s_dup = UbicacionSerializer(
            data={
                "nombre_area": "  departamento ti ",
                "edificio": " EDIFICIO CENTRAL ",
                "piso": " piso 2 ",
            }
        )
        self.assertFalse(s_dup.is_valid())
        self.assertIn("nombre_area", s_dup.errors)

    @patch.object(CategoriaActivo.objects, "filter")
    @patch.object(Marca.objects, "filter")
    @patch.object(Activo.objects, "filter")
    @patch.object(ModeloActivo.objects, "filter")
    def test_modelo_usado_bloquea_cambio_de_marca_o_categoria(
        self,
        mock_mod_filter,
        mock_act_filter,
        mock_marca_filter,
        mock_cat_filter,
    ):
        self.modelo.id_marca_id = 1
        self.modelo.id_categoria_id = 1
        marca2 = MagicMock(id_marca=2, pk=2, nombre="HP")
        cat2 = MagicMock(id_categoria=2, pk=2, nombre="Monitor")
        mock_marca_filter.return_value.exists.return_value = True
        mock_cat_filter.return_value.exists.return_value = True
        mock_mod_filter.return_value.exclude.return_value = []
        mock_act_filter.return_value.count.return_value = 3

        s_cambio = ModeloActivoSerializer(
            self.modelo,
            data={"nombre": "Latitude 5520"},
            partial=True,
        )
        setattr(s_cambio, "initial_data", {"id_marca": 2, "id_categoria": 2})
        with self.assertRaises(ValidationError) as ctx:
            s_cambio.validate(
                {
                    "id_marca": marca2,
                    "id_categoria": cat2,
                    "nombre": "Latitude 5520",
                }
            )
        self.assertIn("id_marca", ctx.exception.detail)
        self.assertIn("id_categoria", ctx.exception.detail)

    @patch("activos.views.bloquear_operacion")
    @patch.object(ModeloActivo.objects, "select_related")
    @patch.object(Activo.objects, "filter")
    def test_eliminacion_modelo_bloqueada_cuando_tiene_activos(
        self,
        mock_act_filter,
        mock_sr,
        _mock_lock,
    ):
        mock_sr.return_value.get.return_value = self.modelo
        mock_act_filter.return_value.count.return_value = 2

        with (
            patch(
                "activos.permissions.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch("activos.permissions.es_administrador", return_value=True),
        ):
            req = crear_request_con_sesion(self.factory, "DELETE", "/api/activos/modelos/1/", usuario_id=1)
            resp = ModeloActivoDetailView.as_view()(req, pk=1)
            self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
            self.assertIn("asociado a 2 activo(s)", obtener_data_dict(resp)["detail"])

    @patch("activos.serializers.bloquear_operacion")
    @patch.object(Marca.objects, "all")
    @patch.object(Marca.objects, "create")
    @patch("activos.serializers.registrar_auditoria", side_effect=DatabaseError("Error audit"))
    def test_fallo_auditoria_propaga_excepcion_en_creacion(
        self,
        _mock_aud,
        mock_create,
        mock_all,
        _mock_lock,
    ):
        mock_all.return_value = []
        mock_create.return_value = Marca(id_marca=9, nombre="Lenovo")
        s = MarcaSerializer(data={"nombre": "Lenovo"})
        self.assertTrue(s.is_valid())
        with self.assertRaises(DatabaseError):
            s.save()
