from django.urls import path
from .views import IngresoRepuestoView, ListadoRepuestosView

urlpatterns = [
    path("", ListadoRepuestosView.as_view(), name="listado-repuestos"),
    path("ingresos/", IngresoRepuestoView.as_view(), name="ingreso-repuesto"),
]