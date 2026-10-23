
from django.urls import path

from .views import IniciarReparacionView, OrdenTrabajoListCreateView

urlpatterns = [
    path("", OrdenTrabajoListCreateView.as_view(), name="ordenes-trabajo"),
    path(
        "<int:pk>/iniciar-reparacion/",
        IniciarReparacionView.as_view(),
        name="iniciar-reparacion",
    ),
]
