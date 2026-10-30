from django.urls import path

from .views import DashboardReportesView

urlpatterns = [
    path(
        "dashboard/",
        DashboardReportesView.as_view(),
        name="dashboard-reportes",
    ),
]