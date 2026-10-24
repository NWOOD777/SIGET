"""
Servicios de alto nivel que consumen las APIs REST existentes de SIGET.
No contienen lógica de persistencia ni acceden directamente a la base de datos.
"""

from __future__ import annotations

from typing import Any

from siget_desktop.api.client import ServerApiError, api_client


def _objeto(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not value:
        raise ServerApiError("El servidor devolvió una respuesta incompleta o con un formato inesperado.")
    return value


def _vacio_o_objeto(value: Any) -> dict[str, Any]:
    if value is None or value == "" or value == {}:
        return {}
    return _objeto(value)


def _lista(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ServerApiError("El servidor devolvió un listado con un formato inesperado.")
    return value


# ============================================================================
# USUARIOS, IDENTIDAD Y RBAC
# ============================================================================

def obtener_perfil_actual() -> dict[str, Any]:
    """Consulta la identidad, roles y permisos efectivos del usuario actual."""
    resultado = api_client.get("/api/usuarios/me/")
    return _objeto(resultado)


def listar_usuarios_rbac() -> list[dict[str, Any]]:
    """Consulta administrativa de usuarios y roles RBAC (exclusivo Administrador)."""
    resultado = api_client.get("/api/usuarios/")
    return _lista(resultado)


def eliminar_usuario(id_usuario: int) -> dict[str, Any]:
    """Elimina una cuenta sin actividad de SIGET y de su proveedor de identidad."""
    return _vacio_o_objeto(api_client.delete(f"/api/usuarios/{id_usuario}/"))


def cambiar_estado_usuario(id_usuario: int, activo: bool) -> dict[str, Any]:
    """Habilita o deshabilita el acceso local sin eliminar su historial."""
    return _objeto(api_client.patch(f"/api/usuarios/{id_usuario}/", json={"activo": activo}))


def aprovisionar_usuario(
    nombres: str,
    apellidos: str,
    correo: str,
    rut: str,
    rol: str,
) -> dict[str, Any]:
    """
    Aprovisiona un nuevo usuario mediante Auth0 y lo vincula en PostgreSQL (exclusivo Administrador).
    """
    payload = {
        "nombres": nombres,
        "apellidos": apellidos,
        "correo": correo,
        "rut": rut,
        "rol": rol,
    }
    resultado = api_client.post("/api/usuarios/aprovisionar/", json=payload)
    return _objeto(resultado)


def obtener_acceso_usuario(id_usuario: int) -> dict[str, Any]:
    """Consulta los roles y permisos efectivos consolidados de un usuario (exclusivo Administrador)."""
    resultado = api_client.get(f"/api/usuarios/{id_usuario}/acceso/")
    return _objeto(resultado)


def listar_roles_rbac() -> list[dict[str, Any]]:
    """Consulta el catálogo de roles oficiales y sus permisos asociados (exclusivo Administrador)."""
    resultado = api_client.get("/api/usuarios/roles/")
    return _lista(resultado)


def actualizar_roles_usuario(id_usuario: int, roles: list[str | int]) -> dict[str, Any]:
    """
    Actualiza la colección completa de roles que conserva el usuario (exclusivo Administrador).
    No permite dejar a una cuenta sin roles.
    """
    payload = {"roles": roles}
    resultado = api_client.post(f"/api/usuarios/{id_usuario}/roles/", json=payload)
    return _objeto(resultado)


def retirar_rol_usuario(id_usuario: int, id_rol: int) -> dict[str, Any]:
    """Retira un rol específico asignado a un usuario (exclusivo Administrador)."""
    resultado = api_client.delete(f"/api/usuarios/{id_usuario}/roles/{id_rol}/")
    return _objeto(resultado)


def asignar_permiso_rol(id_rol: int, id_permiso: int | None = None, codigo: str | None = None) -> dict[str, Any]:
    """Asocia un permiso existente a un rol (exclusivo Administrador)."""
    payload: dict[str, Any] = {}
    if id_permiso is not None:
        payload["id_permiso"] = id_permiso
    if codigo:
        payload["codigo"] = codigo
    resultado = api_client.post(f"/api/usuarios/roles/{id_rol}/permisos/", json=payload)
    return _objeto(resultado)


def retirar_permiso_rol(id_rol: int, id_permiso: int) -> dict[str, Any]:
    """Retira un permiso de un rol oficial (exclusivo Administrador)."""
    resultado = api_client.delete(f"/api/usuarios/roles/{id_rol}/permisos/{id_permiso}/")
    return _objeto(resultado)


# ============================================================================
# ACTIVOS TI
# ============================================================================

def listar_activos(
    search: str | None = None,
    tipo: str | None = None,
    ubicacion: str | None = None,
    estado: str | None = None,
) -> list[dict[str, Any]]:
    """Consulta el inventario de activos TI aplicando filtros."""
    params: dict[str, Any] = {}
    if search:
        params["search"] = search
    if tipo:
        params["tipo"] = tipo
    if ubicacion:
        params["ubicacion"] = ubicacion
    if estado:
        params["estado"] = estado
    resultado = api_client.get("/api/activos/", params=params)
    return _lista(resultado)


def obtener_activo(id_activo: int) -> dict[str, Any]:
    """Consulta el detalle de un activo tecnológico."""
    resultado = api_client.get(f"/api/activos/{id_activo}/")
    return _objeto(resultado)


def crear_activo(datos: dict[str, Any]) -> dict[str, Any]:
    """Registra un nuevo activo tecnológico (exclusivo Administrador)."""
    resultado = api_client.post("/api/activos/", json=datos)
    return _objeto(resultado)


def actualizar_activo(id_activo: int, datos: dict[str, Any], parcial: bool = True) -> dict[str, Any]:
    """Modifica la información de un activo tecnológico (exclusivo Administrador)."""
    metodo = api_client.patch if parcial else api_client.put
    resultado = metodo(f"/api/activos/{id_activo}/", json=datos)
    return _objeto(resultado)


def eliminar_activo(id_activo: int) -> dict[str, Any]:
    """Elimina un activo sin movimientos ni registros relacionados."""
    return _vacio_o_objeto(api_client.delete(f"/api/activos/{id_activo}/"))


def listar_categorias_activos(search: str | None = None) -> list[dict[str, Any]]:
    """Consulta el catálogo de categorías de activos TI."""
    if search and search.strip():
        resultado = api_client.get(
            "/api/activos/categorias/",
            params={"search": search.strip()},
        )
    else:
        resultado = api_client.get("/api/activos/categorias/")
    return _lista(resultado)


def obtener_categoria_activo(id_categoria: int) -> dict[str, Any]:
    """Consulta el detalle de una categoría de activo TI."""
    resultado = api_client.get(f"/api/activos/categorias/{id_categoria}/")
    return _objeto(resultado)


def crear_categoria_activo(datos: dict[str, Any]) -> dict[str, Any]:
    """Registra una nueva categoría de activo TI (exclusivo Administrador)."""
    resultado = api_client.post("/api/activos/categorias/", json=datos)
    return _objeto(resultado)


def actualizar_categoria_activo(
    id_categoria: int, datos: dict[str, Any], parcial: bool = True
) -> dict[str, Any]:
    """Modifica una categoría de activo TI (exclusivo Administrador)."""
    metodo = api_client.patch if parcial else api_client.put
    resultado = metodo(f"/api/activos/categorias/{id_categoria}/", json=datos)
    return _objeto(resultado)


def eliminar_categoria_activo(id_categoria: int) -> dict[str, Any]:
    """Elimina una categoría de activo TI sin referencias (exclusivo Administrador)."""
    resultado = api_client.delete(f"/api/activos/categorias/{id_categoria}/")
    return _vacio_o_objeto(resultado)


def listar_marcas_activos(search: str | None = None) -> list[dict[str, Any]]:
    """Consulta el catálogo de marcas de activos TI."""
    if search and search.strip():
        resultado = api_client.get(
            "/api/activos/marcas/",
            params={"search": search.strip()},
        )
    else:
        resultado = api_client.get("/api/activos/marcas/")
    return _lista(resultado)


def obtener_marca_activo(id_marca: int) -> dict[str, Any]:
    """Consulta el detalle de una marca de activo TI."""
    resultado = api_client.get(f"/api/activos/marcas/{id_marca}/")
    return _objeto(resultado)


def crear_marca_activo(datos: dict[str, Any]) -> dict[str, Any]:
    """Registra una nueva marca de activo TI (exclusivo Administrador)."""
    resultado = api_client.post("/api/activos/marcas/", json=datos)
    return _objeto(resultado)


def actualizar_marca_activo(
    id_marca: int, datos: dict[str, Any], parcial: bool = True
) -> dict[str, Any]:
    """Modifica una marca de activo TI (exclusivo Administrador)."""
    metodo = api_client.patch if parcial else api_client.put
    resultado = metodo(f"/api/activos/marcas/{id_marca}/", json=datos)
    return _objeto(resultado)


def eliminar_marca_activo(id_marca: int) -> dict[str, Any]:
    """Elimina una marca de activo TI sin referencias (exclusivo Administrador)."""
    resultado = api_client.delete(f"/api/activos/marcas/{id_marca}/")
    return _vacio_o_objeto(resultado)


def listar_modelos_activos(search: str | None = None) -> list[dict[str, Any]]:
    """Consulta el catálogo de modelos de activos TI."""
    if search and search.strip():
        resultado = api_client.get(
            "/api/activos/modelos/",
            params={"search": search.strip()},
        )
    else:
        resultado = api_client.get("/api/activos/modelos/")
    return _lista(resultado)


def obtener_modelo_activo(id_modelo: int) -> dict[str, Any]:
    """Consulta el detalle de un modelo de activo TI."""
    resultado = api_client.get(f"/api/activos/modelos/{id_modelo}/")
    return _objeto(resultado)


def crear_modelo_activo(datos: dict[str, Any]) -> dict[str, Any]:
    """Registra un nuevo modelo de activo TI (exclusivo Administrador)."""
    resultado = api_client.post("/api/activos/modelos/", json=datos)
    return _objeto(resultado)


def actualizar_modelo_activo(
    id_modelo: int, datos: dict[str, Any], parcial: bool = True
) -> dict[str, Any]:
    """Modifica un modelo de activo TI (exclusivo Administrador)."""
    metodo = api_client.patch if parcial else api_client.put
    resultado = metodo(f"/api/activos/modelos/{id_modelo}/", json=datos)
    return _objeto(resultado)


def eliminar_modelo_activo(id_modelo: int) -> dict[str, Any]:
    """Elimina un modelo de activo TI sin referencias (exclusivo Administrador)."""
    resultado = api_client.delete(f"/api/activos/modelos/{id_modelo}/")
    return _vacio_o_objeto(resultado)


def listar_ubicaciones_activos(search: str | None = None) -> list[dict[str, Any]]:
    """Consulta el catálogo de ubicaciones físicas de activos TI."""
    if search and search.strip():
        resultado = api_client.get(
            "/api/activos/ubicaciones/",
            params={"search": search.strip()},
        )
    else:
        resultado = api_client.get("/api/activos/ubicaciones/")
    return _lista(resultado)


def obtener_ubicacion_activo(id_ubicacion: int) -> dict[str, Any]:
    """Consulta el detalle de una ubicación física de activo TI."""
    resultado = api_client.get(f"/api/activos/ubicaciones/{id_ubicacion}/")
    return _objeto(resultado)


def crear_ubicacion_activo(datos: dict[str, Any]) -> dict[str, Any]:
    """Registra una nueva ubicación física de activo TI (exclusivo Administrador)."""
    resultado = api_client.post("/api/activos/ubicaciones/", json=datos)
    return _objeto(resultado)


def actualizar_ubicacion_activo(
    id_ubicacion: int, datos: dict[str, Any], parcial: bool = True
) -> dict[str, Any]:
    """Modifica una ubicación física de activo TI (exclusivo Administrador)."""
    metodo = api_client.patch if parcial else api_client.put
    resultado = metodo(f"/api/activos/ubicaciones/{id_ubicacion}/", json=datos)
    return _objeto(resultado)


def eliminar_ubicacion_activo(id_ubicacion: int) -> dict[str, Any]:
    """Elimina una ubicación física de activo TI sin referencias (exclusivo Administrador)."""
    resultado = api_client.delete(f"/api/activos/ubicaciones/{id_ubicacion}/")
    return _vacio_o_objeto(resultado)


def listar_estados_activos() -> list[dict[str, Any]]:
    """Consulta el catálogo de estados de activos TI."""
    resultado = api_client.get("/api/activos/estados/")
    return _lista(resultado)


# ============================================================================
# SOLICITUDES DE ASIGNACIÓN
# ============================================================================

def listar_solicitudes(
    estado: str | None = None,
    categoria: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    """Consulta las solicitudes de asignación en el alcance del usuario."""
    params: dict[str, Any] = {}
    if estado:
        params["estado"] = estado
    if categoria:
        params["categoria"] = categoria
    if search:
        params["search"] = search
    resultado = api_client.get("/api/solicitudes-asignacion/", params=params)
    return _lista(resultado)


def obtener_solicitud(id_solicitud: int) -> dict[str, Any]:
    """Consulta el detalle de una solicitud de asignación específica."""
    resultado = api_client.get(f"/api/solicitudes-asignacion/{id_solicitud}/")
    return _objeto(resultado)


def aprobar_solicitud(id_solicitud: int) -> dict[str, Any]:
    """Aprueba una solicitud de asignación pendiente (exclusivo Administrador)."""
    resultado = api_client.post(f"/api/solicitudes-asignacion/{id_solicitud}/aprobar/")
    return _objeto(resultado)


def rechazar_solicitud(id_solicitud: int, motivo_rechazo: str) -> dict[str, Any]:
    """Rechaza una solicitud de asignación con su motivo (exclusivo Administrador)."""
    payload = {"motivo_rechazo": motivo_rechazo}
    resultado = api_client.post(f"/api/solicitudes-asignacion/{id_solicitud}/rechazar/", json=payload)
    return _objeto(resultado)


def listar_estados_solicitudes() -> list[dict[str, Any]]:
    """Consulta el catálogo de estados de solicitudes de asignación."""
    resultado = api_client.get("/api/solicitudes-asignacion/estados/")
    return _lista(resultado)


# ============================================================================
# ASIGNACIONES, ENTREGAS Y DEVOLUCIONES
# ============================================================================

def listar_asignaciones(
    estado: str | None = None,
    equipo: str | None = None,
    usuario: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    """Consulta asignaciones de equipos aplicando filtros."""
    params: dict[str, Any] = {}
    if estado:
        params["estado"] = estado
    if equipo:
        params["equipo"] = equipo
    if usuario:
        params["usuario"] = usuario
    if search:
        params["search"] = search
    resultado = api_client.get("/api/asignaciones/", params=params)
    return _lista(resultado)


def obtener_asignacion(id_asignacion: int) -> dict[str, Any]:
    """Consulta el detalle de una asignación específica."""
    resultado = api_client.get(f"/api/asignaciones/{id_asignacion}/")
    return _objeto(resultado)


def registrar_entrega_solicitud(
    id_solicitud: int,
    id_activo: int,
    fecha_devolucion_prevista: str | None = None,
) -> dict[str, Any]:
    """
    Registra la entrega física de un activo para una solicitud aprobada (exclusivo Técnico).
    El equipo debe ser compatible y estar disponible.
    """
    payload: dict[str, Any] = {"id_activo": id_activo}
    if fecha_devolucion_prevista:
        payload["fecha_devolucion_prevista"] = fecha_devolucion_prevista
    resultado = api_client.post(f"/api/solicitudes-asignacion/{id_solicitud}/entregar/", json=payload)
    return _objeto(resultado)


def registrar_devolucion_asignacion(
    id_asignacion: int,
    condicion_fisica: str,
    motivo_devolucion: str | None = None,
    observaciones: str | None = None,
    id_ticket_asociado: int | None = None,
) -> dict[str, Any]:
    """
    Registra la devolución y evaluación física integrada de una asignación activa (exclusivo Técnico).
    Condiciones físicas válidas: 'Buen estado', 'Con falla técnica', 'Con daño físico'.
    """
    payload: dict[str, Any] = {"condicion_fisica": condicion_fisica}
    if motivo_devolucion:
        payload["motivo_devolucion"] = motivo_devolucion
    if observaciones:
        payload["observaciones"] = observaciones
    if id_ticket_asociado is not None:
        payload["id_ticket_asociado"] = id_ticket_asociado
    resultado = api_client.post(f"/api/asignaciones/{id_asignacion}/devolucion/", json=payload)
    return _objeto(resultado)


def listar_estados_asignaciones() -> list[dict[str, Any]]:
    """Consulta el catálogo de estados de asignación."""
    resultado = api_client.get("/api/asignaciones/estados/")
    return _lista(resultado)


# ============================================================================
# TICKETS Y SERVICE DESK
# ============================================================================

def listar_tickets(
    estado: str | None = None,
    prioridad: str | None = None,
    search: str | None = None,
    activo: str | None = None,
) -> list[dict[str, Any]]:
    """Consulta tickets de soporte dentro del alcance del usuario."""
    params: dict[str, Any] = {}
    if estado:
        params["estado"] = estado
    if prioridad:
        params["prioridad"] = prioridad
    if search:
        params["search"] = search
    if activo:
        params["activo"] = activo
    resultado = api_client.get("/api/tickets/", params=params)
    return _lista(resultado)


def obtener_ticket(id_ticket: int) -> dict[str, Any]:
    """Consulta el detalle de un ticket de soporte."""
    resultado = api_client.get(f"/api/tickets/{id_ticket}/")
    return _objeto(resultado)


def listar_prioridades_tickets() -> list[dict[str, Any]]:
    """Consulta el catálogo de prioridades de tickets."""
    resultado = api_client.get("/api/tickets/prioridades/")
    return _lista(resultado)


def listar_estados_tickets() -> list[dict[str, Any]]:
    """Consulta el catálogo de estados de tickets."""
    resultado = api_client.get("/api/tickets/estados/")
    return _lista(resultado)


def listar_sla_tickets() -> list[dict[str, Any]]:
    """Consulta las políticas de tiempos de respuesta y resolución (SLA)."""
    resultado = api_client.get("/api/tickets/sla/")
    return _lista(resultado)




# ORDENES DE TRABAJO Y DIAGNOSTICOS


def listar_ordenes_trabajo() -> list[dict[str, Any]]:
    """Consulta las órdenes de trabajo mediante la API REST."""
    resultado = api_client.get("/api/ordenes-trabajo/")
    return _lista(resultado)

def listar_tecnicos_ordenes_trabajo() -> list[dict[str, Any]]:
    """Lista los técnicos activos disponibles para reasignar una OT."""
    resultado = api_client.get(
        "/api/ordenes-trabajo/tecnicos-disponibles/"
    )
    return _lista(resultado)

def crear_orden_trabajo(
    id_ticket: int,
    descripcion_falla: str,
    procedimiento_inicial: str,
    es_reparable: bool = True,
) -> dict[str, Any]:
    """Registra un diagnóstico y crea una orden de trabajo."""
    payload = {
        "id_ticket": id_ticket,
        "descripcion_falla": descripcion_falla,
        "procedimiento_inicial": procedimiento_inicial,
        "es_reparable": es_reparable,
    }
    resultado = api_client.post("/api/ordenes-trabajo/", json=payload)
    return _objeto(resultado)


def iniciar_reparacion(id_orden: int) -> dict[str, Any]:
    """Solicita al backend el inicio de la reparación de una OT."""
    resultado = api_client.post(
        f"/api/ordenes-trabajo/{id_orden}/iniciar-reparacion/"
    )
    return _objeto(resultado)


def pausar_orden_trabajo(
    id_orden: int,
    justificacion: str,
) -> dict[str, Any]:
    """Pausa una OT indicando el motivo."""
    justificacion = justificacion.strip()
    if not justificacion:
        raise ValueError("La justificación de la pausa es obligatoria.")

    resultado = api_client.post(
        f"/api/ordenes-trabajo/{id_orden}/pausar/",
        json={"justificacion": justificacion},
    )
    return _objeto(resultado)


def reasignar_orden_trabajo(
    id_orden: int,
    id_tecnico_responsable: int,
    observaciones: str,
) -> dict[str, Any]:
    """Reasigna una OT a otro técnico."""
    observaciones = observaciones.strip()
    if not observaciones:
        raise ValueError("Las observaciones de la reasignación son obligatorias.")

    if id_tecnico_responsable <= 0:
        raise ValueError("Debes indicar un ID de técnico válido.")

    resultado = api_client.post(
        f"/api/ordenes-trabajo/{id_orden}/reasignar/",
        json={
            "id_tecnico_responsable": id_tecnico_responsable,
            "observaciones": observaciones,
        },
    )
    return _objeto(resultado)


def reanudar_orden_trabajo(id_orden: int) -> dict[str, Any]:
    """Reanuda una OT pausada."""
    resultado = api_client.post(
        f"/api/ordenes-trabajo/{id_orden}/reanudar/"
    )
    return _objeto(resultado)


def obtener_historial_activo(search: str) -> dict[str, Any]:
    """Consulta la trazabilidad de un activo mediante la API REST."""
    resultado = api_client.get(
        "/api/activos/historial/",
        params={"search": search},
    )
    return _objeto(resultado)

def obtener_historial_orden_trabajo(
    id_orden: int,
) -> list[dict[str, Any]]:
    resultado = api_client.get(
        f"/api/ordenes-trabajo/{id_orden}/historial/"
    )
    return _lista(resultado)


# ============================================================================
# AUDITORÍA INTERNA
# ============================================================================

def consultar_bitacora_auditoria(
    usuario: str | None = None,
    activo: str | None = None,
    page: int = 1,
    page_size: int = 25,
    id_usuario: int | None = None,
) -> dict[str, Any]:
    """
    Consulta la bitácora de auditoría interna de SIGET (exclusivo Administrador).
    Permite filtrar por actor (usuario) y activo (código de inventario).
    """
    params: dict[str, Any] = {
        "page": page,
        "page_size": page_size,
    }
    if id_usuario is not None:
        params["id_usuario"] = id_usuario
    elif usuario and usuario.strip():
        params["usuario"] = usuario.strip()
    if activo and activo.strip():
        params["activo"] = activo.strip()

    resultado = api_client.get("/api/auditoria/", params=params)
    return _objeto(resultado)


def buscar_opciones_auditoria(tipo: str, search: str = "") -> dict[str, Any]:
    """Busca etiquetas legibles de actores o equipos para los filtros de auditoría."""
    return _objeto(api_client.get("/api/auditoria/opciones/", params={"tipo": tipo, "search": search}))
