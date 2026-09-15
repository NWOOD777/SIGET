BEGIN;

-- ============================================================================
-- 0. LIMPIEZA TOTAL EN CASCADA
-- Incluye nombres antiguos para permitir reconstruir una BD creada con el DDL
-- previo de Fase 1.
-- ============================================================================

DROP TABLE IF EXISTS bitacora_auditoria CASCADE;
DROP TABLE IF EXISTS notificacion CASCADE;
DROP TABLE IF EXISTS codigo_qr CASCADE;

DROP TABLE IF EXISTS movimiento_repuesto CASCADE;
DROP TABLE IF EXISTS orden_repuesto CASCADE;
DROP TABLE IF EXISTS repuesto CASCADE;

DROP TABLE IF EXISTS intervencion CASCADE;
DROP TABLE IF EXISTS diagnostico CASCADE;
DROP TABLE IF EXISTS orden_trabajo CASCADE;
DROP TABLE IF EXISTS estado_orden_trabajo CASCADE;

DROP TABLE IF EXISTS evaluacion_csat CASCADE;
DROP TABLE IF EXISTS adjunto_ticket CASCADE;
DROP TABLE IF EXISTS comentario_ticket CASCADE;
DROP TABLE IF EXISTS ticket CASCADE;
DROP TABLE IF EXISTS estado_ticket CASCADE;
DROP TABLE IF EXISTS sla CASCADE;
DROP TABLE IF EXISTS prioridad_ticket CASCADE;

DROP TABLE IF EXISTS devolucion_activo CASCADE;
DROP TABLE IF EXISTS asignacion CASCADE;
DROP TABLE IF EXISTS estado_asignacion CASCADE;
DROP TABLE IF EXISTS solicitud_asignacion CASCADE;
DROP TABLE IF EXISTS estado_solicitud_asignacion CASCADE;

DROP TABLE IF EXISTS historial_estado_activo CASCADE;
DROP TABLE IF EXISTS activo CASCADE;
DROP TABLE IF EXISTS estado_activo CASCADE;
DROP TABLE IF EXISTS ubicacion CASCADE;
DROP TABLE IF EXISTS modelo_activo CASCADE;
DROP TABLE IF EXISTS marca CASCADE;
DROP TABLE IF EXISTS categoria_activo CASCADE;

DROP TABLE IF EXISTS rol_permiso CASCADE;
DROP TABLE IF EXISTS usuario_rol CASCADE;
DROP TABLE IF EXISTS permiso CASCADE;
DROP TABLE IF EXISTS rol CASCADE;
DROP TABLE IF EXISTS usuario CASCADE;

-- ============================================================================
-- 1. MÓDULO CONTROL DE ACCESO (RBAC) Y USUARIOS (5 TABLAS)
-- ============================================================================

-- Tabla 1
CREATE TABLE rol (
    id_rol SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    descripcion VARCHAR(255)
);

COMMENT ON TABLE rol IS 'Catálogo de roles oficiales para control de acceso RBAC.';
COMMENT ON COLUMN rol.nombre IS 'Roles canónicos: Usuario solicitante, Técnico de soporte, Administrador del sistema.';

-- Tabla 2
CREATE TABLE permiso (
    id_permiso SERIAL PRIMARY KEY,
    codigo VARCHAR(50) NOT NULL UNIQUE,
    descripcion VARCHAR(255) NOT NULL
);

COMMENT ON TABLE permiso IS 'Catálogo de permisos granulares sobre módulos, operaciones y endpoints de SIGET.';

-- Tabla 3
CREATE TABLE usuario (
    id_usuario SERIAL PRIMARY KEY,
    identificador_externo VARCHAR(255) NOT NULL UNIQUE,
    proveedor_identidad VARCHAR(100) NOT NULL,
    rut VARCHAR(12) NOT NULL UNIQUE,
    nombres VARCHAR(100) NOT NULL,
    apellidos VARCHAR(100) NOT NULL,
    correo VARCHAR(150) NOT NULL UNIQUE,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE usuario IS 'Directorio local de usuarios de SIGET vinculado a un proveedor externo de identidad.';
COMMENT ON COLUMN usuario.identificador_externo IS 'Identificador único entregado por el proveedor externo de identidad.';
COMMENT ON COLUMN usuario.proveedor_identidad IS 'Nombre lógico del proveedor de identidad integrado.';
COMMENT ON COLUMN usuario.rut IS 'Identificador institucional utilizado para trazabilidad y documentación.';
COMMENT ON COLUMN usuario.correo IS 'Correo del usuario; no constituye una contraseña ni una credencial almacenada por SIGET.';
COMMENT ON COLUMN usuario.activo IS 'Indica si el perfil local está habilitado para operar en SIGET.';

-- Tabla 4
CREATE TABLE usuario_rol (
    id_usuario_rol SERIAL PRIMARY KEY,
    id_usuario INT NOT NULL REFERENCES usuario(id_usuario) ON DELETE CASCADE,
    id_rol INT NOT NULL REFERENCES rol(id_rol) ON DELETE RESTRICT,
    fecha_asignacion TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_usuario_rol UNIQUE (id_usuario, id_rol)
);

COMMENT ON TABLE usuario_rol IS 'Relación N:M entre usuarios y roles RBAC.';

-- Tabla 5
CREATE TABLE rol_permiso (
    id_rol_permiso SERIAL PRIMARY KEY,
    id_rol INT NOT NULL REFERENCES rol(id_rol) ON DELETE CASCADE,
    id_permiso INT NOT NULL REFERENCES permiso(id_permiso) ON DELETE RESTRICT,
    CONSTRAINT uk_rol_permiso UNIQUE (id_rol, id_permiso)
);

COMMENT ON TABLE rol_permiso IS 'Relación N:M entre roles y permisos.';

-- ============================================================================
-- 2. MÓDULO GESTIÓN DE ACTIVOS TECNOLÓGICOS (7 TABLAS)
-- ============================================================================

-- Tabla 6
CREATE TABLE categoria_activo (
    id_categoria SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    descripcion VARCHAR(255)
);

COMMENT ON TABLE categoria_activo IS 'Catálogo de tipos o familias de activos tecnológicos.';

-- Tabla 7
CREATE TABLE marca (
    id_marca SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE
);

COMMENT ON TABLE marca IS 'Catálogo de fabricantes y marcas de activos tecnológicos.';

-- Tabla 8
CREATE TABLE modelo_activo (
    id_modelo SERIAL PRIMARY KEY,
    id_marca INT NOT NULL REFERENCES marca(id_marca) ON DELETE RESTRICT,
    id_categoria INT NOT NULL REFERENCES categoria_activo(id_categoria) ON DELETE RESTRICT,
    nombre VARCHAR(100) NOT NULL,
    CONSTRAINT uk_modelo_marca_categoria_nombre
        UNIQUE (id_marca, id_categoria, nombre)
);

COMMENT ON TABLE modelo_activo IS 'Modelos de activos vinculados a una marca y una categoría.';
COMMENT ON COLUMN modelo_activo.id_categoria IS 'La categoría se define a nivel de modelo y no se duplica en activo.';

-- Tabla 9
CREATE TABLE ubicacion (
    id_ubicacion SERIAL PRIMARY KEY,
    nombre_area VARCHAR(100) NOT NULL,
    edificio VARCHAR(50),
    piso VARCHAR(20)
);

COMMENT ON TABLE ubicacion IS 'Ubicaciones físicas, áreas, dependencias o bodegas donde se encuentran activos.';

-- Tabla 10
CREATE TABLE estado_activo (
    id_estado_activo SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    descripcion VARCHAR(255)
);

COMMENT ON TABLE estado_activo IS 'Estados canónicos del activo: Disponible, Asignado, En revisión, En reparación y Dado de baja.';

-- Tabla 11
CREATE TABLE activo (
    id_activo SERIAL PRIMARY KEY,
    codigo_inventario VARCHAR(50) NOT NULL UNIQUE,
    numero_serie VARCHAR(100) NOT NULL UNIQUE,
    id_modelo INT NOT NULL REFERENCES modelo_activo(id_modelo) ON DELETE RESTRICT,
    id_ubicacion INT NOT NULL REFERENCES ubicacion(id_ubicacion) ON DELETE RESTRICT,
    id_estado_activo INT NOT NULL REFERENCES estado_activo(id_estado_activo) ON DELETE RESTRICT,
    valor_adquisicion NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (valor_adquisicion >= 0),
    fecha_compra DATE,
    fecha_garantia DATE,
    fecha_registro TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_activo_garantia
        CHECK (fecha_garantia IS NULL OR fecha_compra IS NULL OR fecha_garantia >= fecha_compra)
);

COMMENT ON TABLE activo IS 'Inventario individual de activos tecnológicos.';
COMMENT ON COLUMN activo.id_modelo IS 'El modelo determina también la categoría del activo.';
COMMENT ON COLUMN activo.id_estado_activo IS 'Estado físico/operativo actual del activo.';

-- Tabla 12
CREATE TABLE historial_estado_activo (
    id_historial_estado SERIAL PRIMARY KEY,
    id_activo INT NOT NULL REFERENCES activo(id_activo) ON DELETE CASCADE,
    id_estado_activo INT NOT NULL REFERENCES estado_activo(id_estado_activo) ON DELETE RESTRICT,
    id_usuario INT REFERENCES usuario(id_usuario) ON DELETE SET NULL,
    fecha_cambio TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    observacion TEXT
);

COMMENT ON TABLE historial_estado_activo IS 'Historial protegido de cambios de estado de los activos.';
COMMENT ON COLUMN historial_estado_activo.id_usuario IS 'Usuario responsable del cambio; puede ser NULL si el evento fue generado automáticamente.';

-- ============================================================================
-- 3. MÓDULO SOLICITUDES, ASIGNACIONES Y DEVOLUCIONES (5 TABLAS)
-- ============================================================================

-- Tabla 13
CREATE TABLE estado_solicitud_asignacion (
    id_estado_solicitud SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    descripcion VARCHAR(255)
);

COMMENT ON TABLE estado_solicitud_asignacion IS 'Estados exclusivos del ciclo de solicitud de asignación.';

-- Tabla 14
CREATE TABLE solicitud_asignacion (
    id_solicitud SERIAL PRIMARY KEY,
    id_usuario INT NOT NULL REFERENCES usuario(id_usuario) ON DELETE RESTRICT,
    id_categoria INT NOT NULL REFERENCES categoria_activo(id_categoria) ON DELETE RESTRICT,
    id_estado_solicitud INT NOT NULL
        REFERENCES estado_solicitud_asignacion(id_estado_solicitud) ON DELETE RESTRICT,
    id_administrador_resolutor INT REFERENCES usuario(id_usuario) ON DELETE SET NULL,
    fecha_solicitud TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_resolucion TIMESTAMPTZ,
    motivo TEXT NOT NULL,
    motivo_rechazo TEXT,
    CONSTRAINT ck_solicitud_fechas
        CHECK (fecha_resolucion IS NULL OR fecha_resolucion >= fecha_solicitud)
);

COMMENT ON TABLE solicitud_asignacion IS 'Solicitud registrada por un Usuario solicitante para una categoría o tipo de equipo.';
COMMENT ON COLUMN solicitud_asignacion.id_categoria IS 'Tipo/categoría requerida; la solicitud no reserva un activo físico específico.';
COMMENT ON COLUMN solicitud_asignacion.id_administrador_resolutor IS 'Administrador del sistema que aprueba o rechaza la solicitud.';
COMMENT ON COLUMN solicitud_asignacion.motivo_rechazo IS 'Justificación de rechazo cuando corresponda.';

-- Tabla 15
CREATE TABLE estado_asignacion (
    id_estado_asignacion SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    descripcion VARCHAR(255)
);

COMMENT ON TABLE estado_asignacion IS 'Estados exclusivos de una asignación ya materializada físicamente.';

-- Tabla 16
CREATE TABLE asignacion (
    id_asignacion SERIAL PRIMARY KEY,
    id_solicitud INT NOT NULL UNIQUE
        REFERENCES solicitud_asignacion(id_solicitud) ON DELETE RESTRICT,
    id_activo INT NOT NULL REFERENCES activo(id_activo) ON DELETE RESTRICT,
    id_tecnico_entrega INT NOT NULL REFERENCES usuario(id_usuario) ON DELETE RESTRICT,
    id_estado_asignacion INT NOT NULL
        REFERENCES estado_asignacion(id_estado_asignacion) ON DELETE RESTRICT,
    fecha_entrega TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_devolucion_prevista TIMESTAMPTZ,
    fecha_finalizacion TIMESTAMPTZ,
    CONSTRAINT ck_asignacion_fechas
        CHECK (
            (fecha_devolucion_prevista IS NULL OR fecha_devolucion_prevista >= fecha_entrega)
            AND (fecha_finalizacion IS NULL OR fecha_finalizacion >= fecha_entrega)
        )
);

COMMENT ON TABLE asignacion IS 'Asignación física de un activo compatible con una solicitud previamente aprobada.';
COMMENT ON COLUMN asignacion.id_solicitud IS 'UNIQUE: una solicitud puede originar como máximo una asignación.';
COMMENT ON COLUMN asignacion.id_activo IS 'Activo físico seleccionado por el Técnico de soporte durante la entrega.';
COMMENT ON COLUMN asignacion.id_tecnico_entrega IS 'Técnico de soporte que registra la entrega física.';
COMMENT ON COLUMN asignacion.fecha_devolucion_prevista IS 'Fecha prevista opcional; no es obligatoria para materializar la entrega.';
COMMENT ON COLUMN asignacion.fecha_finalizacion IS 'Fecha en que la asignación se cierra mediante devolución.';

-- Tabla 17
CREATE TABLE devolucion_activo (
    id_devolucion SERIAL PRIMARY KEY,
    id_asignacion INT NOT NULL UNIQUE
        REFERENCES asignacion(id_asignacion) ON DELETE RESTRICT,
    id_tecnico_receptor INT NOT NULL REFERENCES usuario(id_usuario) ON DELETE RESTRICT,
    id_estado_activo_resultante INT NOT NULL
        REFERENCES estado_activo(id_estado_activo) ON DELETE RESTRICT,
    fecha_devolucion TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    condicion_fisica VARCHAR(50) NOT NULL,
    motivo_devolucion VARCHAR(100),
    observaciones TEXT,
    CONSTRAINT ck_devolucion_condicion
        CHECK (condicion_fisica IN ('Buen estado', 'Con falla técnica', 'Con daño físico'))
);

COMMENT ON TABLE devolucion_activo IS 'Registro de recepción física y evaluación inicial de un activo devuelto.';
COMMENT ON COLUMN devolucion_activo.id_asignacion IS 'La devolución obtiene el activo desde la asignación, evitando duplicar y desincronizar la referencia.';
COMMENT ON COLUMN devolucion_activo.id_estado_activo_resultante IS 'Resultado esperado de la evaluación inicial: normalmente Disponible o En revisión.';
COMMENT ON COLUMN devolucion_activo.id_tecnico_receptor IS 'Técnico de soporte que recibe y evalúa el activo.';

-- ============================================================================
-- 4. MÓDULO SERVICE DESK, TICKETS Y SLA (7 TABLAS)
-- ============================================================================

-- Tabla 18
CREATE TABLE prioridad_ticket (
    id_prioridad SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    nivel_urgencia INT NOT NULL UNIQUE CHECK (nivel_urgencia > 0),
    descripcion VARCHAR(255)
);

COMMENT ON TABLE prioridad_ticket IS 'Catálogo de prioridades de tickets y su orden de urgencia.';

-- Tabla 19
CREATE TABLE sla (
    id_sla SERIAL PRIMARY KEY,
    id_prioridad INT NOT NULL UNIQUE REFERENCES prioridad_ticket(id_prioridad) ON DELETE RESTRICT,
    tiempo_respuesta_horas INT NOT NULL CHECK (tiempo_respuesta_horas > 0),
    tiempo_resolucion_horas INT NOT NULL CHECK (tiempo_resolucion_horas > 0),
    descripcion VARCHAR(255),
    CONSTRAINT ck_sla_tiempos
        CHECK (tiempo_resolucion_horas >= tiempo_respuesta_horas)
);

COMMENT ON TABLE sla IS 'Política SLA única por prioridad.';
COMMENT ON COLUMN sla.id_prioridad IS 'UNIQUE: cada prioridad referencia una única política SLA vigente en este modelo.';

-- Tabla 20
CREATE TABLE estado_ticket (
    id_estado_ticket SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    descripcion VARCHAR(255)
);

COMMENT ON TABLE estado_ticket IS 'Estados de ciclo de vida del ticket de soporte.';

-- Tabla 21
CREATE TABLE ticket (
    id_ticket SERIAL PRIMARY KEY,
    codigo_ticket VARCHAR(50) NOT NULL UNIQUE,
    id_usuario_solicitante INT NOT NULL REFERENCES usuario(id_usuario) ON DELETE RESTRICT,
    id_tecnico_asignado INT REFERENCES usuario(id_usuario) ON DELETE SET NULL,
    id_activo INT REFERENCES activo(id_activo) ON DELETE SET NULL,
    id_estado_ticket INT NOT NULL REFERENCES estado_ticket(id_estado_ticket) ON DELETE RESTRICT,
    id_prioridad INT NOT NULL REFERENCES prioridad_ticket(id_prioridad) ON DELETE RESTRICT,
    asunto VARCHAR(200) NOT NULL,
    descripcion TEXT NOT NULL,
    fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_resolucion TIMESTAMPTZ,
    CONSTRAINT ck_ticket_fechas
        CHECK (fecha_resolucion IS NULL OR fecha_resolucion >= fecha_creacion)
);

COMMENT ON TABLE ticket IS 'Tickets de soporte gestionados bajo el modelo Service Desk.';
COMMENT ON COLUMN ticket.id_prioridad IS 'El SLA aplicable se obtiene a través de prioridad_ticket -> sla, evitando duplicidad.';
COMMENT ON COLUMN ticket.id_tecnico_asignado IS 'Técnico de soporte asignado por el Administrador del sistema.';
COMMENT ON COLUMN ticket.id_activo IS 'Activo relacionado cuando el ticket corresponde a una falla o intervención física.';

-- Tabla 22
CREATE TABLE comentario_ticket (
    id_comentario SERIAL PRIMARY KEY,
    id_ticket INT NOT NULL REFERENCES ticket(id_ticket) ON DELETE CASCADE,
    id_usuario INT NOT NULL REFERENCES usuario(id_usuario) ON DELETE RESTRICT,
    mensaje TEXT NOT NULL,
    fecha_registro TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE comentario_ticket IS 'Historial conversacional y de seguimiento de un ticket.';

-- Tabla 23
CREATE TABLE adjunto_ticket (
    id_adjunto SERIAL PRIMARY KEY,
    id_ticket INT NOT NULL REFERENCES ticket(id_ticket) ON DELETE CASCADE,
    nombre_archivo VARCHAR(255) NOT NULL,
    ruta_archivo VARCHAR(500) NOT NULL,
    tipo_mime VARCHAR(100),
    tamano_bytes BIGINT CHECK (tamano_bytes IS NULL OR tamano_bytes >= 0),
    fecha_subida TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE adjunto_ticket IS 'Archivos de evidencia asociados a tickets de soporte.';

-- Tabla 24
CREATE TABLE evaluacion_csat (
    id_evaluacion SERIAL PRIMARY KEY,
    id_ticket INT NOT NULL UNIQUE REFERENCES ticket(id_ticket) ON DELETE CASCADE,
    id_usuario INT NOT NULL REFERENCES usuario(id_usuario) ON DELETE RESTRICT,
    calificacion_estrellas INT NOT NULL CHECK (calificacion_estrellas BETWEEN 1 AND 5),
    comentario TEXT,
    fecha_evaluacion TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE evaluacion_csat IS 'Evaluación CSAT registrada por el Usuario solicitante tras el cierre del ticket.';

-- ============================================================================
-- 5. MÓDULO CONSOLA DE TALLER, DIAGNÓSTICOS Y REPARACIÓN (4 TABLAS)
-- ============================================================================

-- Tabla 25
CREATE TABLE estado_orden_trabajo (
    id_estado_ot SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    descripcion VARCHAR(255)
);

COMMENT ON TABLE estado_orden_trabajo IS 'Estados del ciclo de una orden de trabajo: En diagnóstico, En reparación, Pausada y Completada.';

-- Tabla 26
CREATE TABLE orden_trabajo (
    id_orden SERIAL PRIMARY KEY,
    codigo_ot VARCHAR(50) NOT NULL UNIQUE,
    id_ticket INT NOT NULL UNIQUE REFERENCES ticket(id_ticket) ON DELETE RESTRICT,
    id_tecnico_responsable INT NOT NULL REFERENCES usuario(id_usuario) ON DELETE RESTRICT,
    id_estado_ot INT NOT NULL REFERENCES estado_orden_trabajo(id_estado_ot) ON DELETE RESTRICT,
    falla_reportada TEXT NOT NULL,
    fecha_inicio TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_estimada_fin TIMESTAMPTZ,
    fecha_termino TIMESTAMPTZ,
    justificacion_pausa TEXT,
    CONSTRAINT ck_ot_fechas
        CHECK (
            (fecha_estimada_fin IS NULL OR fecha_estimada_fin >= fecha_inicio)
            AND (fecha_termino IS NULL OR fecha_termino >= fecha_inicio)
        )
);

COMMENT ON TABLE orden_trabajo IS 'Orden de trabajo asociada a un ticket que referencia el activo a intervenir.';
COMMENT ON COLUMN orden_trabajo.id_ticket IS 'UNIQUE: una orden de trabajo se vincula a un ticket; el activo se obtiene desde ticket.id_activo.';
COMMENT ON COLUMN orden_trabajo.id_tecnico_responsable IS 'Técnico de soporte responsable; la reasignación actualiza esta referencia y se audita.';

-- Tabla 27
CREATE TABLE diagnostico (
    id_diagnostico SERIAL PRIMARY KEY,
    id_orden INT NOT NULL REFERENCES orden_trabajo(id_orden) ON DELETE CASCADE,
    id_tecnico INT NOT NULL REFERENCES usuario(id_usuario) ON DELETE RESTRICT,
    descripcion_falla TEXT NOT NULL,
    procedimiento_inicial TEXT NOT NULL,
    es_reparable BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_diagnostico TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE diagnostico IS 'Diagnósticos técnicos registrados dentro de una orden de trabajo.';

-- Tabla 28
CREATE TABLE intervencion (
    id_intervencion SERIAL PRIMARY KEY,
    id_orden INT NOT NULL REFERENCES orden_trabajo(id_orden) ON DELETE CASCADE,
    id_tecnico INT NOT NULL REFERENCES usuario(id_usuario) ON DELETE RESTRICT,
    descripcion_accion TEXT NOT NULL,
    resultado_prueba TEXT,
    fecha_intervencion TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE intervencion IS 'Intervenciones y pruebas técnicas realizadas sobre una orden de trabajo.';

-- ============================================================================
-- 6. MÓDULO INVENTARIO DE REPUESTOS E INSUMOS TÉCNICOS (3 TABLAS)
-- ============================================================================

-- Tabla 29
CREATE TABLE repuesto (
    id_repuesto SERIAL PRIMARY KEY,
    codigo_repuesto VARCHAR(50) NOT NULL UNIQUE,
    nombre VARCHAR(150) NOT NULL,
    marca_modelo VARCHAR(150),
    unidad_medida VARCHAR(50) NOT NULL DEFAULT 'Unidad',
    stock_actual INT NOT NULL DEFAULT 0 CHECK (stock_actual >= 0),
    stock_minimo INT NOT NULL DEFAULT 1 CHECK (stock_minimo >= 0),
    precio_unitario NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (precio_unitario >= 0),
    ubicacion_bodega VARCHAR(100)
);

COMMENT ON TABLE repuesto IS 'Catálogo e inventario de repuestos, componentes e insumos técnicos.';

-- Tabla 30
CREATE TABLE orden_repuesto (
    id_orden_repuesto SERIAL PRIMARY KEY,
    id_orden INT NOT NULL REFERENCES orden_trabajo(id_orden) ON DELETE CASCADE,
    id_repuesto INT NOT NULL REFERENCES repuesto(id_repuesto) ON DELETE RESTRICT,
    cantidad INT NOT NULL CHECK (cantidad > 0),
    costo_unitario NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (costo_unitario >= 0),
    fecha_imputacion TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE orden_repuesto IS 'Consumo de repuestos imputado a una orden de trabajo.';

-- Tabla 31
CREATE TABLE movimiento_repuesto (
    id_movimiento SERIAL PRIMARY KEY,
    id_repuesto INT NOT NULL REFERENCES repuesto(id_repuesto) ON DELETE RESTRICT,
    id_usuario INT NOT NULL REFERENCES usuario(id_usuario) ON DELETE RESTRICT,
    tipo_movimiento VARCHAR(50) NOT NULL,
    cantidad INT NOT NULL CHECK (cantidad > 0),
    costo_unitario NUMERIC(12,2) DEFAULT 0 CHECK (costo_unitario >= 0),
    motivo VARCHAR(255),
    fecha_movimiento TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_movimiento_repuesto_tipo
        CHECK (tipo_movimiento IN (
            'INGRESO_COMPRA',
            'AJUSTE_INVENTARIO',
            'SALIDA_TALLER',
            'DEVOLUCION_TALLER'
        ))
);

COMMENT ON TABLE movimiento_repuesto IS 'Movimientos de inventario de repuestos.';
COMMENT ON COLUMN movimiento_repuesto.id_usuario IS 'Administrador del sistema o Técnico de soporte autorizado que registra el movimiento.';

-- ============================================================================
-- 7. MÓDULO IDENTIFICACIÓN QR, NOTIFICACIONES Y AUDITORÍA (3 TABLAS)
-- ============================================================================

-- Tabla 32
CREATE TABLE codigo_qr (
    id_qr SERIAL PRIMARY KEY,
    id_activo INT NOT NULL UNIQUE REFERENCES activo(id_activo) ON DELETE CASCADE,
    payload_qr TEXT NOT NULL UNIQUE,
    formato_imagen VARCHAR(20) NOT NULL DEFAULT 'PNG',
    fecha_generacion TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    veces_reimpreso INT NOT NULL DEFAULT 0 CHECK (veces_reimpreso >= 0)
);

COMMENT ON TABLE codigo_qr IS 'Código QR asociado a un activo y generado mediante la API externa definida para SIGET.';
COMMENT ON COLUMN codigo_qr.payload_qr IS 'Contenido o identificador codificado en el QR y asociado al activo.';
COMMENT ON COLUMN codigo_qr.fecha_generacion IS 'Fecha y hora en que SIGET obtuvo el código desde la integración externa.';
COMMENT ON COLUMN codigo_qr.veces_reimpreso IS 'Cantidad de reimpresiones de la etiqueta física.';

-- Tabla 33
CREATE TABLE notificacion (
    id_notificacion SERIAL PRIMARY KEY,
    id_usuario INT NOT NULL REFERENCES usuario(id_usuario) ON DELETE CASCADE,
    modulo_origen VARCHAR(50) NOT NULL,
    titulo VARCHAR(150) NOT NULL,
    mensaje TEXT NOT NULL,
    canal VARCHAR(20) NOT NULL DEFAULT 'PLATAFORMA',
    leida BOOLEAN NOT NULL DEFAULT FALSE,
    estado_envio VARCHAR(20) NOT NULL DEFAULT 'NO_APLICA',
    intentos_envio SMALLINT NOT NULL DEFAULT 0 CHECK (intentos_envio >= 0),
    ultimo_error TEXT,
    fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_ultimo_intento TIMESTAMPTZ,
    fecha_envio TIMESTAMPTZ,
    CONSTRAINT ck_notificacion_canal
        CHECK (canal IN ('PLATAFORMA', 'CORREO_API', 'AMBOS')),
    CONSTRAINT ck_notificacion_estado_envio
        CHECK (estado_envio IN ('NO_APLICA', 'PENDIENTE', 'ENVIADA', 'ERROR')),
    CONSTRAINT ck_notificacion_fechas
        CHECK (
            (fecha_ultimo_intento IS NULL OR fecha_ultimo_intento >= fecha_creacion)
            AND (fecha_envio IS NULL OR fecha_envio >= fecha_creacion)
        )
);

COMMENT ON TABLE notificacion IS 'Notificaciones internas y registro de intentos de correo transaccional.';
COMMENT ON COLUMN notificacion.estado_envio IS 'Estado del envío externo. Para canal PLATAFORMA puede permanecer NO_APLICA.';
COMMENT ON COLUMN notificacion.ultimo_error IS 'Detalle del último error de integración, sin revertir la transacción principal.';
COMMENT ON COLUMN notificacion.fecha_envio IS 'Fecha del envío exitoso; NULL mientras no haya sido enviado.';

-- Tabla 34
CREATE TABLE bitacora_auditoria (
    id_auditoria SERIAL PRIMARY KEY,
    id_usuario INT REFERENCES usuario(id_usuario) ON DELETE SET NULL,
    modulo VARCHAR(50) NOT NULL,
    accion VARCHAR(100) NOT NULL,
    entidad_afectada VARCHAR(100) NOT NULL,
    id_registro_afectado INT,
    detalle_evento TEXT NOT NULL,
    direccion_ip INET,
    fecha_evento TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE bitacora_auditoria IS 'Bitácora protegida para trazabilidad de eventos críticos y acciones administrativas.';
COMMENT ON COLUMN bitacora_auditoria.id_usuario IS 'Usuario responsable; NULL cuando el evento proviene de una operación automática.';
COMMENT ON COLUMN bitacora_auditoria.direccion_ip IS 'Dirección IPv4/IPv6 cuando el evento se origina desde un cliente de red.';
COMMENT ON COLUMN bitacora_auditoria.detalle_evento IS 'Resumen del evento y, cuando corresponda, estado previo/posterior de la operación.';

-- ============================================================================
-- 8. ÍNDICES OPERACIONALES
-- PostgreSQL no crea automáticamente índices en las columnas FK.
-- ============================================================================

CREATE INDEX idx_usuario_rol_usuario ON usuario_rol(id_usuario);
CREATE INDEX idx_usuario_rol_rol ON usuario_rol(id_rol);
CREATE INDEX idx_rol_permiso_rol ON rol_permiso(id_rol);
CREATE INDEX idx_rol_permiso_permiso ON rol_permiso(id_permiso);

CREATE INDEX idx_modelo_categoria ON modelo_activo(id_categoria);
CREATE INDEX idx_activo_modelo ON activo(id_modelo);
CREATE INDEX idx_activo_estado ON activo(id_estado_activo);
CREATE INDEX idx_activo_ubicacion ON activo(id_ubicacion);
CREATE INDEX idx_historial_activo_fecha ON historial_estado_activo(id_activo, fecha_cambio DESC);

CREATE INDEX idx_solicitud_usuario ON solicitud_asignacion(id_usuario);
CREATE INDEX idx_solicitud_categoria ON solicitud_asignacion(id_categoria);
CREATE INDEX idx_solicitud_estado ON solicitud_asignacion(id_estado_solicitud);
CREATE INDEX idx_asignacion_activo ON asignacion(id_activo);
CREATE UNIQUE INDEX uk_asignacion_activo_abierta
ON asignacion(id_activo)
WHERE fecha_finalizacion IS NULL;
CREATE INDEX idx_asignacion_estado ON asignacion(id_estado_asignacion);
CREATE INDEX idx_devolucion_estado_resultante ON devolucion_activo(id_estado_activo_resultante);

CREATE INDEX idx_ticket_solicitante ON ticket(id_usuario_solicitante);
CREATE INDEX idx_ticket_tecnico ON ticket(id_tecnico_asignado);
CREATE INDEX idx_ticket_activo ON ticket(id_activo);
CREATE INDEX idx_ticket_estado ON ticket(id_estado_ticket);
CREATE INDEX idx_ticket_prioridad ON ticket(id_prioridad);
CREATE INDEX idx_comentario_ticket ON comentario_ticket(id_ticket, fecha_registro);
CREATE INDEX idx_adjunto_ticket ON adjunto_ticket(id_ticket);

CREATE INDEX idx_ot_tecnico ON orden_trabajo(id_tecnico_responsable);
CREATE INDEX idx_ot_estado ON orden_trabajo(id_estado_ot);
CREATE INDEX idx_diagnostico_orden ON diagnostico(id_orden);
CREATE INDEX idx_intervencion_orden ON intervencion(id_orden, fecha_intervencion);

CREATE INDEX idx_orden_repuesto_orden ON orden_repuesto(id_orden);
CREATE INDEX idx_movimiento_repuesto_fecha ON movimiento_repuesto(id_repuesto, fecha_movimiento);

CREATE INDEX idx_notificacion_usuario_fecha ON notificacion(id_usuario, fecha_creacion DESC);
CREATE INDEX idx_notificacion_estado_envio ON notificacion(estado_envio);
CREATE INDEX idx_auditoria_fecha ON bitacora_auditoria(fecha_evento DESC);
CREATE INDEX idx_auditoria_entidad ON bitacora_auditoria(entidad_afectada, id_registro_afectado);

-- ============================================================================
-- 9. SEMILLAS DE PRUEBA
-- ============================================================================

-- Roles RBAC oficiales
INSERT INTO rol (nombre, descripcion) VALUES
('Usuario solicitante', 'Portal Web: catálogo, solicitudes de asignación, tickets y seguimiento'),
('Técnico de soporte', 'Escritorio: entregas, devoluciones, tickets asignados, diagnósticos y órdenes de trabajo'),
('Administrador del sistema', 'Administración de usuarios, activos, solicitudes, asignación de tickets, reportería y auditoría');

-- Usuarios base vinculados a proveedor externo (datos de demostración)
INSERT INTO usuario
(identificador_externo, proveedor_identidad, rut, nombres, apellidos, correo)
VALUES
('siget-admin-demo', 'PROVEEDOR_EXTERNO', '11.754.478-8', 'Admin', 'SIGET', 'admin@siget.cl'),
('siget-tecnico-demo', 'PROVEEDOR_EXTERNO', '21.020.957-3', 'Técnico', 'SIGET', 'tecnico@siget.cl'),
('siget-solicitante-demo', 'PROVEEDOR_EXTERNO', '21.762.522-K', 'Usuario', 'Solicitante', 'solicitante@siget.cl');

INSERT INTO usuario_rol (id_usuario, id_rol) VALUES
(1, 3),
(2, 2),
(3, 1);

-- Prioridades y SLA
INSERT INTO prioridad_ticket (nombre, nivel_urgencia, descripcion) VALUES
('Crítico', 1, 'Interrupción total de actividades o servicios troncales'),
('Alto', 2, 'Falla grave que degrada significativamente el servicio'),
('Medio', 3, 'Inconveniente funcional con alternativa operativa'),
('Bajo', 4, 'Consulta o requerimiento menor de configuración');

INSERT INTO sla (id_prioridad, tiempo_respuesta_horas, tiempo_resolucion_horas, descripcion) VALUES
(1, 1, 4, 'SLA Crítico: respuesta <= 1h, resolución <= 4h'),
(2, 2, 8, 'SLA Alto: respuesta <= 2h, resolución <= 8h'),
(3, 4, 24, 'SLA Medio: respuesta <= 4h, resolución <= 24h'),
(4, 8, 72, 'SLA Bajo: respuesta <= 8h, resolución <= 72h');

-- Estados de activo
INSERT INTO estado_activo (nombre, descripcion) VALUES
('Disponible', 'Activo operativo y habilitado para una nueva asignación'),
('Asignado', 'Activo entregado y actualmente asignado a un Usuario solicitante'),
('En revisión', 'Activo bloqueado para asignaciones mientras se realiza evaluación técnica'),
('En reparación', 'Activo con una orden de trabajo en intervención técnica'),
('Dado de baja', 'Activo desincorporado y no habilitado para nuevas asignaciones');

-- Estados de solicitud de asignación
INSERT INTO estado_solicitud_asignacion (nombre, descripcion) VALUES
('Pendiente', 'Solicitud en espera de evaluación administrativa'),
('Aprobada', 'Solicitud aprobada; pendiente de entrega de un activo compatible'),
('Rechazada', 'Solicitud rechazada por el Administrador del sistema'),
('Atendida', 'Solicitud materializada mediante una asignación');

-- Estados de asignación
INSERT INTO estado_asignacion (nombre, descripcion) VALUES
('Activa', 'Activo entregado y actualmente asignado al Usuario solicitante'),
('Finalizada', 'Asignación cerrada mediante una devolución registrada');

-- Estados de ticket
INSERT INTO estado_ticket (nombre, descripcion) VALUES
('Abierto', 'Ticket registrado y pendiente de asignación o atención'),
('En Proceso', 'Ticket actualmente atendido por un Técnico de soporte'),
('En Espera', 'Ticket temporalmente en espera de información o una condición externa'),
('Resuelto', 'Atención técnica finalizada y solución registrada'),
('Cerrado', 'Ticket cerrado para operación normal y disponible para evaluación CSAT');

-- Estados de orden de trabajo
INSERT INTO estado_orden_trabajo (nombre, descripcion) VALUES
('En Diagnóstico', 'Orden abierta para evaluación técnica y diagnóstico inicial'),
('En Reparación', 'Intervención técnica activa sobre el equipo'),
('Pausada', 'Orden temporalmente pausada, por ejemplo por espera de repuestos'),
('Completada', 'Intervención técnica concluida y resultado registrado');

-- Maestros de activos
INSERT INTO categoria_activo (nombre, descripcion) VALUES
('Notebook', 'Equipo portátil'),
('PC Desktop', 'Equipo de escritorio'),
('Proyector', 'Equipo de proyección audiovisual'),
('Impresora', 'Equipo de impresión'),
('Monitor', 'Pantalla o monitor externo');

INSERT INTO marca (nombre) VALUES
('Dell'), ('HP'), ('Lenovo'), ('Epson'), ('Samsung');

INSERT INTO ubicacion (nombre_area, edificio, piso) VALUES
('Departamento TI', 'Edificio Central', 'Piso 2'),
('Bodega TI', 'Edificio Central', 'Piso 1'),
('Laboratorio', 'Edificio A', 'Piso 1');

-- Permisos base mínimos de demostración
INSERT INTO permiso (codigo, descripcion) VALUES
('CATALOGO_CONSULTAR', 'Consultar catálogo y disponibilidad de activos'),
('SOLICITUD_CREAR', 'Registrar solicitud de asignación'),
('SOLICITUD_RESOLVER', 'Aprobar o rechazar solicitudes de asignación'),
('ENTREGA_REGISTRAR', 'Registrar entrega y formalizar una asignación'),
('DEVOLUCION_REGISTRAR', 'Registrar devolución y evaluación inicial'),
('TICKET_CREAR', 'Registrar ticket de soporte'),
('TICKET_ASIGNAR', 'Asignar o reasignar tickets'),
('TICKET_ATENDER', 'Atender tickets asignados'),
('OT_GESTIONAR', 'Gestionar órdenes de trabajo'),
('USUARIOS_ADMINISTRAR', 'Administrar usuarios, roles y permisos'),
('AUDITORIA_CONSULTAR', 'Consultar bitácora y reportes de auditoría');

-- Asignación mínima de permisos por rol
INSERT INTO rol_permiso (id_rol, id_permiso)
SELECT 1, id_permiso FROM permiso
WHERE codigo IN ('CATALOGO_CONSULTAR', 'SOLICITUD_CREAR', 'TICKET_CREAR');

INSERT INTO rol_permiso (id_rol, id_permiso)
SELECT 2, id_permiso FROM permiso
WHERE codigo IN (
    'CATALOGO_CONSULTAR',
    'ENTREGA_REGISTRAR',
    'DEVOLUCION_REGISTRAR',
    'TICKET_ATENDER',
    'OT_GESTIONAR'
);

INSERT INTO rol_permiso (id_rol, id_permiso)
SELECT 3, id_permiso FROM permiso
WHERE codigo IN (
    'CATALOGO_CONSULTAR',
    'SOLICITUD_RESOLVER',
    'TICKET_ASIGNAR',
    'USUARIOS_ADMINISTRAR',
    'AUDITORIA_CONSULTAR'
);

COMMIT;
