from django.urls import path

from .views import DashboardReportesView, ReporteParqueTIView

urlpatterns = [
    path(
        "dashboard/",
        DashboardReportesView.as_view(),
        name="dashboard-reportes",
    ),
    path(
        "parque-ti/",
        ReporteParqueTIView.as_view(),
        name="reporte-parque-ti",
    ),
]
