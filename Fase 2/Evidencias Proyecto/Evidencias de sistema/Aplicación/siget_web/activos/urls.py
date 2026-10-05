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
        "marcas/",
        views.MarcaListView.as_view(),
        name="marcas",
    ),
    path(
        "modelos/",
        views.ModeloActivoListView.as_view(),
        name="modelos",
    ),
    path(
        "ubicaciones/",
        views.UbicacionListView.as_view(),
        name="ubicaciones",
    ),
    path(
        "estados/",
        views.EstadoActivoListView.as_view(),
        name="estados",
    ),
]