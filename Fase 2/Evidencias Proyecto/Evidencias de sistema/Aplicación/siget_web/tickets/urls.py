"""
Rutas URL para la API REST de tickets y Service Desk.
"""
from django.urls import path

from tickets.views import (
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
    path("prioridades/", PrioridadListView.as_view(), name="ticket-prioridades"),
    path("estados/", EstadoTicketListView.as_view(), name="ticket-estados"),
]
