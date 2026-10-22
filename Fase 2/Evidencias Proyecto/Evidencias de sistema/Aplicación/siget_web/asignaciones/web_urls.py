"""Rutas de registro y consulta de solicitudes en el portal."""

from django.urls import path

from asignaciones import web_views

app_name = "asignaciones_web"

urlpatterns = [
    path("<int:pk>/", web_views.detalle_solicitud, name="detalle"),
    path("nueva/", web_views.solicitar_equipo, name="solicitar"),
    path("<int:pk>/confirmacion/", web_views.confirmacion_solicitud, name="confirmacion"),
]
