from django.urls import path

from .views import (
    AjusteStockRepuestoView,
    AlertasRepuestosView,
    EstadoRepuestoView,
    IngresoRepuestoView,
    ListadoRepuestosView,
    StockMinimoRepuestoView,
)

urlpatterns = [
    path(
        "",
        ListadoRepuestosView.as_view(),
        name="listado-repuestos",
    ),
    path(
        "ingresos/",
        IngresoRepuestoView.as_view(),
        name="ingreso-repuesto",
    ),
    path(
        "alertas/",
        AlertasRepuestosView.as_view(),
        name="alertas-repuestos",
    ),
    path(
        "<int:id_repuesto>/stock-minimo/",
        StockMinimoRepuestoView.as_view(),
        name="stock-minimo-repuesto",
    ),
    path(
        "<int:id_repuesto>/ajustar-stock/",
        AjusteStockRepuestoView.as_view(),
        name="ajustar-stock-repuesto",
    ),
    path(
        "<int:id_repuesto>/estado/",
        EstadoRepuestoView.as_view(),
        name="estado-repuesto",
    ),
]