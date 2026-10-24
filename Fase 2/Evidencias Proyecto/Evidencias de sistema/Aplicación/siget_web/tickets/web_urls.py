"""Rutas del portal para creación, consulta, seguimiento y evaluación de tickets."""

from django.urls import path

from tickets import web_views

app_name = "tickets_web"

urlpatterns = [
    path("seguimiento/", web_views.seguimiento_tickets, name="seguimiento"),
    path("<int:pk>/", web_views.detalle_ticket, name="detalle"),
    path("<int:pk>/csat/", web_views.evaluar_ticket_web, name="evaluar_csat"),
    path("nuevo/", web_views.crear_ticket_web, name="nuevo"),
    path("<int:pk>/confirmacion/", web_views.confirmacion_ticket, name="confirmacion"),
]
