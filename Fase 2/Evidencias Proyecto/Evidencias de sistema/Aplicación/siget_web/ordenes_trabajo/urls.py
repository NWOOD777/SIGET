
from django.urls import path

from .views import (
    HistorialOrdenTrabajoView,
    IniciarReparacionView,
    ListarTecnicosOTView,
    OrdenTrabajoListCreateView,
    PausarOrdenTrabajoView,
    ReasignarOrdenTrabajoView,
    ReanudarOrdenTrabajoView,
)

urlpatterns = [
    
    path(
        "tecnicos-disponibles/",
        ListarTecnicosOTView.as_view(),
        name="listar-tecnicos-ot",
    ),

    path(
        "<int:pk>/historial/",
        HistorialOrdenTrabajoView.as_view(),
        name="historial-orden-trabajo",
    ),



    path("", OrdenTrabajoListCreateView.as_view(), name="ordenes-trabajo"),
    path(
        "<int:pk>/iniciar-reparacion/",
        IniciarReparacionView.as_view(),
        name="iniciar-reparacion",
    ),
    path(
        "<int:pk>/pausar/",
        PausarOrdenTrabajoView.as_view(),
        name="pausar-orden-trabajo",
    ),
    path(
        "<int:pk>/reasignar/",
        ReasignarOrdenTrabajoView.as_view(),
        name="reasignar-orden-trabajo",
    ),
    path(
        "<int:pk>/reanudar/",
        ReanudarOrdenTrabajoView.as_view(),
        name="reanudar-orden-trabajo",
    ),
]
