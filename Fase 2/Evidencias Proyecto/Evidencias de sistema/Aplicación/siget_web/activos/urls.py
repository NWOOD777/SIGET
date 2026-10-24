from django.urls import path

from . import views

app_name = "activos"


urlpatterns = [
    path(
        "",
        views.ActivoListCreateView.as_view(),
        name="activo_list_create",
    ),
    path(
        "<int:pk>/",
        views.ActivoDetailView.as_view(),
        name="activo_detail",
    ),
    path(
        "categorias/",
        views.CategoriaActivoListView.as_view(),
        name="categorias",
    ),
    path(
        "categorias/<int:pk>/",
        views.CategoriaActivoDetailView.as_view(),
        name="categoria_detail",
    ),
    path(
        "marcas/",
        views.MarcaListView.as_view(),
        name="marcas",
    ),
    path(
        "marcas/<int:pk>/",
        views.MarcaDetailView.as_view(),
        name="marca_detail",
    ),
    path(
        "modelos/",
        views.ModeloActivoListView.as_view(),
        name="modelos",
    ),
    path(
        "modelos/<int:pk>/",
        views.ModeloActivoDetailView.as_view(),
        name="modelo_detail",
    ),
    path(
        "ubicaciones/",
        views.UbicacionListView.as_view(),
        name="ubicaciones",
    ),
    path(
        "ubicaciones/<int:pk>/",
        views.UbicacionDetailView.as_view(),
        name="ubicacion_detail",
    ),
    path(
        "estados/",
        views.EstadoActivoListView.as_view(),
        name="estados",
    ),
    path(
    "historial/",
    views.ActivoHistorialView.as_view(),
    name="activo_historial",
    ),



]