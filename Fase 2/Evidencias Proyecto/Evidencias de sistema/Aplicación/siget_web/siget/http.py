"""Metadatos de cliente validados para el despliegue local sin proxy confiable."""
from ipaddress import ip_address


def direccion_ip_cliente(request):
    try:
        return str(ip_address(request.META.get("REMOTE_ADDR", "")))
    except ValueError:
        return None
