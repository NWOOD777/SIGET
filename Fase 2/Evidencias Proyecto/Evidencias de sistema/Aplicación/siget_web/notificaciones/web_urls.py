from django.urls import path

from notificaciones import web_views

app_name = "notificaciones_web"

urlpatterns = [
    path("", web_views.bandeja_notificaciones, name="bandeja"),
    path("<int:pk>/", web_views.detalle_notificacion, name="detalle"),
    path("<int:pk>/leer/", web_views.marcar_notificacion_leida, name="marcar_leida"),
    path("<int:pk>/abrir/", web_views.abrir_notificacion, name="abrir"),
]

