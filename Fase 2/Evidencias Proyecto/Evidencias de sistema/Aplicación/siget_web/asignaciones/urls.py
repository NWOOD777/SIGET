
from django.urls import path

from .views import RegistrarDevolucionView

app_name = "asignaciones"

urlpatterns = [
    path(
        "<int:pk>/devolucion/",
        RegistrarDevolucionView.as_view(),
        name="registrar_devolucion",
    ),
]
