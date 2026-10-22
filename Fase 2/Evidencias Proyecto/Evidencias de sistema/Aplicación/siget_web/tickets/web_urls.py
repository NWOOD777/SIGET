"""Rutas web de E5-H13 incluidas bajo /tickets/ en el portal."""

from django.urls import path

from tickets import web_views

app_name = "tickets_web"

urlpatterns = [
    path("<int:pk>/", web_views.detalle_ticket, name="detalle"),
    path("nuevo/", web_views.crear_ticket_web, name="nuevo"),
    # Alias conservado para las referencias de la Etapa 2.
    path("nuevo/", web_views.crear_ticket_web, name="crear"),
    path("<int:pk>/confirmacion/", web_views.confirmacion_ticket, name="confirmacion"),
]
