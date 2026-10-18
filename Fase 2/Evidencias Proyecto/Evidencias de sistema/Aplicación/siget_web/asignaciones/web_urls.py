"""Rutas locales del portal; pendientes de incluir en el enrutamiento principal."""

from django.urls import path

from asignaciones import web_views

app_name = "asignaciones_web"

urlpatterns = [
    path("nueva/", web_views.solicitar_equipo, name="solicitar"),
    path("<int:pk>/confirmacion/", web_views.confirmacion_solicitud, name="confirmacion"),
]
