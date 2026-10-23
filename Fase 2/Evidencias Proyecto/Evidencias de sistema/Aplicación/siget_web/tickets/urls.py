"""
Rutas URL para la API REST de tickets y Service Desk.
"""
from django.urls import path

from tickets.views import (
    EstadoTicketListView,
    IndicadoresCSATDetailView,
    IndicadoresCSATListView,
    PrioridadListView,
    SLAListView,
    TicketAsignarView,
    TicketAtencionCreateView,
    TicketCSATView,
    TicketDetailView,
    TicketEstadoView,
    TicketListCreateView,
    TicketTomarView,
)

urlpatterns = [
    path("sla/", SLAListView.as_view(), name="ticket-sla"),
    path("indicadores-csat/", IndicadoresCSATListView.as_view(), name="ticket-indicadores-csat"),
    path(
        "indicadores-csat/<int:id_tecnico>/",
        IndicadoresCSATDetailView.as_view(),
        name="ticket-indicadores-csat-detalle",
    ),
    path("", TicketListCreateView.as_view(), name="ticket-list-create"),
    path("<int:pk>/", TicketDetailView.as_view(), name="ticket-detail"),
    path("<int:pk>/asignar/", TicketAsignarView.as_view(), name="ticket-asignar"),
    path("<int:pk>/atenciones/", TicketAtencionCreateView.as_view(), name="ticket-atenciones"),
    path("<int:pk>/csat/", TicketCSATView.as_view(), name="ticket-csat"),
    path("<int:pk>/estado/", TicketEstadoView.as_view(), name="ticket-estado"),
    path("<int:pk>/tomar/", TicketTomarView.as_view(), name="ticket-tomar"),
    path("prioridades/", PrioridadListView.as_view(), name="ticket-prioridades"),
    path("estados/", EstadoTicketListView.as_view(), name="ticket-estados"),
]
