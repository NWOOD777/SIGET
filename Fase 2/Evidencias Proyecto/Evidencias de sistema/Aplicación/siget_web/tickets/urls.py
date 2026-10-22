"""
Rutas URL para la API REST de tickets y Service Desk.
"""
from django.urls import path

from tickets.views import (
    TicketAsignarView,
    TicketAtencionCreateView,
    TicketEstadoView,
    TicketTomarView,
    EstadoTicketListView,
    PrioridadListView,
    SLAListView,
    TicketDetailView,
    TicketListCreateView,
)

urlpatterns = [
    path("sla/", SLAListView.as_view(), name="ticket-sla"),
    path("", TicketListCreateView.as_view(), name="ticket-list-create"),
    path("<int:pk>/", TicketDetailView.as_view(), name="ticket-detail"),
    path("<int:pk>/asignar/", TicketAsignarView.as_view(), name="ticket-asignar"),
    path("<int:pk>/atenciones/", TicketAtencionCreateView.as_view(), name="ticket-atenciones"),
    path("<int:pk>/estado/", TicketEstadoView.as_view(), name="ticket-estado"),
    path("<int:pk>/tomar/", TicketTomarView.as_view(), name="ticket-tomar"),
    path("prioridades/", PrioridadListView.as_view(), name="ticket-prioridades"),
    path("estados/", EstadoTicketListView.as_view(), name="ticket-estados"),
]
