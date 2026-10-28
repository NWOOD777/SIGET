--
-- PostgreSQL database dump
--

\restrict A6qd71F4Nawnw8vcgyQwYyNJYpA2POWbGFGLxcSLDUXdbigD6gPmJuVYSqyOCTz

-- Dumped from database version 17.11 (Debian 17.11-1.pgdg13+2)
-- Dumped by pg_dump version 17.11 (Debian 17.11-1.pgdg13+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: activo; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.activo (
    id_activo integer NOT NULL,
    codigo_inventario character varying(50) NOT NULL,
    numero_serie character varying(100) NOT NULL,
    id_modelo integer NOT NULL,
    id_ubicacion integer NOT NULL,
    id_estado_activo integer NOT NULL,
    valor_adquisicion numeric(12,2) DEFAULT 0 NOT NULL,
    fecha_compra date,
    fecha_garantia date,
    fecha_registro timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT activo_valor_adquisicion_check CHECK ((valor_adquisicion >= (0)::numeric)),
    CONSTRAINT ck_activo_garantia CHECK (((fecha_garantia IS NULL) OR (fecha_compra IS NULL) OR (fecha_garantia >= fecha_compra)))
);


ALTER TABLE public.activo OWNER TO siget_dev;

--
-- Name: TABLE activo; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.activo IS 'Inventario individual de activos tecnológicos.';


--
-- Name: COLUMN activo.id_modelo; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.activo.id_modelo IS 'El modelo determina también la categoría del activo.';


--
-- Name: COLUMN activo.id_estado_activo; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.activo.id_estado_activo IS 'Estado físico/operativo actual del activo.';


--
-- Name: activo_id_activo_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.activo_id_activo_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.activo_id_activo_seq OWNER TO siget_dev;

--
-- Name: activo_id_activo_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.activo_id_activo_seq OWNED BY public.activo.id_activo;


--
-- Name: adjunto_ticket; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.adjunto_ticket (
    id_adjunto integer NOT NULL,
    id_ticket integer NOT NULL,
    nombre_archivo character varying(255) NOT NULL,
    ruta_archivo character varying(500) NOT NULL,
    tipo_mime character varying(100),
    tamano_bytes bigint,
    fecha_subida timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT adjunto_ticket_tamano_bytes_check CHECK (((tamano_bytes IS NULL) OR (tamano_bytes >= 0)))
);


ALTER TABLE public.adjunto_ticket OWNER TO siget_dev;

--
-- Name: TABLE adjunto_ticket; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.adjunto_ticket IS 'Archivos de evidencia asociados a tickets de soporte.';


--
-- Name: adjunto_ticket_id_adjunto_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.adjunto_ticket_id_adjunto_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.adjunto_ticket_id_adjunto_seq OWNER TO siget_dev;

--
-- Name: adjunto_ticket_id_adjunto_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.adjunto_ticket_id_adjunto_seq OWNED BY public.adjunto_ticket.id_adjunto;


--
-- Name: asignacion; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.asignacion (
    id_asignacion integer NOT NULL,
    id_solicitud integer NOT NULL,
    id_activo integer NOT NULL,
    id_tecnico_entrega integer NOT NULL,
    id_estado_asignacion integer NOT NULL,
    fecha_entrega timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    fecha_devolucion_prevista timestamp with time zone,
    fecha_finalizacion timestamp with time zone,
    CONSTRAINT ck_asignacion_fechas CHECK ((((fecha_devolucion_prevista IS NULL) OR (fecha_devolucion_prevista >= fecha_entrega)) AND ((fecha_finalizacion IS NULL) OR (fecha_finalizacion >= fecha_entrega))))
);


ALTER TABLE public.asignacion OWNER TO siget_dev;

--
-- Name: TABLE asignacion; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.asignacion IS 'Asignación física de un activo compatible con una solicitud previamente aprobada.';


--
-- Name: COLUMN asignacion.id_solicitud; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.asignacion.id_solicitud IS 'UNIQUE: una solicitud puede originar como máximo una asignación.';


--
-- Name: COLUMN asignacion.id_activo; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.asignacion.id_activo IS 'Activo físico seleccionado por el Técnico de soporte durante la entrega.';


--
-- Name: COLUMN asignacion.id_tecnico_entrega; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.asignacion.id_tecnico_entrega IS 'Técnico de soporte que registra la entrega física.';


--
-- Name: COLUMN asignacion.fecha_devolucion_prevista; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.asignacion.fecha_devolucion_prevista IS 'Fecha prevista opcional; no es obligatoria para materializar la entrega.';


--
-- Name: COLUMN asignacion.fecha_finalizacion; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.asignacion.fecha_finalizacion IS 'Fecha en que la asignación se cierra mediante devolución.';


--
-- Name: asignacion_id_asignacion_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.asignacion_id_asignacion_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.asignacion_id_asignacion_seq OWNER TO siget_dev;

--
-- Name: asignacion_id_asignacion_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.asignacion_id_asignacion_seq OWNED BY public.asignacion.id_asignacion;


--
-- Name: bitacora_auditoria; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.bitacora_auditoria (
    id_auditoria integer NOT NULL,
    id_usuario integer,
    modulo character varying(50) NOT NULL,
    accion character varying(100) NOT NULL,
    entidad_afectada character varying(100) NOT NULL,
    id_registro_afectado integer,
    detalle_evento text NOT NULL,
    direccion_ip inet,
    fecha_evento timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


ALTER TABLE public.bitacora_auditoria OWNER TO siget_dev;

--
-- Name: TABLE bitacora_auditoria; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.bitacora_auditoria IS 'Bitácora protegida para trazabilidad de eventos críticos y acciones administrativas.';


--
-- Name: COLUMN bitacora_auditoria.id_usuario; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.bitacora_auditoria.id_usuario IS 'Usuario responsable; NULL cuando el evento proviene de una operación automática.';


--
-- Name: COLUMN bitacora_auditoria.detalle_evento; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.bitacora_auditoria.detalle_evento IS 'Resumen del evento y, cuando corresponda, estado previo/posterior de la operación.';


--
-- Name: COLUMN bitacora_auditoria.direccion_ip; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.bitacora_auditoria.direccion_ip IS 'Dirección IPv4/IPv6 cuando el evento se origina desde un cliente de red.';


--
-- Name: bitacora_auditoria_id_auditoria_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.bitacora_auditoria_id_auditoria_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.bitacora_auditoria_id_auditoria_seq OWNER TO siget_dev;

--
-- Name: bitacora_auditoria_id_auditoria_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.bitacora_auditoria_id_auditoria_seq OWNED BY public.bitacora_auditoria.id_auditoria;


--
-- Name: categoria_activo; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.categoria_activo (
    id_categoria integer NOT NULL,
    nombre character varying(100) NOT NULL,
    descripcion character varying(255)
);


ALTER TABLE public.categoria_activo OWNER TO siget_dev;

--
-- Name: TABLE categoria_activo; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.categoria_activo IS 'Catálogo de tipos o familias de activos tecnológicos.';


--
-- Name: categoria_activo_id_categoria_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.categoria_activo_id_categoria_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.categoria_activo_id_categoria_seq OWNER TO siget_dev;

--
-- Name: categoria_activo_id_categoria_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.categoria_activo_id_categoria_seq OWNED BY public.categoria_activo.id_categoria;


--
-- Name: codigo_qr; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.codigo_qr (
    id_qr integer NOT NULL,
    id_activo integer NOT NULL,
    payload_qr text NOT NULL,
    formato_imagen character varying(20) DEFAULT 'PNG'::character varying NOT NULL,
    fecha_generacion timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    veces_reimpreso integer DEFAULT 0 NOT NULL,
    CONSTRAINT codigo_qr_veces_reimpreso_check CHECK ((veces_reimpreso >= 0))
);


ALTER TABLE public.codigo_qr OWNER TO siget_dev;

--
-- Name: TABLE codigo_qr; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.codigo_qr IS 'Código QR asociado a un activo y generado mediante la API externa definida para SIGET.';


--
-- Name: COLUMN codigo_qr.payload_qr; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.codigo_qr.payload_qr IS 'Contenido o identificador codificado en el QR y asociado al activo.';


--
-- Name: COLUMN codigo_qr.fecha_generacion; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.codigo_qr.fecha_generacion IS 'Fecha y hora en que SIGET obtuvo el código desde la integración externa.';


--
-- Name: COLUMN codigo_qr.veces_reimpreso; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.codigo_qr.veces_reimpreso IS 'Cantidad de reimpresiones de la etiqueta física.';


--
-- Name: codigo_qr_id_qr_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.codigo_qr_id_qr_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.codigo_qr_id_qr_seq OWNER TO siget_dev;

--
-- Name: codigo_qr_id_qr_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.codigo_qr_id_qr_seq OWNED BY public.codigo_qr.id_qr;


--
-- Name: comentario_ticket; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.comentario_ticket (
    id_comentario integer NOT NULL,
    id_ticket integer NOT NULL,
    id_usuario integer NOT NULL,
    mensaje text NOT NULL,
    fecha_registro timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


ALTER TABLE public.comentario_ticket OWNER TO siget_dev;

--
-- Name: TABLE comentario_ticket; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.comentario_ticket IS 'Historial conversacional y de seguimiento de un ticket.';


--
-- Name: comentario_ticket_id_comentario_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.comentario_ticket_id_comentario_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.comentario_ticket_id_comentario_seq OWNER TO siget_dev;

--
-- Name: comentario_ticket_id_comentario_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.comentario_ticket_id_comentario_seq OWNED BY public.comentario_ticket.id_comentario;


--
-- Name: devolucion_activo; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.devolucion_activo (
    id_devolucion integer NOT NULL,
    id_asignacion integer NOT NULL,
    id_tecnico_receptor integer NOT NULL,
    id_estado_activo_resultante integer NOT NULL,
    fecha_devolucion timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    condicion_fisica character varying(50) NOT NULL,
    motivo_devolucion character varying(100),
    observaciones text,
    CONSTRAINT ck_devolucion_condicion CHECK (((condicion_fisica)::text = ANY ((ARRAY['Buen estado'::character varying, 'Con falla técnica'::character varying, 'Con daño físico'::character varying])::text[])))
);


ALTER TABLE public.devolucion_activo OWNER TO siget_dev;

--
-- Name: TABLE devolucion_activo; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.devolucion_activo IS 'Registro de recepción física y evaluación inicial de un activo devuelto.';


--
-- Name: COLUMN devolucion_activo.id_asignacion; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.devolucion_activo.id_asignacion IS 'La devolución obtiene el activo desde la asignación, evitando duplicar y desincronizar la referencia.';


--
-- Name: COLUMN devolucion_activo.id_tecnico_receptor; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.devolucion_activo.id_tecnico_receptor IS 'Técnico de soporte que recibe y evalúa el activo.';


--
-- Name: COLUMN devolucion_activo.id_estado_activo_resultante; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.devolucion_activo.id_estado_activo_resultante IS 'Resultado esperado de la evaluación inicial: normalmente Disponible o En revisión.';


--
-- Name: devolucion_activo_id_devolucion_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.devolucion_activo_id_devolucion_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.devolucion_activo_id_devolucion_seq OWNER TO siget_dev;

--
-- Name: devolucion_activo_id_devolucion_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.devolucion_activo_id_devolucion_seq OWNED BY public.devolucion_activo.id_devolucion;


--
-- Name: diagnostico; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.diagnostico (
    id_diagnostico integer NOT NULL,
    id_orden integer NOT NULL,
    id_tecnico integer NOT NULL,
    descripcion_falla text NOT NULL,
    procedimiento_inicial text NOT NULL,
    es_reparable boolean DEFAULT true NOT NULL,
    fecha_diagnostico timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


ALTER TABLE public.diagnostico OWNER TO siget_dev;

--
-- Name: TABLE diagnostico; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.diagnostico IS 'Diagnósticos técnicos registrados dentro de una orden de trabajo.';


--
-- Name: diagnostico_id_diagnostico_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.diagnostico_id_diagnostico_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.diagnostico_id_diagnostico_seq OWNER TO siget_dev;

--
-- Name: diagnostico_id_diagnostico_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.diagnostico_id_diagnostico_seq OWNED BY public.diagnostico.id_diagnostico;


--
-- Name: django_migrations; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.django_migrations (
    id bigint NOT NULL,
    app character varying(255) NOT NULL,
    name character varying(255) NOT NULL,
    applied timestamp with time zone NOT NULL
);


ALTER TABLE public.django_migrations OWNER TO siget_dev;

--
-- Name: django_migrations_id_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

ALTER TABLE public.django_migrations ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.django_migrations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: django_session; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.django_session (
    session_key character varying(40) NOT NULL,
    session_data text NOT NULL,
    expire_date timestamp with time zone NOT NULL
);


ALTER TABLE public.django_session OWNER TO siget_dev;

--
-- Name: estado_activo; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.estado_activo (
    id_estado_activo integer NOT NULL,
    nombre character varying(50) NOT NULL,
    descripcion character varying(255)
);


ALTER TABLE public.estado_activo OWNER TO siget_dev;

--
-- Name: TABLE estado_activo; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.estado_activo IS 'Estados canónicos del activo: Disponible, Asignado, En revisión, En reparación y Dado de baja.';


--
-- Name: estado_activo_id_estado_activo_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.estado_activo_id_estado_activo_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.estado_activo_id_estado_activo_seq OWNER TO siget_dev;

--
-- Name: estado_activo_id_estado_activo_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.estado_activo_id_estado_activo_seq OWNED BY public.estado_activo.id_estado_activo;


--
-- Name: estado_asignacion; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.estado_asignacion (
    id_estado_asignacion integer NOT NULL,
    nombre character varying(50) NOT NULL,
    descripcion character varying(255)
);


ALTER TABLE public.estado_asignacion OWNER TO siget_dev;

--
-- Name: TABLE estado_asignacion; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.estado_asignacion IS 'Estados exclusivos de una asignación ya materializada físicamente.';


--
-- Name: estado_asignacion_id_estado_asignacion_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.estado_asignacion_id_estado_asignacion_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.estado_asignacion_id_estado_asignacion_seq OWNER TO siget_dev;

--
-- Name: estado_asignacion_id_estado_asignacion_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.estado_asignacion_id_estado_asignacion_seq OWNED BY public.estado_asignacion.id_estado_asignacion;


--
-- Name: estado_orden_trabajo; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.estado_orden_trabajo (
    id_estado_ot integer NOT NULL,
    nombre character varying(50) NOT NULL,
    descripcion character varying(255)
);


ALTER TABLE public.estado_orden_trabajo OWNER TO siget_dev;

--
-- Name: TABLE estado_orden_trabajo; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.estado_orden_trabajo IS 'Estados del ciclo de una orden de trabajo: En diagnóstico, En reparación, Pausada y Completada.';


--
-- Name: estado_orden_trabajo_id_estado_ot_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.estado_orden_trabajo_id_estado_ot_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.estado_orden_trabajo_id_estado_ot_seq OWNER TO siget_dev;

--
-- Name: estado_orden_trabajo_id_estado_ot_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.estado_orden_trabajo_id_estado_ot_seq OWNED BY public.estado_orden_trabajo.id_estado_ot;


--
-- Name: estado_solicitud_asignacion; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.estado_solicitud_asignacion (
    id_estado_solicitud integer NOT NULL,
    nombre character varying(50) NOT NULL,
    descripcion character varying(255)
);


ALTER TABLE public.estado_solicitud_asignacion OWNER TO siget_dev;

--
-- Name: TABLE estado_solicitud_asignacion; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.estado_solicitud_asignacion IS 'Estados exclusivos del ciclo de solicitud de asignación.';


--
-- Name: estado_solicitud_asignacion_id_estado_solicitud_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.estado_solicitud_asignacion_id_estado_solicitud_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.estado_solicitud_asignacion_id_estado_solicitud_seq OWNER TO siget_dev;

--
-- Name: estado_solicitud_asignacion_id_estado_solicitud_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.estado_solicitud_asignacion_id_estado_solicitud_seq OWNED BY public.estado_solicitud_asignacion.id_estado_solicitud;


--
-- Name: estado_ticket; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.estado_ticket (
    id_estado_ticket integer NOT NULL,
    nombre character varying(50) NOT NULL,
    descripcion character varying(255)
);


ALTER TABLE public.estado_ticket OWNER TO siget_dev;

--
-- Name: TABLE estado_ticket; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.estado_ticket IS 'Estados de ciclo de vida del ticket de soporte.';


--
-- Name: estado_ticket_id_estado_ticket_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.estado_ticket_id_estado_ticket_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.estado_ticket_id_estado_ticket_seq OWNER TO siget_dev;

--
-- Name: estado_ticket_id_estado_ticket_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.estado_ticket_id_estado_ticket_seq OWNED BY public.estado_ticket.id_estado_ticket;


--
-- Name: evaluacion_csat; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.evaluacion_csat (
    id_evaluacion integer NOT NULL,
    id_ticket integer NOT NULL,
    id_usuario integer NOT NULL,
    calificacion_estrellas integer NOT NULL,
    comentario text,
    fecha_evaluacion timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT evaluacion_csat_calificacion_estrellas_check CHECK (((calificacion_estrellas >= 1) AND (calificacion_estrellas <= 5)))
);


ALTER TABLE public.evaluacion_csat OWNER TO siget_dev;

--
-- Name: TABLE evaluacion_csat; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.evaluacion_csat IS 'Evaluación CSAT registrada por el Usuario solicitante tras el cierre del ticket.';


--
-- Name: evaluacion_csat_id_evaluacion_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.evaluacion_csat_id_evaluacion_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.evaluacion_csat_id_evaluacion_seq OWNER TO siget_dev;

--
-- Name: evaluacion_csat_id_evaluacion_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.evaluacion_csat_id_evaluacion_seq OWNED BY public.evaluacion_csat.id_evaluacion;


--
-- Name: historial_estado_activo; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.historial_estado_activo (
    id_historial_estado integer NOT NULL,
    id_activo integer NOT NULL,
    id_estado_activo integer NOT NULL,
    id_usuario integer,
    fecha_cambio timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    observacion text
);


ALTER TABLE public.historial_estado_activo OWNER TO siget_dev;

--
-- Name: TABLE historial_estado_activo; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.historial_estado_activo IS 'Historial protegido de cambios de estado de los activos.';


--
-- Name: COLUMN historial_estado_activo.id_usuario; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.historial_estado_activo.id_usuario IS 'Usuario responsable del cambio; puede ser NULL si el evento fue generado automáticamente.';


--
-- Name: historial_estado_activo_id_historial_estado_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.historial_estado_activo_id_historial_estado_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.historial_estado_activo_id_historial_estado_seq OWNER TO siget_dev;

--
-- Name: historial_estado_activo_id_historial_estado_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.historial_estado_activo_id_historial_estado_seq OWNED BY public.historial_estado_activo.id_historial_estado;


--
-- Name: intervencion; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.intervencion (
    id_intervencion integer NOT NULL,
    id_orden integer NOT NULL,
    id_tecnico integer NOT NULL,
    descripcion_accion text NOT NULL,
    resultado_prueba text,
    fecha_intervencion timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


ALTER TABLE public.intervencion OWNER TO siget_dev;

--
-- Name: TABLE intervencion; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.intervencion IS 'Intervenciones y pruebas técnicas realizadas sobre una orden de trabajo.';


--
-- Name: intervencion_id_intervencion_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.intervencion_id_intervencion_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.intervencion_id_intervencion_seq OWNER TO siget_dev;

--
-- Name: intervencion_id_intervencion_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.intervencion_id_intervencion_seq OWNED BY public.intervencion.id_intervencion;


--
-- Name: marca; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.marca (
    id_marca integer NOT NULL,
    nombre character varying(100) NOT NULL
);


ALTER TABLE public.marca OWNER TO siget_dev;

--
-- Name: TABLE marca; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.marca IS 'Catálogo de fabricantes y marcas de activos tecnológicos.';


--
-- Name: marca_id_marca_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.marca_id_marca_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.marca_id_marca_seq OWNER TO siget_dev;

--
-- Name: marca_id_marca_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.marca_id_marca_seq OWNED BY public.marca.id_marca;


--
-- Name: modelo_activo; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.modelo_activo (
    id_modelo integer NOT NULL,
    id_marca integer NOT NULL,
    id_categoria integer NOT NULL,
    nombre character varying(100) NOT NULL
);


ALTER TABLE public.modelo_activo OWNER TO siget_dev;

--
-- Name: TABLE modelo_activo; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.modelo_activo IS 'Modelos de activos vinculados a una marca y una categoría.';


--
-- Name: COLUMN modelo_activo.id_categoria; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.modelo_activo.id_categoria IS 'La categoría se define a nivel de modelo y no se duplica en activo.';


--
-- Name: modelo_activo_id_modelo_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.modelo_activo_id_modelo_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.modelo_activo_id_modelo_seq OWNER TO siget_dev;

--
-- Name: modelo_activo_id_modelo_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.modelo_activo_id_modelo_seq OWNED BY public.modelo_activo.id_modelo;


--
-- Name: movimiento_repuesto; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.movimiento_repuesto (
    id_movimiento integer NOT NULL,
    id_repuesto integer NOT NULL,
    id_usuario integer NOT NULL,
    tipo_movimiento character varying(50) NOT NULL,
    cantidad integer NOT NULL,
    costo_unitario numeric(12,2) DEFAULT 0,
    motivo character varying(255),
    fecha_movimiento timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_movimiento_repuesto_tipo CHECK (((tipo_movimiento)::text = ANY ((ARRAY['INGRESO_COMPRA'::character varying, 'AJUSTE_INVENTARIO'::character varying, 'SALIDA_TALLER'::character varying, 'DEVOLUCION_TALLER'::character varying])::text[]))),
    CONSTRAINT movimiento_repuesto_cantidad_check CHECK ((cantidad > 0)),
    CONSTRAINT movimiento_repuesto_costo_unitario_check CHECK ((costo_unitario >= (0)::numeric))
);


ALTER TABLE public.movimiento_repuesto OWNER TO siget_dev;

--
-- Name: TABLE movimiento_repuesto; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.movimiento_repuesto IS 'Movimientos de inventario de repuestos.';


--
-- Name: COLUMN movimiento_repuesto.id_usuario; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.movimiento_repuesto.id_usuario IS 'Administrador del sistema o Técnico de soporte autorizado que registra el movimiento.';


--
-- Name: movimiento_repuesto_id_movimiento_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.movimiento_repuesto_id_movimiento_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.movimiento_repuesto_id_movimiento_seq OWNER TO siget_dev;

--
-- Name: movimiento_repuesto_id_movimiento_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.movimiento_repuesto_id_movimiento_seq OWNED BY public.movimiento_repuesto.id_movimiento;


--
-- Name: notificacion; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.notificacion (
    id_notificacion integer NOT NULL,
    id_usuario integer NOT NULL,
    modulo_origen character varying(50) NOT NULL,
    titulo character varying(150) NOT NULL,
    mensaje text NOT NULL,
    canal character varying(20) DEFAULT 'PLATAFORMA'::character varying NOT NULL,
    leida boolean DEFAULT false NOT NULL,
    estado_envio character varying(20) DEFAULT 'NO_APLICA'::character varying NOT NULL,
    intentos_envio smallint DEFAULT 0 NOT NULL,
    ultimo_error text,
    fecha_creacion timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    fecha_ultimo_intento timestamp with time zone,
    fecha_envio timestamp with time zone,
    clave_evento character varying(255),
    datos_envio jsonb DEFAULT '{}'::jsonb NOT NULL,
    referencia jsonb DEFAULT '{}'::jsonb NOT NULL,
    id_proveedor character varying(100),
    reintento_permitido boolean DEFAULT true NOT NULL,
    proximo_intento timestamp with time zone,
    fecha_primer_intento timestamp with time zone,
    CONSTRAINT ck_notificacion_canal CHECK (((canal)::text = ANY ((ARRAY['PLATAFORMA'::character varying, 'CORREO_API'::character varying, 'AMBOS'::character varying])::text[]))),
    CONSTRAINT ck_notificacion_estado_envio CHECK (((estado_envio)::text = ANY ((ARRAY['NO_APLICA'::character varying, 'PENDIENTE'::character varying, 'ENVIADA'::character varying, 'ERROR'::character varying])::text[]))),
    CONSTRAINT ck_notificacion_fechas CHECK ((((fecha_ultimo_intento IS NULL) OR (fecha_ultimo_intento >= fecha_creacion)) AND ((fecha_envio IS NULL) OR (fecha_envio >= fecha_creacion)))),
    CONSTRAINT notificacion_intentos_envio_check CHECK ((intentos_envio >= 0))
);


ALTER TABLE public.notificacion OWNER TO siget_dev;

--
-- Name: TABLE notificacion; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.notificacion IS 'Notificaciones internas y registro de intentos de correo transaccional.';


--
-- Name: COLUMN notificacion.estado_envio; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.notificacion.estado_envio IS 'Estado del envío externo. Para canal PLATAFORMA puede permanecer NO_APLICA.';


--
-- Name: COLUMN notificacion.ultimo_error; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.notificacion.ultimo_error IS 'Detalle del último error de integración, sin revertir la transacción principal.';


--
-- Name: COLUMN notificacion.fecha_envio; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.notificacion.fecha_envio IS 'Fecha del envío exitoso; NULL mientras no haya sido enviado.';


--
-- Name: notificacion_id_notificacion_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.notificacion_id_notificacion_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.notificacion_id_notificacion_seq OWNER TO siget_dev;

--
-- Name: notificacion_id_notificacion_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.notificacion_id_notificacion_seq OWNED BY public.notificacion.id_notificacion;


--
-- Name: orden_repuesto; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.orden_repuesto (
    id_orden_repuesto integer NOT NULL,
    id_orden integer NOT NULL,
    id_repuesto integer NOT NULL,
    cantidad integer NOT NULL,
    costo_unitario numeric(12,2) DEFAULT 0 NOT NULL,
    fecha_imputacion timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT orden_repuesto_cantidad_check CHECK ((cantidad > 0)),
    CONSTRAINT orden_repuesto_costo_unitario_check CHECK ((costo_unitario >= (0)::numeric))
);


ALTER TABLE public.orden_repuesto OWNER TO siget_dev;

--
-- Name: TABLE orden_repuesto; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.orden_repuesto IS 'Consumo de repuestos imputado a una orden de trabajo.';


--
-- Name: orden_repuesto_id_orden_repuesto_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.orden_repuesto_id_orden_repuesto_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.orden_repuesto_id_orden_repuesto_seq OWNER TO siget_dev;

--
-- Name: orden_repuesto_id_orden_repuesto_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.orden_repuesto_id_orden_repuesto_seq OWNED BY public.orden_repuesto.id_orden_repuesto;


--
-- Name: orden_trabajo; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.orden_trabajo (
    id_orden integer NOT NULL,
    codigo_ot character varying(50) NOT NULL,
    id_ticket integer NOT NULL,
    id_tecnico_responsable integer NOT NULL,
    id_estado_ot integer NOT NULL,
    falla_reportada text NOT NULL,
    fecha_inicio timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    fecha_estimada_fin timestamp with time zone,
    fecha_termino timestamp with time zone,
    justificacion_pausa text,
    CONSTRAINT ck_ot_fechas CHECK ((((fecha_estimada_fin IS NULL) OR (fecha_estimada_fin >= fecha_inicio)) AND ((fecha_termino IS NULL) OR (fecha_termino >= fecha_inicio))))
);


ALTER TABLE public.orden_trabajo OWNER TO siget_dev;

--
-- Name: TABLE orden_trabajo; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.orden_trabajo IS 'Orden de trabajo asociada a un ticket que referencia el activo a intervenir.';


--
-- Name: COLUMN orden_trabajo.id_ticket; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.orden_trabajo.id_ticket IS 'UNIQUE: una orden de trabajo se vincula a un ticket; el activo se obtiene desde ticket.id_activo.';


--
-- Name: COLUMN orden_trabajo.id_tecnico_responsable; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.orden_trabajo.id_tecnico_responsable IS 'Técnico de soporte responsable; la reasignación actualiza esta referencia y se audita.';


--
-- Name: orden_trabajo_id_orden_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.orden_trabajo_id_orden_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.orden_trabajo_id_orden_seq OWNER TO siget_dev;

--
-- Name: orden_trabajo_id_orden_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.orden_trabajo_id_orden_seq OWNED BY public.orden_trabajo.id_orden;


--
-- Name: permiso; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.permiso (
    id_permiso integer NOT NULL,
    codigo character varying(50) NOT NULL,
    descripcion character varying(255) NOT NULL
);


ALTER TABLE public.permiso OWNER TO siget_dev;

--
-- Name: TABLE permiso; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.permiso IS 'Catálogo de permisos granulares sobre módulos, operaciones y endpoints de SIGET.';


--
-- Name: permiso_id_permiso_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.permiso_id_permiso_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.permiso_id_permiso_seq OWNER TO siget_dev;

--
-- Name: permiso_id_permiso_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.permiso_id_permiso_seq OWNED BY public.permiso.id_permiso;


--
-- Name: prioridad_ticket; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.prioridad_ticket (
    id_prioridad integer NOT NULL,
    nombre character varying(50) NOT NULL,
    nivel_urgencia integer NOT NULL,
    descripcion character varying(255),
    CONSTRAINT prioridad_ticket_nivel_urgencia_check CHECK ((nivel_urgencia > 0))
);


ALTER TABLE public.prioridad_ticket OWNER TO siget_dev;

--
-- Name: TABLE prioridad_ticket; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.prioridad_ticket IS 'Catálogo de prioridades de tickets y su orden de urgencia.';


--
-- Name: prioridad_ticket_id_prioridad_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.prioridad_ticket_id_prioridad_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.prioridad_ticket_id_prioridad_seq OWNER TO siget_dev;

--
-- Name: prioridad_ticket_id_prioridad_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.prioridad_ticket_id_prioridad_seq OWNED BY public.prioridad_ticket.id_prioridad;


--
-- Name: repuesto; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.repuesto (
    id_repuesto integer NOT NULL,
    codigo_repuesto character varying(50) NOT NULL,
    nombre character varying(150) NOT NULL,
    marca_modelo character varying(150),
    unidad_medida character varying(50) DEFAULT 'Unidad'::character varying NOT NULL,
    stock_actual integer DEFAULT 0 NOT NULL,
    stock_minimo integer DEFAULT 5 NOT NULL,
    precio_unitario numeric(12,2) DEFAULT 0 NOT NULL,
    ubicacion_bodega character varying(100),
    activo boolean DEFAULT true NOT NULL,
    CONSTRAINT repuesto_precio_unitario_check CHECK ((precio_unitario >= (0)::numeric)),
    CONSTRAINT repuesto_stock_actual_check CHECK ((stock_actual >= 0)),
    CONSTRAINT repuesto_stock_minimo_check CHECK ((stock_minimo >= 0))
);


ALTER TABLE public.repuesto OWNER TO siget_dev;

--
-- Name: TABLE repuesto; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.repuesto IS 'Catálogo e inventario de repuestos, componentes e insumos técnicos.';


--
-- Name: repuesto_id_repuesto_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.repuesto_id_repuesto_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.repuesto_id_repuesto_seq OWNER TO siget_dev;

--
-- Name: repuesto_id_repuesto_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.repuesto_id_repuesto_seq OWNED BY public.repuesto.id_repuesto;


--
-- Name: rol; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.rol (
    id_rol integer NOT NULL,
    nombre character varying(50) NOT NULL,
    descripcion character varying(255)
);


ALTER TABLE public.rol OWNER TO siget_dev;

--
-- Name: TABLE rol; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.rol IS 'Catálogo de roles oficiales para control de acceso RBAC.';


--
-- Name: COLUMN rol.nombre; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.rol.nombre IS 'Roles canónicos: Usuario solicitante, Técnico de soporte, Administrador del sistema.';


--
-- Name: rol_id_rol_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.rol_id_rol_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.rol_id_rol_seq OWNER TO siget_dev;

--
-- Name: rol_id_rol_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.rol_id_rol_seq OWNED BY public.rol.id_rol;


--
-- Name: rol_permiso; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.rol_permiso (
    id_rol_permiso integer NOT NULL,
    id_rol integer NOT NULL,
    id_permiso integer NOT NULL
);


ALTER TABLE public.rol_permiso OWNER TO siget_dev;

--
-- Name: TABLE rol_permiso; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.rol_permiso IS 'Relación N:M entre roles y permisos.';


--
-- Name: rol_permiso_id_rol_permiso_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.rol_permiso_id_rol_permiso_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.rol_permiso_id_rol_permiso_seq OWNER TO siget_dev;

--
-- Name: rol_permiso_id_rol_permiso_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.rol_permiso_id_rol_permiso_seq OWNED BY public.rol_permiso.id_rol_permiso;


--
-- Name: sla; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.sla (
    id_sla integer NOT NULL,
    id_prioridad integer NOT NULL,
    tiempo_respuesta_horas integer NOT NULL,
    tiempo_resolucion_horas integer NOT NULL,
    descripcion character varying(255),
    CONSTRAINT ck_sla_tiempos CHECK ((tiempo_resolucion_horas >= tiempo_respuesta_horas)),
    CONSTRAINT sla_tiempo_resolucion_horas_check CHECK ((tiempo_resolucion_horas > 0)),
    CONSTRAINT sla_tiempo_respuesta_horas_check CHECK ((tiempo_respuesta_horas > 0))
);


ALTER TABLE public.sla OWNER TO siget_dev;

--
-- Name: TABLE sla; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.sla IS 'Política SLA única por prioridad.';


--
-- Name: COLUMN sla.id_prioridad; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.sla.id_prioridad IS 'UNIQUE: cada prioridad referencia una única política SLA vigente en este modelo.';


--
-- Name: sla_id_sla_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.sla_id_sla_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sla_id_sla_seq OWNER TO siget_dev;

--
-- Name: sla_id_sla_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.sla_id_sla_seq OWNED BY public.sla.id_sla;


--
-- Name: solicitud_asignacion; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.solicitud_asignacion (
    id_solicitud integer NOT NULL,
    id_usuario integer NOT NULL,
    id_categoria integer NOT NULL,
    id_estado_solicitud integer NOT NULL,
    id_administrador_resolutor integer,
    fecha_solicitud timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    fecha_resolucion timestamp with time zone,
    motivo text NOT NULL,
    motivo_rechazo text,
    CONSTRAINT ck_solicitud_fechas CHECK (((fecha_resolucion IS NULL) OR (fecha_resolucion >= fecha_solicitud)))
);


ALTER TABLE public.solicitud_asignacion OWNER TO siget_dev;

--
-- Name: TABLE solicitud_asignacion; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.solicitud_asignacion IS 'Solicitud registrada por un Usuario solicitante para una categoría o tipo de equipo.';


--
-- Name: COLUMN solicitud_asignacion.id_categoria; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.solicitud_asignacion.id_categoria IS 'Tipo/categoría requerida; la solicitud no reserva un activo físico específico.';


--
-- Name: COLUMN solicitud_asignacion.id_administrador_resolutor; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.solicitud_asignacion.id_administrador_resolutor IS 'Administrador del sistema que aprueba o rechaza la solicitud.';


--
-- Name: COLUMN solicitud_asignacion.motivo_rechazo; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.solicitud_asignacion.motivo_rechazo IS 'Justificación de rechazo cuando corresponda.';


--
-- Name: solicitud_asignacion_id_solicitud_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.solicitud_asignacion_id_solicitud_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.solicitud_asignacion_id_solicitud_seq OWNER TO siget_dev;

--
-- Name: solicitud_asignacion_id_solicitud_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.solicitud_asignacion_id_solicitud_seq OWNED BY public.solicitud_asignacion.id_solicitud;


--
-- Name: ticket; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.ticket (
    id_ticket integer NOT NULL,
    codigo_ticket character varying(50) NOT NULL,
    id_usuario_solicitante integer NOT NULL,
    id_tecnico_asignado integer,
    id_activo integer,
    id_estado_ticket integer NOT NULL,
    id_prioridad integer NOT NULL,
    asunto character varying(200) NOT NULL,
    descripcion text NOT NULL,
    fecha_creacion timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    fecha_resolucion timestamp with time zone,
    CONSTRAINT ck_ticket_fechas CHECK (((fecha_resolucion IS NULL) OR (fecha_resolucion >= fecha_creacion)))
);


ALTER TABLE public.ticket OWNER TO siget_dev;

--
-- Name: TABLE ticket; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.ticket IS 'Tickets de soporte gestionados bajo el modelo Service Desk.';


--
-- Name: COLUMN ticket.id_tecnico_asignado; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.ticket.id_tecnico_asignado IS 'Técnico de soporte asignado por el Administrador del sistema.';


--
-- Name: COLUMN ticket.id_activo; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.ticket.id_activo IS 'Activo relacionado cuando el ticket corresponde a una falla o intervención física.';


--
-- Name: COLUMN ticket.id_prioridad; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.ticket.id_prioridad IS 'El SLA aplicable se obtiene a través de prioridad_ticket -> sla, evitando duplicidad.';


--
-- Name: ticket_id_ticket_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.ticket_id_ticket_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ticket_id_ticket_seq OWNER TO siget_dev;

--
-- Name: ticket_id_ticket_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.ticket_id_ticket_seq OWNED BY public.ticket.id_ticket;


--
-- Name: ubicacion; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.ubicacion (
    id_ubicacion integer NOT NULL,
    nombre_area character varying(100) NOT NULL,
    edificio character varying(50),
    piso character varying(20)
);


ALTER TABLE public.ubicacion OWNER TO siget_dev;

--
-- Name: TABLE ubicacion; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.ubicacion IS 'Ubicaciones físicas, áreas, dependencias o bodegas donde se encuentran activos.';


--
-- Name: ubicacion_id_ubicacion_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.ubicacion_id_ubicacion_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ubicacion_id_ubicacion_seq OWNER TO siget_dev;

--
-- Name: ubicacion_id_ubicacion_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.ubicacion_id_ubicacion_seq OWNED BY public.ubicacion.id_ubicacion;


--
-- Name: usuario; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.usuario (
    id_usuario integer NOT NULL,
    identificador_externo character varying(255) NOT NULL,
    proveedor_identidad character varying(100) NOT NULL,
    rut character varying(12) NOT NULL,
    nombres character varying(100) NOT NULL,
    apellidos character varying(100) NOT NULL,
    correo character varying(150) NOT NULL,
    activo boolean DEFAULT true NOT NULL,
    fecha_creacion timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


ALTER TABLE public.usuario OWNER TO siget_dev;

--
-- Name: TABLE usuario; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.usuario IS 'Directorio local de usuarios de SIGET vinculado a un proveedor externo de identidad.';


--
-- Name: COLUMN usuario.identificador_externo; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.usuario.identificador_externo IS 'Identificador único entregado por el proveedor externo de identidad.';


--
-- Name: COLUMN usuario.proveedor_identidad; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.usuario.proveedor_identidad IS 'Nombre lógico del proveedor de identidad integrado.';


--
-- Name: COLUMN usuario.rut; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.usuario.rut IS 'Identificador institucional utilizado para trazabilidad y documentación.';


--
-- Name: COLUMN usuario.correo; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.usuario.correo IS 'Correo del usuario; no constituye una contraseña ni una credencial almacenada por SIGET.';


--
-- Name: COLUMN usuario.activo; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON COLUMN public.usuario.activo IS 'Indica si el perfil local está habilitado para operar en SIGET.';


--
-- Name: usuario_id_usuario_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.usuario_id_usuario_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.usuario_id_usuario_seq OWNER TO siget_dev;

--
-- Name: usuario_id_usuario_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.usuario_id_usuario_seq OWNED BY public.usuario.id_usuario;


--
-- Name: usuario_rol; Type: TABLE; Schema: public; Owner: siget_dev
--

CREATE TABLE public.usuario_rol (
    id_usuario_rol integer NOT NULL,
    id_usuario integer NOT NULL,
    id_rol integer NOT NULL,
    fecha_asignacion timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


ALTER TABLE public.usuario_rol OWNER TO siget_dev;

--
-- Name: TABLE usuario_rol; Type: COMMENT; Schema: public; Owner: siget_dev
--

COMMENT ON TABLE public.usuario_rol IS 'Relación N:M entre usuarios y roles RBAC.';


--
-- Name: usuario_rol_id_usuario_rol_seq; Type: SEQUENCE; Schema: public; Owner: siget_dev
--

CREATE SEQUENCE public.usuario_rol_id_usuario_rol_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.usuario_rol_id_usuario_rol_seq OWNER TO siget_dev;

--
-- Name: usuario_rol_id_usuario_rol_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: siget_dev
--

ALTER SEQUENCE public.usuario_rol_id_usuario_rol_seq OWNED BY public.usuario_rol.id_usuario_rol;


--
-- Name: activo id_activo; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.activo ALTER COLUMN id_activo SET DEFAULT nextval('public.activo_id_activo_seq'::regclass);


--
-- Name: adjunto_ticket id_adjunto; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.adjunto_ticket ALTER COLUMN id_adjunto SET DEFAULT nextval('public.adjunto_ticket_id_adjunto_seq'::regclass);


--
-- Name: asignacion id_asignacion; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.asignacion ALTER COLUMN id_asignacion SET DEFAULT nextval('public.asignacion_id_asignacion_seq'::regclass);


--
-- Name: bitacora_auditoria id_auditoria; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.bitacora_auditoria ALTER COLUMN id_auditoria SET DEFAULT nextval('public.bitacora_auditoria_id_auditoria_seq'::regclass);


--
-- Name: categoria_activo id_categoria; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.categoria_activo ALTER COLUMN id_categoria SET DEFAULT nextval('public.categoria_activo_id_categoria_seq'::regclass);


--
-- Name: codigo_qr id_qr; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.codigo_qr ALTER COLUMN id_qr SET DEFAULT nextval('public.codigo_qr_id_qr_seq'::regclass);


--
-- Name: comentario_ticket id_comentario; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.comentario_ticket ALTER COLUMN id_comentario SET DEFAULT nextval('public.comentario_ticket_id_comentario_seq'::regclass);


--
-- Name: devolucion_activo id_devolucion; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.devolucion_activo ALTER COLUMN id_devolucion SET DEFAULT nextval('public.devolucion_activo_id_devolucion_seq'::regclass);


--
-- Name: diagnostico id_diagnostico; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.diagnostico ALTER COLUMN id_diagnostico SET DEFAULT nextval('public.diagnostico_id_diagnostico_seq'::regclass);


--
-- Name: estado_activo id_estado_activo; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.estado_activo ALTER COLUMN id_estado_activo SET DEFAULT nextval('public.estado_activo_id_estado_activo_seq'::regclass);


--
-- Name: estado_asignacion id_estado_asignacion; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.estado_asignacion ALTER COLUMN id_estado_asignacion SET DEFAULT nextval('public.estado_asignacion_id_estado_asignacion_seq'::regclass);


--
-- Name: estado_orden_trabajo id_estado_ot; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.estado_orden_trabajo ALTER COLUMN id_estado_ot SET DEFAULT nextval('public.estado_orden_trabajo_id_estado_ot_seq'::regclass);


--
-- Name: estado_solicitud_asignacion id_estado_solicitud; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.estado_solicitud_asignacion ALTER COLUMN id_estado_solicitud SET DEFAULT nextval('public.estado_solicitud_asignacion_id_estado_solicitud_seq'::regclass);


--
-- Name: estado_ticket id_estado_ticket; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.estado_ticket ALTER COLUMN id_estado_ticket SET DEFAULT nextval('public.estado_ticket_id_estado_ticket_seq'::regclass);


--
-- Name: evaluacion_csat id_evaluacion; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.evaluacion_csat ALTER COLUMN id_evaluacion SET DEFAULT nextval('public.evaluacion_csat_id_evaluacion_seq'::regclass);


--
-- Name: historial_estado_activo id_historial_estado; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.historial_estado_activo ALTER COLUMN id_historial_estado SET DEFAULT nextval('public.historial_estado_activo_id_historial_estado_seq'::regclass);


--
-- Name: intervencion id_intervencion; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.intervencion ALTER COLUMN id_intervencion SET DEFAULT nextval('public.intervencion_id_intervencion_seq'::regclass);


--
-- Name: marca id_marca; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.marca ALTER COLUMN id_marca SET DEFAULT nextval('public.marca_id_marca_seq'::regclass);


--
-- Name: modelo_activo id_modelo; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.modelo_activo ALTER COLUMN id_modelo SET DEFAULT nextval('public.modelo_activo_id_modelo_seq'::regclass);


--
-- Name: movimiento_repuesto id_movimiento; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.movimiento_repuesto ALTER COLUMN id_movimiento SET DEFAULT nextval('public.movimiento_repuesto_id_movimiento_seq'::regclass);


--
-- Name: notificacion id_notificacion; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.notificacion ALTER COLUMN id_notificacion SET DEFAULT nextval('public.notificacion_id_notificacion_seq'::regclass);


--
-- Name: orden_repuesto id_orden_repuesto; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.orden_repuesto ALTER COLUMN id_orden_repuesto SET DEFAULT nextval('public.orden_repuesto_id_orden_repuesto_seq'::regclass);


--
-- Name: orden_trabajo id_orden; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.orden_trabajo ALTER COLUMN id_orden SET DEFAULT nextval('public.orden_trabajo_id_orden_seq'::regclass);


--
-- Name: permiso id_permiso; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.permiso ALTER COLUMN id_permiso SET DEFAULT nextval('public.permiso_id_permiso_seq'::regclass);


--
-- Name: prioridad_ticket id_prioridad; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.prioridad_ticket ALTER COLUMN id_prioridad SET DEFAULT nextval('public.prioridad_ticket_id_prioridad_seq'::regclass);


--
-- Name: repuesto id_repuesto; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.repuesto ALTER COLUMN id_repuesto SET DEFAULT nextval('public.repuesto_id_repuesto_seq'::regclass);


--
-- Name: rol id_rol; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.rol ALTER COLUMN id_rol SET DEFAULT nextval('public.rol_id_rol_seq'::regclass);


--
-- Name: rol_permiso id_rol_permiso; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.rol_permiso ALTER COLUMN id_rol_permiso SET DEFAULT nextval('public.rol_permiso_id_rol_permiso_seq'::regclass);


--
-- Name: sla id_sla; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.sla ALTER COLUMN id_sla SET DEFAULT nextval('public.sla_id_sla_seq'::regclass);


--
-- Name: solicitud_asignacion id_solicitud; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.solicitud_asignacion ALTER COLUMN id_solicitud SET DEFAULT nextval('public.solicitud_asignacion_id_solicitud_seq'::regclass);


--
-- Name: ticket id_ticket; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.ticket ALTER COLUMN id_ticket SET DEFAULT nextval('public.ticket_id_ticket_seq'::regclass);


--
-- Name: ubicacion id_ubicacion; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.ubicacion ALTER COLUMN id_ubicacion SET DEFAULT nextval('public.ubicacion_id_ubicacion_seq'::regclass);


--
-- Name: usuario id_usuario; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.usuario ALTER COLUMN id_usuario SET DEFAULT nextval('public.usuario_id_usuario_seq'::regclass);


--
-- Name: usuario_rol id_usuario_rol; Type: DEFAULT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.usuario_rol ALTER COLUMN id_usuario_rol SET DEFAULT nextval('public.usuario_rol_id_usuario_rol_seq'::regclass);


--
-- Data for Name: activo; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.activo (id_activo, codigo_inventario, numero_serie, id_modelo, id_ubicacion, id_estado_activo, valor_adquisicion, fecha_compra, fecha_garantia, fecha_registro) FROM stdin;
2	INV-TEST-002	SN-TEST-002	2	1	2	0.00	\N	\N	2026-10-15 16:01:19.289324+00
4	INV-TEST-004	SN-TEST-004	7	2	4	0.00	\N	\N	2026-10-15 16:01:19.289324+00
5	INV-TEST-005	SN-TEST-005	9	1	5	0.00	\N	\N	2026-10-15 16:01:19.289324+00
3	INV-TEST-003	SN-TEST-003	3	3	4	0.00	\N	\N	2026-10-15 16:01:19.289324+00
1	INV-TEST-001	SN-TEST-001	1	2	3	0.00	\N	\N	2026-10-15 16:01:19.289324+00
6	ACT-0001	STL-20020202	10	3	3	40000.00	\N	\N	2026-10-21 23:54:54.372109+00
7	INV-QA-001	SN-QA-001	3	1	4	0.00	\N	\N	2026-10-21 23:58:40.002781+00
8	ACT-0002	SADÑKSADSAJDSA	8	1	3	12121221.00	\N	\N	2026-10-22 00:46:58.311758+00
\.


--
-- Data for Name: adjunto_ticket; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.adjunto_ticket (id_adjunto, id_ticket, nombre_archivo, ruta_archivo, tipo_mime, tamano_bytes, fecha_subida) FROM stdin;
\.


--
-- Data for Name: asignacion; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.asignacion (id_asignacion, id_solicitud, id_activo, id_tecnico_entrega, id_estado_asignacion, fecha_entrega, fecha_devolucion_prevista, fecha_finalizacion) FROM stdin;
1	1	1	1	2	2026-10-21 22:53:46.010057+00	2027-04-22 03:59:59+00	2026-10-21 23:13:36.862978+00
\.


--
-- Data for Name: bitacora_auditoria; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.bitacora_auditoria (id_auditoria, id_usuario, modulo, accion, entidad_afectada, id_registro_afectado, detalle_evento, direccion_ip, fecha_evento) FROM stdin;
1	1	USUARIOS	PRIMER_ADMIN	usuario	1	Bootstrap inicial: Primer Administrador 'di.alcaino@duocuc.cl' (RUT: 21636490-2) creado con rol 'Administrador del sistema' e identificador Auth0 'auth0|6ad11451afcad1dcde49322d'.	\N	2026-10-15 17:58:41.73856+00
2	1	SERVICE_DESK	TICKET_CREADO	ticket	1	Ticket TCK-0001 creado por di.alcaino@duocuc.cl. Prioridad: Medio. Activo: INV-TEST-003.	\N	2026-10-21 20:31:27.497363+00
3	1	USUARIOS	APROVISIONAR_USUARIO	usuario	2	Usuario 'c.morales@institucion.cl' (RUT: 12222222-5) aprovisionado con rol inicial 'Técnico de soporte' e identificador Auth0 'auth0|6ad9225130bc3afcc2d8b545'.	172.18.0.1	2026-10-21 20:36:32.822073+00
4	2	ORDENES_TRABAJO	OT_CREADA	orden_trabajo	1	Se creó la OT OT-0001 para el ticket TCK-0001. El activo permanece en revisión.	\N	2026-10-21 20:37:45.901075+00
5	2	ORDENES_TRABAJO	REPARACION_INICIADA	orden_trabajo	1	Se inició la reparación de la OT OT-0001. El activo INV-TEST-003 pasó a En reparación.	\N	2026-10-21 20:39:16.744833+00
6	1	RBAC	ASIGNAR_ROLES	usuario_rol	1	Roles asignados a di.alcaino@duocuc.cl: ['Técnico de soporte', 'Administrador del sistema'].	172.18.0.1	2026-10-21 21:30:42.830602+00
7	1	RBAC	ASIGNAR_ROLES	usuario_rol	1	Roles asignados a di.alcaino@duocuc.cl: ['Administrador del sistema'].	172.18.0.1	2026-10-21 21:31:43.813597+00
8	1	RBAC	ASIGNAR_ROLES	usuario_rol	1	Roles asignados a di.alcaino@duocuc.cl: ['Técnico de soporte', 'Administrador del sistema'].	172.18.0.1	2026-10-21 21:39:02.455977+00
9	1	RBAC	ASIGNAR_ROLES	usuario_rol	1	Roles asignados a di.alcaino@duocuc.cl: ['Usuario solicitante', 'Técnico de soporte', 'Administrador del sistema'].	172.18.0.1	2026-10-21 22:49:44.848214+00
10	1	ASIGNACIONES	SOLICITUD_CREADA	solicitud_asignacion	1	Solicitud #1 registrada por di.alcaino@duocuc.cl para categoría Notebook.	\N	2026-10-21 22:52:15.018733+00
11	1	ASIGNACIONES	SOLICITUD_APROBADA	solicitud_asignacion	1	Solicitud #1 aprobada por Administrador di.alcaino@duocuc.cl.	172.18.0.1	2026-10-21 22:53:20.398427+00
12	1	ASIGNACIONES	ENTREGA_REGISTRADA	asignacion	1	Entrega física registrada por Técnico di.alcaino@duocuc.cl. Activo INV-TEST-001 asignado a usuario ID 1.	172.18.0.1	2026-10-21 22:53:46.021729+00
13	1	SERVICE_DESK	TICKET_CREADO	ticket	2	Ticket TCK-0002 creado por di.alcaino@duocuc.cl. Prioridad: Medio. Activo: INV-TEST-001.	172.18.0.1	2026-10-21 23:13:36.930157+00
14	1	ASIGNACIONES	DEVOLUCION_REGISTRADA	devolucion_activo	1	Devolución #1 registrada por Técnico di.alcaino@duocuc.cl. Asignación #1 cerrada. Activo INV-TEST-001 pasó a estado 'En revisión' (Condición física: Con falla técnica). Ticket de soporte asociado: TCK-0002.	172.18.0.1	2026-10-21 23:13:36.935617+00
15	1	ORDENES_TRABAJO	OT_CREADA	orden_trabajo	2	Se creó la OT OT-0002 para el ticket TCK-0002. El activo permanece en revisión.	172.18.0.1	2026-10-21 23:49:19.727202+00
16	1	ORDENES_TRABAJO	REPARACION_INICIADA	orden_trabajo	2	Se inició la reparación de la OT OT-0002. El activo INV-TEST-001 pasó a En reparación.	172.18.0.1	2026-10-21 23:50:36.117455+00
17	1	ACTIVOS	ACTIVO_MODIFICADO	activo	1	ACTIVO_MODIFICADO: INV-TEST-001.	172.18.0.1	2026-10-21 23:53:02.159507+00
18	1	ACTIVOS	ACTIVO_CREADO	activo	6	ACTIVO_CREADO: ACT-0001.	172.18.0.1	2026-10-21 23:54:54.391163+00
19	1	ACTIVOS	ACTIVO_MODIFICADO	activo	6	ACTIVO_MODIFICADO: ACT-0001.	172.18.0.1	2026-10-21 23:55:06.476701+00
20	2	ORDENES_TRABAJO	OT_CREADA	orden_trabajo	3	Se creó la OT OT-0003 para el ticket TCK-QA-001. El activo permanece en revisión.	\N	2026-10-22 00:07:03.968521+00
21	2	ORDENES_TRABAJO	REPARACION_INICIADA	orden_trabajo	3	Se inició la reparación de la OT OT-0003. El activo INV-QA-001 pasó a En reparación.	\N	2026-10-22 00:07:29.943626+00
22	1	RBAC	ASIGNAR_ROLES	usuario_rol	1	Roles asignados a di.alcaino@duocuc.cl: ['Técnico de soporte', 'Administrador del sistema'].	172.18.0.1	2026-10-22 00:13:12.845696+00
23	1	RBAC	ASIGNAR_ROLES	usuario_rol	1	Roles asignados a di.alcaino@duocuc.cl: ['Administrador del sistema'].	172.18.0.1	2026-10-22 00:13:44.335731+00
24	1	RBAC	ASIGNAR_ROLES	usuario_rol	1	Roles asignados a di.alcaino@duocuc.cl: ['Técnico de soporte', 'Administrador del sistema'].	172.18.0.1	2026-10-22 00:17:13.82006+00
25	1	ACTIVOS	ACTIVO_CREADO	activo	8	ACTIVO_CREADO: ACT-0002.	172.18.0.1	2026-10-22 00:46:58.312877+00
26	1	ACTIVOS	ACTIVO_MODIFICADO	activo	8	ACTIVO_MODIFICADO: ACT-0002.	172.18.0.1	2026-10-22 00:47:11.553457+00
27	1	ORDENES_TRABAJO	OT_CREADA	orden_trabajo	4	Se creó la OT OT-0004 para el ticket . El activo permanece en revisión.	172.18.0.1	2026-10-22 00:53:17.044281+00
28	1	RBAC	ASIGNAR_ROLES	usuario_rol	1	Roles asignados a di.alcaino@duocuc.cl: ['Usuario solicitante', 'Técnico de soporte', 'Administrador del sistema'].	172.18.0.1	2026-10-23 00:48:11.62859+00
29	1	USUARIOS	APROVISIONAR_USUARIO	usuario	3	Usuario 'u.solicitante@empresa.cl' (RUT: 11111111-1) aprovisionado con rol inicial 'Usuario solicitante' e identificador Auth0 'auth0|6adabd5d1da8c18b84927efe'.	172.18.0.1	2026-10-23 01:50:20.065228+00
30	1	ORDENES_TRABAJO	OT_REASIGNADA	orden_trabajo	1	OT OT-0001 reasignada del técnico 2 al técnico 1. Observaciones: No existe tecnico	172.18.0.1	2026-10-23 18:42:41.886099+00
31	1	ORDENES_TRABAJO	OT_REASIGNADA	orden_trabajo	1	OT OT-0001 reasignada del técnico 1 al técnico 2. Observaciones: No existe tecnico asignado	172.18.0.1	2026-10-23 18:43:33.098413+00
32	1	ORDENES_TRABAJO	OT_PAUSADA	orden_trabajo	1	Se pausó la OT OT-0001. Motivo: AAAAAAA	172.18.0.1	2026-10-23 18:43:49.138008+00
33	1	ORDENES_TRABAJO	OT_REANUDADA	orden_trabajo	1	Se reanudó la OT OT-0001. Motivo de pausa anterior: AAAAAAA	172.18.0.1	2026-10-23 18:43:52.796573+00
34	1	ORDENES_TRABAJO	OT_PAUSADA	orden_trabajo	2	Se pausó la OT OT-0002. Motivo: aaa	172.18.0.1	2026-10-23 18:47:23.072144+00
35	1	ORDENES_TRABAJO	OT_PAUSADA	orden_trabajo	1	Se pausó la OT OT-0001. Motivo: Prueba numero 2	172.18.0.1	2026-10-23 18:49:16.924218+00
36	1	ORDENES_TRABAJO	OT_PAUSADA	orden_trabajo	4	Se pausó la OT OT-0004. Motivo: Prueba número 3	172.18.0.1	2026-10-23 18:57:35.780967+00
37	1	ORDENES_TRABAJO	OT_REANUDADA	orden_trabajo	2	Se reanudó la OT OT-0002. Motivo de pausa anterior: aaa	172.18.0.1	2026-10-23 18:58:27.168051+00
38	1	ORDENES_TRABAJO	OT_REASIGNADA	orden_trabajo	2	OT OT-0002 reasignada del técnico 1 al técnico 1. Observaciones: No tiene tecnico asignado	172.18.0.1	2026-10-23 18:58:45.585943+00
39	1	ORDENES_TRABAJO	OT_REANUDADA	orden_trabajo	4	Se reanudó la OT OT-0004. Motivo de pausa anterior: Prueba número 3	172.18.0.1	2026-10-23 18:59:08.599228+00
40	1	ORDENES_TRABAJO	OT_REANUDADA	orden_trabajo	1	Se reanudó la OT OT-0001. Motivo de pausa anterior: Prueba numero 2	172.18.0.1	2026-10-23 18:59:14.898783+00
41	1	ORDENES_TRABAJO	OT_REASIGNADA	orden_trabajo	4	OT OT-0004 reasignada del técnico 1 al técnico 2. Observaciones: No existe tecnico	172.18.0.1	2026-10-23 19:15:25.920148+00
42	1	ORDENES_TRABAJO	OT_REASIGNADA	orden_trabajo	1	OT OT-0001 reasignada del técnico 2 al técnico 2. Observaciones: ASDSAKÑDSAKDSA	172.18.0.1	2026-10-23 19:16:23.679627+00
43	1	ORDENES_TRABAJO	OT_REASIGNADA	orden_trabajo	1	OT OT-0001 reasignada del técnico 2 al técnico 1. Observaciones: aaa	172.18.0.1	2026-10-23 19:26:18.238914+00
44	1	ORDENES_TRABAJO	OT_REASIGNADA	orden_trabajo	1	OT OT-0001 reasignada del técnico 1 al técnico 2. Observaciones: asdsadasdsadsa	172.18.0.1	2026-10-23 19:26:33.328219+00
45	1	ORDENES_TRABAJO	OT_REASIGNADA	orden_trabajo	4	Orden de trabajo: OT-0004\nAcción: Reasignación de técnico\nTécnico anterior: Carlos Andres Morales Vega\nTécnico nuevo: Carlos Andres Morales Vega\nObservaciones: Prueba número 5	172.18.0.1	2026-10-23 20:26:03.046591+00
46	1	ORDENES_TRABAJO	OT_PAUSADA	orden_trabajo	3	Se pausó la OT OT-0003. Motivo: ADSA[KLDSDSA	172.18.0.1	2026-10-23 20:28:33.915321+00
47	1	ORDENES_TRABAJO	OT_PAUSADA	orden_trabajo	4	Se pausó la OT OT-0004. Motivo: ASDLJSADSAJDSAJDSA	172.18.0.1	2026-10-23 20:28:51.711629+00
48	1	ORDENES_TRABAJO	OT_PAUSADA	orden_trabajo	1	Se pausó la OT OT-0001. Motivo: sadsadsadsadsadsa	172.18.0.1	2026-10-23 20:29:31.45348+00
49	1	ORDENES_TRABAJO	OT_PAUSADA	orden_trabajo	2	Se pausó la OT OT-0002. Motivo: No se puede	172.18.0.1	2026-10-23 20:30:16.819676+00
50	1	ORDENES_TRABAJO	OT_REANUDADA	orden_trabajo	3	Se reanudó la OT OT-0003. Motivo de pausa anterior: ADSA[KLDSDSA	172.18.0.1	2026-10-23 20:32:04.026857+00
51	1	ORDENES_TRABAJO	OT_PAUSADA	orden_trabajo	3	Se pausó la OT OT-0003. Motivo: adiñlusadhsaoihdsa	172.18.0.1	2026-10-23 20:32:11.263552+00
52	1	ORDENES_TRABAJO	OT_REASIGNADA	orden_trabajo	3	Orden de trabajo: OT-0003\nAcción: Reasignación de técnico\nTécnico anterior: Carlos Andres Morales Vega\nTécnico nuevo: Carlos Andres Morales Vega\nObservaciones: Perdi la cuenta de las pruebas	172.18.0.1	2026-10-23 20:32:25.709365+00
53	1	ORDENES_TRABAJO	OT_REANUDADA	orden_trabajo	1	Se reanudó la OT OT-0001. Motivo de pausa anterior: sadsadsadsadsadsa	172.18.0.1	2026-10-23 20:33:11.595765+00
54	1	ORDENES_TRABAJO	OT_REANUDADA	orden_trabajo	2	Se reanudó la OT OT-0002. Motivo de pausa anterior: No se puede	172.18.0.1	2026-10-23 20:33:15.487418+00
55	1	ORDENES_TRABAJO	OT_REANUDADA	orden_trabajo	3	Se reanudó la OT OT-0003. Motivo de pausa anterior: adiñlusadhsaoihdsa	172.18.0.1	2026-10-23 20:33:18.034564+00
56	1	ORDENES_TRABAJO	OT_REANUDADA	orden_trabajo	4	Se reanudó la OT OT-0004. Motivo de pausa anterior: ASDLJSADSAJDSAJDSA	172.18.0.1	2026-10-23 20:33:20.910782+00
57	1	ORDENES_TRABAJO	OT_PAUSADA	orden_trabajo	3	Se pausó la OT OT-0003. Motivo: asadsadsa	172.18.0.1	2026-10-23 20:33:32.874367+00
58	1	REPUESTOS	INGRESO_COMPRA	repuesto	1	Ingreso de compra del repuesto REP-0001. Cantidad ingresada: 5. Costo unitario de compra: 15000.00. Stock resultante: 5. Movimiento registrado: 1.	\N	2026-10-26 16:38:18.243597+00
59	1	REPUESTOS	INGRESO_COMPRA	repuesto	1	Ingreso de compra del repuesto REP-0001. Cantidad ingresada: 3. Costo unitario de compra: 18000.00. Stock resultante: 8. Movimiento registrado: 2.	\N	2026-10-26 16:39:36.398674+00
60	1	REPUESTOS	ACTUALIZAR_STOCK_MINIMO	repuesto	1	Actualización del stock mínimo del repuesto REP-0001. Mínimo anterior: 5. Nuevo mínimo: 3. Stock actual: 8.	\N	2026-10-26 19:14:28.628893+00
61	1	REPUESTOS	ACTUALIZAR_STOCK_MINIMO	repuesto	1	Actualización del stock mínimo del repuesto REP-0001. Mínimo anterior: 3. Nuevo mínimo: 10. Stock actual: 8.	\N	2026-10-26 19:14:34.113464+00
62	1	REPUESTOS	ACTUALIZAR_STOCK_MINIMO	repuesto	1	Actualización del stock mínimo del repuesto REP-0001. Mínimo anterior: 10. Nuevo mínimo: 5. Stock actual: 8.	\N	2026-10-26 19:14:49.215591+00
63	1	REPUESTOS	ACTUALIZAR_STOCK_MINIMO	repuesto	1	Actualización del stock mínimo del repuesto REP-0001. Mínimo anterior: 5. Nuevo mínimo: 2. Stock actual: 8.	\N	2026-10-26 19:26:57.543185+00
64	1	REPUESTOS	ACTUALIZAR_STOCK_MINIMO	repuesto	1	Actualización del stock mínimo del repuesto REP-0001. Mínimo anterior: 2. Nuevo mínimo: 10. Stock actual: 8.	\N	2026-10-26 19:27:13.666026+00
65	1	REPUESTOS	INGRESO_COMPRA	repuesto	2	Ingreso de compra del repuesto REP-0002. Cantidad ingresada: 3. Costo unitario de compra: 28990.00. Stock resultante: 3. Movimiento registrado: 3.	\N	2026-10-26 19:28:17.681673+00
66	1	REPUESTOS	ACTUALIZAR_STOCK_MINIMO	repuesto	2	Actualización del stock mínimo del repuesto REP-0002. Mínimo anterior: 1. Nuevo mínimo: 4. Stock actual: 3.	\N	2026-10-26 19:28:34.032716+00
67	1	REPUESTOS	INGRESO_COMPRA	repuesto	3	Ingreso de compra del repuesto REP-0003. Cantidad ingresada: 2. Costo unitario de compra: 35990.00. Stock resultante: 2. Movimiento registrado: 4.	\N	2026-10-26 19:29:18.797903+00
68	1	REPUESTOS	INGRESO_COMPRA	repuesto	4	Ingreso de compra del repuesto REP-0004. Cantidad ingresada: 2. Costo unitario de compra: 12000.00. Stock resultante: 2. Movimiento registrado: 5.	\N	2026-10-26 19:43:48.631275+00
69	1	REPUESTOS	ACTUALIZAR_STOCK_MINIMO	repuesto	4	Actualización del stock mínimo del repuesto REP-0004. Mínimo anterior: 5. Nuevo mínimo: 4. Stock actual: 2.	\N	2026-10-26 19:44:22.103808+00
70	1	REPUESTOS	INGRESO_COMPRA	repuesto	4	Ingreso de compra del repuesto REP-0004. Cantidad ingresada: 10. Costo unitario de compra: 13000.00. Stock resultante: 12. Movimiento registrado: 6.	\N	2026-10-26 19:44:37.960066+00
71	1	REPUESTOS	ACTUALIZAR_STOCK_MINIMO	repuesto	4	Actualización del stock mínimo del repuesto REP-0004. Mínimo anterior: 4. Nuevo mínimo: 20. Stock actual: 12.	\N	2026-10-26 19:45:01.623314+00
73	1	REPUESTOS	AJUSTAR_STOCK	repuesto	1	Ajuste de stock de REP-0001. DISMINUCION. Stock anterior: 8. Nuevo stock: 5. Motivo: Error al ingresar la cantidad de memoria RAM DDR4. Movimiento: 8.	\N	2026-10-26 20:06:28.891758+00
76	1	REPUESTOS	DAR_BAJA_REPUESTO	repuesto	3	Baja del repuesto REP-0003 (Batería para notebook HP). Estado anterior: Activo. Estado nuevo: Inactivo. Motivo: Repuesto descontinuado para prueba.	\N	2026-10-26 21:04:59.91727+00
77	1	REPUESTOS	REACTIVAR_REPUESTO	repuesto	3	Reactivación del repuesto REP-0003 (Batería para notebook HP). Estado anterior: Inactivo. Estado nuevo: Activo. Motivo: Reactivacion de prueba.	\N	2026-10-26 21:05:37.120653+00
78	1	REPUESTOS	ACTUALIZAR_STOCK_MINIMO	repuesto	4	Actualización del stock mínimo del repuesto REP-0004. Mínimo anterior: 20. Nuevo mínimo: 5. Stock actual: 12.	\N	2026-10-26 21:06:59.883075+00
\.


--
-- Data for Name: categoria_activo; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.categoria_activo (id_categoria, nombre, descripcion) FROM stdin;
1	Notebook	Equipo portátil
2	PC Desktop	Equipo de escritorio
3	Proyector	Equipo de proyección audiovisual
4	Impresora	Equipo de impresión
5	Monitor	Pantalla o monitor externo
\.


--
-- Data for Name: codigo_qr; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.codigo_qr (id_qr, id_activo, payload_qr, formato_imagen, fecha_generacion, veces_reimpreso) FROM stdin;
\.


--
-- Data for Name: comentario_ticket; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.comentario_ticket (id_comentario, id_ticket, id_usuario, mensaje, fecha_registro) FROM stdin;
\.


--
-- Data for Name: devolucion_activo; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.devolucion_activo (id_devolucion, id_asignacion, id_tecnico_receptor, id_estado_activo_resultante, fecha_devolucion, condicion_fisica, motivo_devolucion, observaciones) FROM stdin;
1	1	1	3	2026-10-21 23:13:36.931303+00	Con falla técnica	Problemas de hardware	Disco duro fallando
\.


--
-- Data for Name: diagnostico; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.diagnostico (id_diagnostico, id_orden, id_tecnico, descripcion_falla, procedimiento_inicial, es_reparable, fecha_diagnostico) FROM stdin;
1	1	2	Prueba de diagnóstico: equipo no enciende correctamente.	Inspeccionar alimentación eléctrica, cargador y batería; realizar pruebas de encendido.	t	2026-10-21 20:37:45.852156+00
2	2	1	Problema con el hardware	Realizar reparacion total del hardware	t	2026-10-21 23:49:19.722624+00
3	3	2	Prueba QA: equipo presenta una falla de funcionamiento.	Inspección visual y diagnóstico inicial del equipo.	t	2026-10-22 00:07:03.965844+00
4	4	1	asdsadsadasdsa	dasdasdasdasdsa	f	2026-10-22 00:53:17.041737+00
\.


--
-- Data for Name: django_migrations; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.django_migrations (id, app, name, applied) FROM stdin;
1	sessions	0001_initial	2026-10-15 17:46:06.206588+00
\.


--
-- Data for Name: django_session; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.django_session (session_key, session_data, expire_date) FROM stdin;
s4z0i9phr7dwqrafi0v5yvjkvpdb96bq	.eJx9UW1r2zAQ_itBUH9p8HvSxGBax53ZoOsgZKzbKEaRLomobNl6WdN2_e87u13phzGQ0OnuubvnnnsitbHUQk2dPYT11_nH6qqnKSzKL2Kh-0O_uoKKJ324_lQuSPZEOLV0eDVwoYHZ2mlBMnKwtsuCQCpG5UEZmy3CMAyGogF65Jayu4BMSataBgjXn6_7445X1_YHu-nTyJlvDYadlq-1DBYzYg_Wd8YfuflMNWNBpcUjnGswnWoN1Pahg5wpDh6TAlpbC54XD99Lu57p5Gx1v1lVx826LDb7-Y370HFadlvvPft86HeSFCdxhedtAvQMM6BraIrP3znQ9AxT2BVvK_hpp9VOSDiFhgrpjXLm_xfSG3XI_6nC85TAsSNZdLaMw2UYprEfR0mSzmYYGSWpnXFUC4WTImxKXlZn3Ba1G-3fc8qjKJ1FdMfQ4oxDukzimA8Sv-YypTUozODCp5JR0aoL7hRzzGfyHa5VzVYPK7sUsFeT4gWKAK0kGJL9JAVvRCuM1ZQrPeEgJwZ_KAa5nRLU5hcABpAsLkdwipxJMbAkz38Aw6DZCw:1xHPlp:r453t3SZs4_CbLMibjcTEJAD4aSAlHw8XrPgLqCjdow	2026-10-29 18:01:37.403601+00
0h9cjy562i41nnmmy432l7quabcpyzv9	.eJxNj8FOw0AMRH8l8jmqklKQmhOR-glwAhS5timWNuvKu8sF-HcMERK3Gb03h_mAohepSysNXW1RhmnsAVt9G5bSzjBt-fMOeRwPtyO-UiQmlsPxZr9n6OFvS-YuFgvWHSZCzXbPzajRjtI_L9t6dgnvpHKxbt7UENySFJie4HEzu2JJSSvmKoEfntswyJGyknUsQa_mv2TmVbOW6sjmgVJXosmK8NLD1e1dJECck1yVMT7C_PMKvr4BVTFZIg:1xK4DC:sfjw_LkAom8QbleJth53f9R9oIGJsbYyArVFPD_RMnc	2026-11-06 01:36:50.605626+00
wqzvgvj5l0bjz6jgcxzesucaz7ibqn6j	.eJxtj80KwjAQhF9F9lyK9bf2pM8gnkTKJrtqoO2WTeJFfXcjRe3B2zDMx8zcwbsLhzr6iOqkdgTVPAOM4TqtfTRQDfqxQkJDSyoIS1uUplxsZms-M2TwYa2osiQi5l4aZ13ALvCW217ZY26bUbaT1iin7GEwJvsfMfnjJVSlYQ_V8YuMSuCUQa9yYybRdIK74AjTF9i918PzBVNbUtM:1xK4gM:11c8BtzeTHqBhYd_cU4eVx5XgpOqvqHYSW2jKOyyI9I	2026-11-06 02:06:58.081414+00
\.


--
-- Data for Name: estado_activo; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.estado_activo (id_estado_activo, nombre, descripcion) FROM stdin;
1	Disponible	Activo operativo y habilitado para una nueva asignación
2	Asignado	Activo entregado y actualmente asignado a un Usuario solicitante
3	En revisión	Activo bloqueado para asignaciones mientras se realiza evaluación técnica
4	En reparación	Activo con una orden de trabajo en intervención técnica
5	Dado de baja	Activo desincorporado y no habilitado para nuevas asignaciones
\.


--
-- Data for Name: estado_asignacion; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.estado_asignacion (id_estado_asignacion, nombre, descripcion) FROM stdin;
1	Activa	Activo entregado y actualmente asignado al Usuario solicitante
2	Finalizada	Asignación cerrada mediante una devolución registrada
\.


--
-- Data for Name: estado_orden_trabajo; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.estado_orden_trabajo (id_estado_ot, nombre, descripcion) FROM stdin;
1	En Diagnóstico	Orden abierta para evaluación técnica y diagnóstico inicial
2	En Reparación	Intervención técnica activa sobre el equipo
3	Pausada	Orden temporalmente pausada, por ejemplo por espera de repuestos
4	Completada	Intervención técnica concluida y resultado registrado
\.


--
-- Data for Name: estado_solicitud_asignacion; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.estado_solicitud_asignacion (id_estado_solicitud, nombre, descripcion) FROM stdin;
1	Pendiente	Solicitud en espera de evaluación administrativa
2	Aprobada	Solicitud aprobada; pendiente de entrega de un activo compatible
3	Rechazada	Solicitud rechazada por el Administrador del sistema
4	Atendida	Solicitud materializada mediante una asignación
\.


--
-- Data for Name: estado_ticket; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.estado_ticket (id_estado_ticket, nombre, descripcion) FROM stdin;
1	Abierto	Ticket registrado y pendiente de asignación o atención
2	En Proceso	Ticket actualmente atendido por un Técnico de soporte
3	En Espera	Ticket temporalmente en espera de información o una condición externa
4	Resuelto	Atención técnica finalizada y solución registrada
5	Cerrado	Ticket cerrado para operación normal y disponible para evaluación CSAT
\.


--
-- Data for Name: evaluacion_csat; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.evaluacion_csat (id_evaluacion, id_ticket, id_usuario, calificacion_estrellas, comentario, fecha_evaluacion) FROM stdin;
\.


--
-- Data for Name: historial_estado_activo; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.historial_estado_activo (id_historial_estado, id_activo, id_estado_activo, id_usuario, fecha_cambio, observacion) FROM stdin;
1	3	4	2	2026-10-21 20:39:16.63505+00	Activo enviado a reparación mediante la OT OT-0001.
2	1	3	1	2026-10-21 23:13:36.931303+00	Devolución de la asignación 1. Condición física: Con falla técnica. Evaluación inicial E4-H11: En revisión.
3	1	4	1	2026-10-21 23:50:36.114097+00	Activo enviado a reparación mediante la OT OT-0002.
4	7	3	2	2026-10-22 00:07:03.934107+00	Preparación de prueba QA para TCK-QA-001 antes de crear la OT.
5	7	4	2	2026-10-22 00:07:29.941558+00	Activo enviado a reparación mediante la OT OT-0003.
\.


--
-- Data for Name: intervencion; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.intervencion (id_intervencion, id_orden, id_tecnico, descripcion_accion, resultado_prueba, fecha_intervencion) FROM stdin;
\.


--
-- Data for Name: marca; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.marca (id_marca, nombre) FROM stdin;
1	Dell
2	HP
3	Lenovo
4	Epson
5	Samsung
\.


--
-- Data for Name: modelo_activo; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.modelo_activo (id_modelo, id_marca, id_categoria, nombre) FROM stdin;
1	1	1	Latitude 5520
2	2	1	ProBook 450
3	3	1	ThinkPad E14
4	1	2	OptiPlex 7090
5	2	2	ProDesk 400
6	3	2	ThinkCentre M70
7	4	3	PowerLite X49
8	2	4	LaserJet Pro
9	5	5	S24R350
10	5	5	ViewFinity S24
\.


--
-- Data for Name: movimiento_repuesto; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.movimiento_repuesto (id_movimiento, id_repuesto, id_usuario, tipo_movimiento, cantidad, costo_unitario, motivo, fecha_movimiento) FROM stdin;
1	1	1	INGRESO_COMPRA	5	15000.00	Ingreso de repuestos al inventario	2026-10-26 16:38:18.241223+00
2	1	1	INGRESO_COMPRA	3	18000.00	Ingreso de repuestos al inventario	2026-10-26 16:39:36.39801+00
3	2	1	INGRESO_COMPRA	3	28990.00	Ingreso de repuestos al inventario	2026-10-26 19:28:17.680542+00
4	3	1	INGRESO_COMPRA	2	35990.00	Ingreso de repuestos al inventario	2026-10-26 19:29:18.797128+00
5	4	1	INGRESO_COMPRA	2	12000.00	Ingreso de repuestos al inventario	2026-10-26 19:43:48.630393+00
6	4	1	INGRESO_COMPRA	10	13000.00	Ingreso de repuestos al inventario	2026-10-26 19:44:37.959069+00
8	1	1	AJUSTE_INVENTARIO	3	16125.00	DISMINUCION. Stock anterior: 8. Nuevo stock: 5. Motivo: Error al ingresar la cantidad de memoria RAM DDR4	2026-10-26 20:06:28.890746+00
\.


--
-- Data for Name: notificacion; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.notificacion (id_notificacion, id_usuario, modulo_origen, titulo, mensaje, canal, leida, estado_envio, intentos_envio, ultimo_error, fecha_creacion, fecha_ultimo_intento, fecha_envio, clave_evento, datos_envio, referencia, id_proveedor, reintento_permitido, proximo_intento, fecha_primer_intento) FROM stdin;
1	1	SERVICE_DESK	Orden de trabajo reasignada: OT-0001	Se te ha asignado la orden de trabajo OT-0001.\nObservaciones: No existe tecnico	AMBOS	f	ERROR	1	Falta configurar RESEND_API_KEY.	2026-10-23 18:42:41.931685+00	2026-10-23 18:43:19.800663+00	\N	7dbe03fcb62d1a46ee9d9791597bc5c3eb927b5b5f4f378b0a3a5711855cf1a7	{"to": ["di.alcaino@duocuc.cl"], "from": "", "html": "<!doctype html>\\n<html lang=\\"es\\"><head><meta charset=\\"utf-8\\"><title>Orden de trabajo reasignada: OT-0001</title></head>\\n<body style=\\"font-family:Arial,sans-serif;color:#172033;line-height:1.6\\">\\n<h1 style=\\"font-size:22px\\">Orden de trabajo reasignada: OT-0001</h1>\\n<p>Hola Diego,</p>\\n<div>Se te ha asignado la orden de trabajo OT-0001.<br>Observaciones: No existe tecnico</div>\\n\\n<hr><p>SIGET — Sistema Integral de Gestión de Equipos y Soporte Tecnológico<br>\\nEste es un aviso automático. No respondas a este remitente.</p>\\n</body></html>\\n", "text": "Hola Diego,\\n\\nSe te ha asignado la orden de trabajo OT-0001.\\nObservaciones: No existe tecnico\\n\\nSIGET — Sistema Integral de Gestión de Equipos y Soporte Tecnológico\\nEste es un aviso automático. No respondas a este remitente.\\n", "subject": "Orden de trabajo reasignada: OT-0001"}	{"codigo_ot": "OT-0001", "orden_trabajo": 1, "tecnico_anterior": 2}	\N	f	2026-10-23 18:44:19.960787+00	2026-10-23 18:43:19.800663+00
2	2	SERVICE_DESK	Orden de trabajo reasignada: OT-0001	Se te ha asignado la orden de trabajo OT-0001.\nObservaciones: No existe tecnico asignado	AMBOS	f	ERROR	1	Falta configurar RESEND_API_KEY.	2026-10-23 18:43:33.100403+00	2026-10-23 18:44:20.034377+00	\N	94d9172c850fa30895e963281a029200a096dd4692c7231cfcb8a2cd84d9e2e8	{"to": ["c.morales@institucion.cl"], "from": "", "html": "<!doctype html>\\n<html lang=\\"es\\"><head><meta charset=\\"utf-8\\"><title>Orden de trabajo reasignada: OT-0001</title></head>\\n<body style=\\"font-family:Arial,sans-serif;color:#172033;line-height:1.6\\">\\n<h1 style=\\"font-size:22px\\">Orden de trabajo reasignada: OT-0001</h1>\\n<p>Hola Carlos Andres,</p>\\n<div>Se te ha asignado la orden de trabajo OT-0001.<br>Observaciones: No existe tecnico asignado</div>\\n\\n<hr><p>SIGET — Sistema Integral de Gestión de Equipos y Soporte Tecnológico<br>\\nEste es un aviso automático. No respondas a este remitente.</p>\\n</body></html>\\n", "text": "Hola Carlos Andres,\\n\\nSe te ha asignado la orden de trabajo OT-0001.\\nObservaciones: No existe tecnico asignado\\n\\nSIGET — Sistema Integral de Gestión de Equipos y Soporte Tecnológico\\nEste es un aviso automático. No respondas a este remitente.\\n", "subject": "Orden de trabajo reasignada: OT-0001"}	{"codigo_ot": "OT-0001", "orden_trabajo": 1, "tecnico_anterior": 1}	\N	f	2026-10-23 18:45:20.088259+00	2026-10-23 18:44:20.034377+00
3	1	SERVICE_DESK	Orden de trabajo reasignada: OT-0002	Se te ha asignado la orden de trabajo OT-0002.\nObservaciones: No tiene tecnico asignado	AMBOS	f	ERROR	1	Falta configurar RESEND_API_KEY.	2026-10-23 18:58:45.607993+00	2026-10-23 18:59:20.265986+00	\N	7b1578b763db5cfcc28c74794791fd77746bf49836da9897fb8acad2229309af	{"to": ["di.alcaino@duocuc.cl"], "from": "", "html": "<!doctype html>\\n<html lang=\\"es\\"><head><meta charset=\\"utf-8\\"><title>Orden de trabajo reasignada: OT-0002</title></head>\\n<body style=\\"font-family:Arial,sans-serif;color:#172033;line-height:1.6\\">\\n<h1 style=\\"font-size:22px\\">Orden de trabajo reasignada: OT-0002</h1>\\n<p>Hola Diego,</p>\\n<div>Se te ha asignado la orden de trabajo OT-0002.<br>Observaciones: No tiene tecnico asignado</div>\\n\\n<hr><p>SIGET — Sistema Integral de Gestión de Equipos y Soporte Tecnológico<br>\\nEste es un aviso automático. No respondas a este remitente.</p>\\n</body></html>\\n", "text": "Hola Diego,\\n\\nSe te ha asignado la orden de trabajo OT-0002.\\nObservaciones: No tiene tecnico asignado\\n\\nSIGET — Sistema Integral de Gestión de Equipos y Soporte Tecnológico\\nEste es un aviso automático. No respondas a este remitente.\\n", "subject": "Orden de trabajo reasignada: OT-0002"}	{"codigo_ot": "OT-0002", "orden_trabajo": 2, "tecnico_anterior": 1}	\N	f	2026-10-23 19:00:20.320418+00	2026-10-23 18:59:20.265986+00
4	2	SERVICE_DESK	Orden de trabajo reasignada: OT-0004	Se te ha asignado la orden de trabajo OT-0004.\nObservaciones: No existe tecnico	AMBOS	f	ERROR	1	Falta configurar RESEND_API_KEY.	2026-10-23 19:15:25.943075+00	2026-10-23 19:16:21.861756+00	\N	1482142fd6d710f2b4f0a878f70158f30d95d3bfa7dc2b745e48fdd3adc04c8e	{"to": ["c.morales@institucion.cl"], "from": "", "html": "<!doctype html>\\n<html lang=\\"es\\"><head><meta charset=\\"utf-8\\"><title>Orden de trabajo reasignada: OT-0004</title></head>\\n<body style=\\"font-family:Arial,sans-serif;color:#172033;line-height:1.6\\">\\n<h1 style=\\"font-size:22px\\">Orden de trabajo reasignada: OT-0004</h1>\\n<p>Hola Carlos Andres,</p>\\n<div>Se te ha asignado la orden de trabajo OT-0004.<br>Observaciones: No existe tecnico</div>\\n\\n<hr><p>SIGET — Sistema Integral de Gestión de Equipos y Soporte Tecnológico<br>\\nEste es un aviso automático. No respondas a este remitente.</p>\\n</body></html>\\n", "text": "Hola Carlos Andres,\\n\\nSe te ha asignado la orden de trabajo OT-0004.\\nObservaciones: No existe tecnico\\n\\nSIGET — Sistema Integral de Gestión de Equipos y Soporte Tecnológico\\nEste es un aviso automático. No respondas a este remitente.\\n", "subject": "Orden de trabajo reasignada: OT-0004"}	{"codigo_ot": "OT-0004", "orden_trabajo": 4, "tecnico_anterior": 1}	\N	f	2026-10-23 19:17:21.960324+00	2026-10-23 19:16:21.861756+00
5	2	SERVICE_DESK	Orden de trabajo reasignada: OT-0001	Se te ha asignado la orden de trabajo OT-0001.\nObservaciones: ASDSAKÑDSAKDSA	AMBOS	f	ERROR	1	Falta configurar RESEND_API_KEY.	2026-10-23 19:16:23.681459+00	2026-10-23 19:17:22.014005+00	\N	bd50a075bdc5770ca99c10c744938e26ec9cb6171809ad1cfa43aa2045a346cc	{"to": ["c.morales@institucion.cl"], "from": "", "html": "<!doctype html>\\n<html lang=\\"es\\"><head><meta charset=\\"utf-8\\"><title>Orden de trabajo reasignada: OT-0001</title></head>\\n<body style=\\"font-family:Arial,sans-serif;color:#172033;line-height:1.6\\">\\n<h1 style=\\"font-size:22px\\">Orden de trabajo reasignada: OT-0001</h1>\\n<p>Hola Carlos Andres,</p>\\n<div>Se te ha asignado la orden de trabajo OT-0001.<br>Observaciones: ASDSAKÑDSAKDSA</div>\\n\\n<hr><p>SIGET — Sistema Integral de Gestión de Equipos y Soporte Tecnológico<br>\\nEste es un aviso automático. No respondas a este remitente.</p>\\n</body></html>\\n", "text": "Hola Carlos Andres,\\n\\nSe te ha asignado la orden de trabajo OT-0001.\\nObservaciones: ASDSAKÑDSAKDSA\\n\\nSIGET — Sistema Integral de Gestión de Equipos y Soporte Tecnológico\\nEste es un aviso automático. No respondas a este remitente.\\n", "subject": "Orden de trabajo reasignada: OT-0001"}	{"codigo_ot": "OT-0001", "orden_trabajo": 1, "tecnico_anterior": 2}	\N	f	2026-10-23 19:18:22.113025+00	2026-10-23 19:17:22.014005+00
6	1	SERVICE_DESK	Orden de trabajo reasignada: OT-0001	Se te ha asignado la orden de trabajo OT-0001.\nObservaciones: aaa	AMBOS	f	ERROR	1	Falta configurar RESEND_API_KEY.	2026-10-23 19:26:18.258362+00	2026-10-23 19:26:22.2218+00	\N	5f523b7b50b11f5c799e64dd6a522827f1830651dd20a613253bacd7ef4cb4db	{"to": ["di.alcaino@duocuc.cl"], "from": "", "html": "<!doctype html>\\n<html lang=\\"es\\"><head><meta charset=\\"utf-8\\"><title>Orden de trabajo reasignada: OT-0001</title></head>\\n<body style=\\"font-family:Arial,sans-serif;color:#172033;line-height:1.6\\">\\n<h1 style=\\"font-size:22px\\">Orden de trabajo reasignada: OT-0001</h1>\\n<p>Hola Diego,</p>\\n<div>Se te ha asignado la orden de trabajo OT-0001.<br>Observaciones: aaa</div>\\n\\n<hr><p>SIGET — Sistema Integral de Gestión de Equipos y Soporte Tecnológico<br>\\nEste es un aviso automático. No respondas a este remitente.</p>\\n</body></html>\\n", "text": "Hola Diego,\\n\\nSe te ha asignado la orden de trabajo OT-0001.\\nObservaciones: aaa\\n\\nSIGET — Sistema Integral de Gestión de Equipos y Soporte Tecnológico\\nEste es un aviso automático. No respondas a este remitente.\\n", "subject": "Orden de trabajo reasignada: OT-0001"}	{"codigo_ot": "OT-0001", "orden_trabajo": 1, "tecnico_anterior": 2}	\N	f	2026-10-23 19:27:22.264715+00	2026-10-23 19:26:22.2218+00
7	2	SERVICE_DESK	Orden de trabajo reasignada: OT-0001	Se te ha asignado la orden de trabajo OT-0001.\nObservaciones: asdsadasdsadsa	AMBOS	f	ERROR	1	Falta configurar RESEND_API_KEY.	2026-10-23 19:26:33.330337+00	2026-10-23 19:27:22.320328+00	\N	6e4acadc5672248208ae6739f37dad8e3c3a424cc48abba466d9fe5e46336bac	{"to": ["c.morales@institucion.cl"], "from": "", "html": "<!doctype html>\\n<html lang=\\"es\\"><head><meta charset=\\"utf-8\\"><title>Orden de trabajo reasignada: OT-0001</title></head>\\n<body style=\\"font-family:Arial,sans-serif;color:#172033;line-height:1.6\\">\\n<h1 style=\\"font-size:22px\\">Orden de trabajo reasignada: OT-0001</h1>\\n<p>Hola Carlos Andres,</p>\\n<div>Se te ha asignado la orden de trabajo OT-0001.<br>Observaciones: asdsadasdsadsa</div>\\n\\n<hr><p>SIGET — Sistema Integral de Gestión de Equipos y Soporte Tecnológico<br>\\nEste es un aviso automático. No respondas a este remitente.</p>\\n</body></html>\\n", "text": "Hola Carlos Andres,\\n\\nSe te ha asignado la orden de trabajo OT-0001.\\nObservaciones: asdsadasdsadsa\\n\\nSIGET — Sistema Integral de Gestión de Equipos y Soporte Tecnológico\\nEste es un aviso automático. No respondas a este remitente.\\n", "subject": "Orden de trabajo reasignada: OT-0001"}	{"codigo_ot": "OT-0001", "orden_trabajo": 1, "tecnico_anterior": 1}	\N	f	2026-10-23 19:28:22.418136+00	2026-10-23 19:27:22.320328+00
8	2	SERVICE_DESK	Orden de trabajo reasignada: OT-0004	Se te ha asignado la orden de trabajo OT-0004.\nObservaciones: Prueba número 5	AMBOS	f	ERROR	1	Falta configurar RESEND_API_KEY.	2026-10-23 20:26:03.088159+00	2026-10-23 20:26:03.144196+00	\N	a4ad3fc5eed978e1bc34e603afef4729630eaac70f02c03e4f9fafddaf3f3b9d	{"to": ["c.morales@institucion.cl"], "from": "", "html": "<!doctype html>\\n<html lang=\\"es\\"><head><meta charset=\\"utf-8\\"><title>Orden de trabajo reasignada: OT-0004</title></head>\\n<body style=\\"font-family:Arial,sans-serif;color:#172033;line-height:1.6\\">\\n<h1 style=\\"font-size:22px\\">Orden de trabajo reasignada: OT-0004</h1>\\n<p>Hola Carlos Andres,</p>\\n<div>Se te ha asignado la orden de trabajo OT-0004.<br>Observaciones: Prueba número 5</div>\\n\\n<hr><p>SIGET — Sistema Integral de Gestión de Equipos y Soporte Tecnológico<br>\\nEste es un aviso automático. No respondas a este remitente.</p>\\n</body></html>\\n", "text": "Hola Carlos Andres,\\n\\nSe te ha asignado la orden de trabajo OT-0004.\\nObservaciones: Prueba número 5\\n\\nSIGET — Sistema Integral de Gestión de Equipos y Soporte Tecnológico\\nEste es un aviso automático. No respondas a este remitente.\\n", "subject": "Orden de trabajo reasignada: OT-0004"}	{"codigo_ot": "OT-0004", "orden_trabajo": 4, "tecnico_anterior": 2}	\N	f	2026-10-23 20:27:03.212225+00	2026-10-23 20:26:03.144196+00
9	2	SERVICE_DESK	Orden de trabajo reasignada: OT-0003	Se te ha asignado la orden de trabajo OT-0003.\nObservaciones: Perdi la cuenta de las pruebas	AMBOS	f	ERROR	1	Falta configurar RESEND_API_KEY.	2026-10-23 20:32:25.725985+00	2026-10-23 20:32:25.785688+00	\N	bdda48df074a5162eb303635e6d3b6086e119ce1011e3a0490b038e71fec769a	{"to": ["c.morales@institucion.cl"], "from": "", "html": "<!doctype html>\\n<html lang=\\"es\\"><head><meta charset=\\"utf-8\\"><title>Orden de trabajo reasignada: OT-0003</title></head>\\n<body style=\\"font-family:Arial,sans-serif;color:#172033;line-height:1.6\\">\\n<h1 style=\\"font-size:22px\\">Orden de trabajo reasignada: OT-0003</h1>\\n<p>Hola Carlos Andres,</p>\\n<div>Se te ha asignado la orden de trabajo OT-0003.<br>Observaciones: Perdi la cuenta de las pruebas</div>\\n\\n<hr><p>SIGET — Sistema Integral de Gestión de Equipos y Soporte Tecnológico<br>\\nEste es un aviso automático. No respondas a este remitente.</p>\\n</body></html>\\n", "text": "Hola Carlos Andres,\\n\\nSe te ha asignado la orden de trabajo OT-0003.\\nObservaciones: Perdi la cuenta de las pruebas\\n\\nSIGET — Sistema Integral de Gestión de Equipos y Soporte Tecnológico\\nEste es un aviso automático. No respondas a este remitente.\\n", "subject": "Orden de trabajo reasignada: OT-0003"}	{"codigo_ot": "OT-0003", "orden_trabajo": 3, "tecnico_anterior": 2}	\N	f	2026-10-23 20:33:25.879194+00	2026-10-23 20:32:25.785688+00
\.


--
-- Data for Name: orden_repuesto; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.orden_repuesto (id_orden_repuesto, id_orden, id_repuesto, cantidad, costo_unitario, fecha_imputacion) FROM stdin;
\.


--
-- Data for Name: orden_trabajo; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.orden_trabajo (id_orden, codigo_ot, id_ticket, id_tecnico_responsable, id_estado_ot, falla_reportada, fecha_inicio, fecha_estimada_fin, fecha_termino, justificacion_pausa) FROM stdin;
1	OT-0001	1	2	2	Prueba de diagnóstico: equipo no enciende correctamente.	2026-10-21 20:37:45.852156+00	\N	\N	\N
2	OT-0002	2	1	2	Problema con el hardware	2026-10-21 23:49:19.722624+00	\N	\N	\N
4	OT-0004	4	2	2	asdsadsadasdsa	2026-10-22 00:53:17.041737+00	\N	\N	\N
3	OT-0003	3	2	3	Prueba QA: equipo presenta una falla de funcionamiento.	2026-10-22 00:07:03.965844+00	\N	\N	asadsadsa
\.


--
-- Data for Name: permiso; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.permiso (id_permiso, codigo, descripcion) FROM stdin;
1	CATALOGO_CONSULTAR	Consultar catálogo y disponibilidad de activos
2	SOLICITUD_CREAR	Registrar solicitud de asignación
3	SOLICITUD_RESOLVER	Aprobar o rechazar solicitudes de asignación
4	ENTREGA_REGISTRAR	Registrar entrega y formalizar una asignación
5	DEVOLUCION_REGISTRAR	Registrar devolución y evaluación inicial
6	TICKET_CREAR	Registrar ticket de soporte
7	TICKET_ASIGNAR	Asignar o reasignar tickets
8	TICKET_ATENDER	Atender tickets asignados
9	OT_GESTIONAR	Gestionar órdenes de trabajo
10	USUARIOS_ADMINISTRAR	Administrar usuarios, roles y permisos
11	AUDITORIA_CONSULTAR	Consultar bitácora y reportes de auditoría
\.


--
-- Data for Name: prioridad_ticket; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.prioridad_ticket (id_prioridad, nombre, nivel_urgencia, descripcion) FROM stdin;
1	Crítico	1	Interrupción total de actividades o servicios troncales
2	Alto	2	Falla grave que degrada significativamente el servicio
3	Medio	3	Inconveniente funcional con alternativa operativa
4	Bajo	4	Consulta o requerimiento menor de configuración
\.


--
-- Data for Name: repuesto; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.repuesto (id_repuesto, codigo_repuesto, nombre, marca_modelo, unidad_medida, stock_actual, stock_minimo, precio_unitario, ubicacion_bodega, activo) FROM stdin;
2	REP-0002	Disco SSD SATA 2.5" 480 GB	\N	Unidad	3	4	28990.00	\N	t
1	REP-0001	Memoria RAM DDR4	\N	Unidad	5	10	16125.00	\N	t
3	REP-0003	Batería para notebook HP	\N	Unidad	2	1	35990.00	\N	t
4	REP-0004	Ventilador para notebook	HP Pavilion 15	Unidad	12	5	12833.33	\N	t
\.


--
-- Data for Name: rol; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.rol (id_rol, nombre, descripcion) FROM stdin;
1	Usuario solicitante	Portal Web: catálogo, solicitudes de asignación, tickets y seguimiento
2	Técnico de soporte	Escritorio: entregas, devoluciones, tickets asignados, diagnósticos y órdenes de trabajo
3	Administrador del sistema	Administración de usuarios, activos, solicitudes, asignación de tickets, reportería y auditoría
\.


--
-- Data for Name: rol_permiso; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.rol_permiso (id_rol_permiso, id_rol, id_permiso) FROM stdin;
1	1	1
2	1	2
3	1	6
4	2	1
5	2	4
6	2	5
7	2	8
8	2	9
9	3	1
10	3	3
11	3	7
12	3	10
13	3	11
\.


--
-- Data for Name: sla; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.sla (id_sla, id_prioridad, tiempo_respuesta_horas, tiempo_resolucion_horas, descripcion) FROM stdin;
1	1	1	4	SLA Crítico: respuesta <= 1h, resolución <= 4h
2	2	2	8	SLA Alto: respuesta <= 2h, resolución <= 8h
3	3	4	24	SLA Medio: respuesta <= 4h, resolución <= 24h
4	4	8	72	SLA Bajo: respuesta <= 8h, resolución <= 72h
\.


--
-- Data for Name: solicitud_asignacion; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.solicitud_asignacion (id_solicitud, id_usuario, id_categoria, id_estado_solicitud, id_administrador_resolutor, fecha_solicitud, fecha_resolucion, motivo, motivo_rechazo) FROM stdin;
1	1	1	4	1	2026-10-21 22:52:15.016163+00	2026-10-21 22:53:20.397185+00	Prueba funcional del módulo de devolución SIGET	\N
\.


--
-- Data for Name: ticket; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.ticket (id_ticket, codigo_ticket, id_usuario_solicitante, id_tecnico_asignado, id_activo, id_estado_ticket, id_prioridad, asunto, descripcion, fecha_creacion, fecha_resolucion) FROM stdin;
1	TCK-0001	1	\N	3	1	3	Prueba E6-H16 - diagnóstico de equipo	Ticket de prueba para validar el registro de diagnóstico y la creación de una orden de trabajo.	2026-10-21 20:31:27.477452+00	\N
2	TCK-0002	1	\N	1	1	3	Devolución con con falla técnica: Activo INV-TEST-001	Disco duro fallando	2026-10-21 23:13:36.92867+00	\N
3	TCK-QA-001	1	\N	7	1	3	Prueba integral QA - INV-QA-001	Equipo de prueba para validar el flujo completo de diagnóstico, orden de trabajo y reparación.	2026-10-22 00:00:01.974889+00	\N
4		1	\N	8	1	1	Prueba de orden de trabajo	Ticket de prueba asociado al activo ACT-0002.	2026-10-22 00:52:18.406759+00	\N
5	TKT-PRUEBA-OTRO-USUARIO	3	\N	\N	1	4	Prueba de aislamiento entre usuarios	Ticket de prueba para comprobar que no aparece en el seguimiento de Diego.	2026-10-23 01:52:52.297743+00	\N
\.


--
-- Data for Name: ubicacion; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.ubicacion (id_ubicacion, nombre_area, edificio, piso) FROM stdin;
1	Departamento TI	Edificio Central	Piso 2
2	Bodega TI	Edificio Central	Piso 1
3	Laboratorio	Edificio A	Piso 1
\.


--
-- Data for Name: usuario; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.usuario (id_usuario, identificador_externo, proveedor_identidad, rut, nombres, apellidos, correo, activo, fecha_creacion) FROM stdin;
1	auth0|6ad11451afcad1dcde49322d	Auth0	21636490-2	Diego	Alcaino	di.alcaino@duocuc.cl	t	2026-10-15 17:58:41.709612+00
2	auth0|6ad9225130bc3afcc2d8b545	Auth0	12222222-5	Carlos Andres	Morales Vega	c.morales@institucion.cl	t	2026-10-21 20:36:32.800229+00
3	auth0|6adabd5d1da8c18b84927efe	Auth0	11111111-1	Usuario Solicitante	Usuario Solicitante	u.solicitante@empresa.cl	t	2026-10-23 01:50:20.050875+00
\.


--
-- Data for Name: usuario_rol; Type: TABLE DATA; Schema: public; Owner: siget_dev
--

COPY public.usuario_rol (id_usuario_rol, id_usuario, id_rol, fecha_asignacion) FROM stdin;
1	1	3	2026-10-15 17:58:41.732786+00
2	2	2	2026-10-21 20:36:32.819485+00
6	1	2	2026-10-22 00:17:13.818232+00
7	1	1	2026-10-23 00:48:11.582516+00
8	3	1	2026-10-23 01:50:20.063656+00
\.


--
-- Name: activo_id_activo_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.activo_id_activo_seq', 8, true);


--
-- Name: adjunto_ticket_id_adjunto_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.adjunto_ticket_id_adjunto_seq', 1, false);


--
-- Name: asignacion_id_asignacion_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.asignacion_id_asignacion_seq', 1, true);


--
-- Name: bitacora_auditoria_id_auditoria_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.bitacora_auditoria_id_auditoria_seq', 78, true);


--
-- Name: categoria_activo_id_categoria_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.categoria_activo_id_categoria_seq', 5, true);


--
-- Name: codigo_qr_id_qr_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.codigo_qr_id_qr_seq', 1, false);


--
-- Name: comentario_ticket_id_comentario_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.comentario_ticket_id_comentario_seq', 1, false);


--
-- Name: devolucion_activo_id_devolucion_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.devolucion_activo_id_devolucion_seq', 1, true);


--
-- Name: diagnostico_id_diagnostico_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.diagnostico_id_diagnostico_seq', 4, true);


--
-- Name: django_migrations_id_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.django_migrations_id_seq', 1, true);


--
-- Name: estado_activo_id_estado_activo_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.estado_activo_id_estado_activo_seq', 5, true);


--
-- Name: estado_asignacion_id_estado_asignacion_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.estado_asignacion_id_estado_asignacion_seq', 2, true);


--
-- Name: estado_orden_trabajo_id_estado_ot_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.estado_orden_trabajo_id_estado_ot_seq', 4, true);


--
-- Name: estado_solicitud_asignacion_id_estado_solicitud_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.estado_solicitud_asignacion_id_estado_solicitud_seq', 4, true);


--
-- Name: estado_ticket_id_estado_ticket_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.estado_ticket_id_estado_ticket_seq', 5, true);


--
-- Name: evaluacion_csat_id_evaluacion_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.evaluacion_csat_id_evaluacion_seq', 1, false);


--
-- Name: historial_estado_activo_id_historial_estado_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.historial_estado_activo_id_historial_estado_seq', 5, true);


--
-- Name: intervencion_id_intervencion_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.intervencion_id_intervencion_seq', 1, false);


--
-- Name: marca_id_marca_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.marca_id_marca_seq', 5, true);


--
-- Name: modelo_activo_id_modelo_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.modelo_activo_id_modelo_seq', 10, true);


--
-- Name: movimiento_repuesto_id_movimiento_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.movimiento_repuesto_id_movimiento_seq', 8, true);


--
-- Name: notificacion_id_notificacion_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.notificacion_id_notificacion_seq', 9, true);


--
-- Name: orden_repuesto_id_orden_repuesto_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.orden_repuesto_id_orden_repuesto_seq', 1, false);


--
-- Name: orden_trabajo_id_orden_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.orden_trabajo_id_orden_seq', 4, true);


--
-- Name: permiso_id_permiso_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.permiso_id_permiso_seq', 11, true);


--
-- Name: prioridad_ticket_id_prioridad_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.prioridad_ticket_id_prioridad_seq', 4, true);


--
-- Name: repuesto_id_repuesto_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.repuesto_id_repuesto_seq', 4, true);


--
-- Name: rol_id_rol_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.rol_id_rol_seq', 3, true);


--
-- Name: rol_permiso_id_rol_permiso_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.rol_permiso_id_rol_permiso_seq', 13, true);


--
-- Name: sla_id_sla_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.sla_id_sla_seq', 4, true);


--
-- Name: solicitud_asignacion_id_solicitud_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.solicitud_asignacion_id_solicitud_seq', 1, true);


--
-- Name: ticket_id_ticket_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.ticket_id_ticket_seq', 5, true);


--
-- Name: ubicacion_id_ubicacion_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.ubicacion_id_ubicacion_seq', 3, true);


--
-- Name: usuario_id_usuario_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.usuario_id_usuario_seq', 3, true);


--
-- Name: usuario_rol_id_usuario_rol_seq; Type: SEQUENCE SET; Schema: public; Owner: siget_dev
--

SELECT pg_catalog.setval('public.usuario_rol_id_usuario_rol_seq', 8, true);


--
-- Name: activo activo_codigo_inventario_key; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.activo
    ADD CONSTRAINT activo_codigo_inventario_key UNIQUE (codigo_inventario);


--
-- Name: activo activo_numero_serie_key; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.activo
    ADD CONSTRAINT activo_numero_serie_key UNIQUE (numero_serie);


--
-- Name: activo activo_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.activo
    ADD CONSTRAINT activo_pkey PRIMARY KEY (id_activo);


--
-- Name: adjunto_ticket adjunto_ticket_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.adjunto_ticket
    ADD CONSTRAINT adjunto_ticket_pkey PRIMARY KEY (id_adjunto);


--
-- Name: asignacion asignacion_id_solicitud_key; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.asignacion
    ADD CONSTRAINT asignacion_id_solicitud_key UNIQUE (id_solicitud);


--
-- Name: asignacion asignacion_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.asignacion
    ADD CONSTRAINT asignacion_pkey PRIMARY KEY (id_asignacion);


--
-- Name: bitacora_auditoria bitacora_auditoria_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.bitacora_auditoria
    ADD CONSTRAINT bitacora_auditoria_pkey PRIMARY KEY (id_auditoria);


--
-- Name: categoria_activo categoria_activo_nombre_key; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.categoria_activo
    ADD CONSTRAINT categoria_activo_nombre_key UNIQUE (nombre);


--
-- Name: categoria_activo categoria_activo_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.categoria_activo
    ADD CONSTRAINT categoria_activo_pkey PRIMARY KEY (id_categoria);


--
-- Name: codigo_qr codigo_qr_id_activo_key; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.codigo_qr
    ADD CONSTRAINT codigo_qr_id_activo_key UNIQUE (id_activo);


--
-- Name: codigo_qr codigo_qr_payload_qr_key; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.codigo_qr
    ADD CONSTRAINT codigo_qr_payload_qr_key UNIQUE (payload_qr);


--
-- Name: codigo_qr codigo_qr_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.codigo_qr
    ADD CONSTRAINT codigo_qr_pkey PRIMARY KEY (id_qr);


--
-- Name: comentario_ticket comentario_ticket_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.comentario_ticket
    ADD CONSTRAINT comentario_ticket_pkey PRIMARY KEY (id_comentario);


--
-- Name: devolucion_activo devolucion_activo_id_asignacion_key; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.devolucion_activo
    ADD CONSTRAINT devolucion_activo_id_asignacion_key UNIQUE (id_asignacion);


--
-- Name: devolucion_activo devolucion_activo_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.devolucion_activo
    ADD CONSTRAINT devolucion_activo_pkey PRIMARY KEY (id_devolucion);


--
-- Name: diagnostico diagnostico_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.diagnostico
    ADD CONSTRAINT diagnostico_pkey PRIMARY KEY (id_diagnostico);


--
-- Name: django_migrations django_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.django_migrations
    ADD CONSTRAINT django_migrations_pkey PRIMARY KEY (id);


--
-- Name: django_session django_session_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.django_session
    ADD CONSTRAINT django_session_pkey PRIMARY KEY (session_key);


--
-- Name: estado_activo estado_activo_nombre_key; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.estado_activo
    ADD CONSTRAINT estado_activo_nombre_key UNIQUE (nombre);


--
-- Name: estado_activo estado_activo_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.estado_activo
    ADD CONSTRAINT estado_activo_pkey PRIMARY KEY (id_estado_activo);


--
-- Name: estado_asignacion estado_asignacion_nombre_key; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.estado_asignacion
    ADD CONSTRAINT estado_asignacion_nombre_key UNIQUE (nombre);


--
-- Name: estado_asignacion estado_asignacion_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.estado_asignacion
    ADD CONSTRAINT estado_asignacion_pkey PRIMARY KEY (id_estado_asignacion);


--
-- Name: estado_orden_trabajo estado_orden_trabajo_nombre_key; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.estado_orden_trabajo
    ADD CONSTRAINT estado_orden_trabajo_nombre_key UNIQUE (nombre);


--
-- Name: estado_orden_trabajo estado_orden_trabajo_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.estado_orden_trabajo
    ADD CONSTRAINT estado_orden_trabajo_pkey PRIMARY KEY (id_estado_ot);


--
-- Name: estado_solicitud_asignacion estado_solicitud_asignacion_nombre_key; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.estado_solicitud_asignacion
    ADD CONSTRAINT estado_solicitud_asignacion_nombre_key UNIQUE (nombre);


--
-- Name: estado_solicitud_asignacion estado_solicitud_asignacion_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.estado_solicitud_asignacion
    ADD CONSTRAINT estado_solicitud_asignacion_pkey PRIMARY KEY (id_estado_solicitud);


--
-- Name: estado_ticket estado_ticket_nombre_key; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.estado_ticket
    ADD CONSTRAINT estado_ticket_nombre_key UNIQUE (nombre);


--
-- Name: estado_ticket estado_ticket_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.estado_ticket
    ADD CONSTRAINT estado_ticket_pkey PRIMARY KEY (id_estado_ticket);


--
-- Name: evaluacion_csat evaluacion_csat_id_ticket_key; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.evaluacion_csat
    ADD CONSTRAINT evaluacion_csat_id_ticket_key UNIQUE (id_ticket);


--
-- Name: evaluacion_csat evaluacion_csat_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.evaluacion_csat
    ADD CONSTRAINT evaluacion_csat_pkey PRIMARY KEY (id_evaluacion);


--
-- Name: historial_estado_activo historial_estado_activo_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.historial_estado_activo
    ADD CONSTRAINT historial_estado_activo_pkey PRIMARY KEY (id_historial_estado);


--
-- Name: intervencion intervencion_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.intervencion
    ADD CONSTRAINT intervencion_pkey PRIMARY KEY (id_intervencion);


--
-- Name: marca marca_nombre_key; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.marca
    ADD CONSTRAINT marca_nombre_key UNIQUE (nombre);


--
-- Name: marca marca_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.marca
    ADD CONSTRAINT marca_pkey PRIMARY KEY (id_marca);


--
-- Name: modelo_activo modelo_activo_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.modelo_activo
    ADD CONSTRAINT modelo_activo_pkey PRIMARY KEY (id_modelo);


--
-- Name: movimiento_repuesto movimiento_repuesto_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.movimiento_repuesto
    ADD CONSTRAINT movimiento_repuesto_pkey PRIMARY KEY (id_movimiento);


--
-- Name: notificacion notificacion_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.notificacion
    ADD CONSTRAINT notificacion_pkey PRIMARY KEY (id_notificacion);


--
-- Name: orden_repuesto orden_repuesto_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.orden_repuesto
    ADD CONSTRAINT orden_repuesto_pkey PRIMARY KEY (id_orden_repuesto);


--
-- Name: orden_trabajo orden_trabajo_codigo_ot_key; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.orden_trabajo
    ADD CONSTRAINT orden_trabajo_codigo_ot_key UNIQUE (codigo_ot);


--
-- Name: orden_trabajo orden_trabajo_id_ticket_key; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.orden_trabajo
    ADD CONSTRAINT orden_trabajo_id_ticket_key UNIQUE (id_ticket);


--
-- Name: orden_trabajo orden_trabajo_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.orden_trabajo
    ADD CONSTRAINT orden_trabajo_pkey PRIMARY KEY (id_orden);


--
-- Name: permiso permiso_codigo_key; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.permiso
    ADD CONSTRAINT permiso_codigo_key UNIQUE (codigo);


--
-- Name: permiso permiso_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.permiso
    ADD CONSTRAINT permiso_pkey PRIMARY KEY (id_permiso);


--
-- Name: prioridad_ticket prioridad_ticket_nivel_urgencia_key; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.prioridad_ticket
    ADD CONSTRAINT prioridad_ticket_nivel_urgencia_key UNIQUE (nivel_urgencia);


--
-- Name: prioridad_ticket prioridad_ticket_nombre_key; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.prioridad_ticket
    ADD CONSTRAINT prioridad_ticket_nombre_key UNIQUE (nombre);


--
-- Name: prioridad_ticket prioridad_ticket_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.prioridad_ticket
    ADD CONSTRAINT prioridad_ticket_pkey PRIMARY KEY (id_prioridad);


--
-- Name: repuesto repuesto_codigo_repuesto_key; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.repuesto
    ADD CONSTRAINT repuesto_codigo_repuesto_key UNIQUE (codigo_repuesto);


--
-- Name: repuesto repuesto_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.repuesto
    ADD CONSTRAINT repuesto_pkey PRIMARY KEY (id_repuesto);


--
-- Name: rol rol_nombre_key; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.rol
    ADD CONSTRAINT rol_nombre_key UNIQUE (nombre);


--
-- Name: rol_permiso rol_permiso_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.rol_permiso
    ADD CONSTRAINT rol_permiso_pkey PRIMARY KEY (id_rol_permiso);


--
-- Name: rol rol_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.rol
    ADD CONSTRAINT rol_pkey PRIMARY KEY (id_rol);


--
-- Name: sla sla_id_prioridad_key; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.sla
    ADD CONSTRAINT sla_id_prioridad_key UNIQUE (id_prioridad);


--
-- Name: sla sla_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.sla
    ADD CONSTRAINT sla_pkey PRIMARY KEY (id_sla);


--
-- Name: solicitud_asignacion solicitud_asignacion_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.solicitud_asignacion
    ADD CONSTRAINT solicitud_asignacion_pkey PRIMARY KEY (id_solicitud);


--
-- Name: ticket ticket_codigo_ticket_key; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.ticket
    ADD CONSTRAINT ticket_codigo_ticket_key UNIQUE (codigo_ticket);


--
-- Name: ticket ticket_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.ticket
    ADD CONSTRAINT ticket_pkey PRIMARY KEY (id_ticket);


--
-- Name: ubicacion ubicacion_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.ubicacion
    ADD CONSTRAINT ubicacion_pkey PRIMARY KEY (id_ubicacion);


--
-- Name: modelo_activo uk_modelo_marca_categoria_nombre; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.modelo_activo
    ADD CONSTRAINT uk_modelo_marca_categoria_nombre UNIQUE (id_marca, id_categoria, nombre);


--
-- Name: rol_permiso uk_rol_permiso; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.rol_permiso
    ADD CONSTRAINT uk_rol_permiso UNIQUE (id_rol, id_permiso);


--
-- Name: usuario_rol uk_usuario_rol; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.usuario_rol
    ADD CONSTRAINT uk_usuario_rol UNIQUE (id_usuario, id_rol);


--
-- Name: usuario usuario_correo_key; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.usuario
    ADD CONSTRAINT usuario_correo_key UNIQUE (correo);


--
-- Name: usuario usuario_identificador_externo_key; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.usuario
    ADD CONSTRAINT usuario_identificador_externo_key UNIQUE (identificador_externo);


--
-- Name: usuario usuario_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.usuario
    ADD CONSTRAINT usuario_pkey PRIMARY KEY (id_usuario);


--
-- Name: usuario_rol usuario_rol_pkey; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.usuario_rol
    ADD CONSTRAINT usuario_rol_pkey PRIMARY KEY (id_usuario_rol);


--
-- Name: usuario usuario_rut_key; Type: CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.usuario
    ADD CONSTRAINT usuario_rut_key UNIQUE (rut);


--
-- Name: django_session_expire_date_a5c62663; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX django_session_expire_date_a5c62663 ON public.django_session USING btree (expire_date);


--
-- Name: django_session_session_key_c0390e0f_like; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX django_session_session_key_c0390e0f_like ON public.django_session USING btree (session_key varchar_pattern_ops);


--
-- Name: idx_activo_estado; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_activo_estado ON public.activo USING btree (id_estado_activo);


--
-- Name: idx_activo_modelo; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_activo_modelo ON public.activo USING btree (id_modelo);


--
-- Name: idx_activo_ubicacion; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_activo_ubicacion ON public.activo USING btree (id_ubicacion);


--
-- Name: idx_adjunto_ticket; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_adjunto_ticket ON public.adjunto_ticket USING btree (id_ticket);


--
-- Name: idx_asignacion_activo; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_asignacion_activo ON public.asignacion USING btree (id_activo);


--
-- Name: idx_asignacion_estado; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_asignacion_estado ON public.asignacion USING btree (id_estado_asignacion);


--
-- Name: idx_auditoria_entidad; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_auditoria_entidad ON public.bitacora_auditoria USING btree (entidad_afectada, id_registro_afectado);


--
-- Name: idx_auditoria_fecha; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_auditoria_fecha ON public.bitacora_auditoria USING btree (fecha_evento DESC);


--
-- Name: idx_comentario_ticket; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_comentario_ticket ON public.comentario_ticket USING btree (id_ticket, fecha_registro);


--
-- Name: idx_devolucion_estado_resultante; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_devolucion_estado_resultante ON public.devolucion_activo USING btree (id_estado_activo_resultante);


--
-- Name: idx_diagnostico_orden; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_diagnostico_orden ON public.diagnostico USING btree (id_orden);


--
-- Name: idx_historial_activo_fecha; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_historial_activo_fecha ON public.historial_estado_activo USING btree (id_activo, fecha_cambio DESC);


--
-- Name: idx_intervencion_orden; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_intervencion_orden ON public.intervencion USING btree (id_orden, fecha_intervencion);


--
-- Name: idx_modelo_categoria; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_modelo_categoria ON public.modelo_activo USING btree (id_categoria);


--
-- Name: idx_movimiento_repuesto_fecha; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_movimiento_repuesto_fecha ON public.movimiento_repuesto USING btree (id_repuesto, fecha_movimiento);


--
-- Name: idx_notificacion_estado_envio; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_notificacion_estado_envio ON public.notificacion USING btree (estado_envio);


--
-- Name: idx_notificacion_usuario_fecha; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_notificacion_usuario_fecha ON public.notificacion USING btree (id_usuario, fecha_creacion DESC);


--
-- Name: idx_orden_repuesto_orden; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_orden_repuesto_orden ON public.orden_repuesto USING btree (id_orden);


--
-- Name: idx_ot_estado; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_ot_estado ON public.orden_trabajo USING btree (id_estado_ot);


--
-- Name: idx_ot_tecnico; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_ot_tecnico ON public.orden_trabajo USING btree (id_tecnico_responsable);


--
-- Name: idx_rol_permiso_permiso; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_rol_permiso_permiso ON public.rol_permiso USING btree (id_permiso);


--
-- Name: idx_rol_permiso_rol; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_rol_permiso_rol ON public.rol_permiso USING btree (id_rol);


--
-- Name: idx_solicitud_categoria; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_solicitud_categoria ON public.solicitud_asignacion USING btree (id_categoria);


--
-- Name: idx_solicitud_estado; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_solicitud_estado ON public.solicitud_asignacion USING btree (id_estado_solicitud);


--
-- Name: idx_solicitud_usuario; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_solicitud_usuario ON public.solicitud_asignacion USING btree (id_usuario);


--
-- Name: idx_ticket_activo; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_ticket_activo ON public.ticket USING btree (id_activo);


--
-- Name: idx_ticket_estado; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_ticket_estado ON public.ticket USING btree (id_estado_ticket);


--
-- Name: idx_ticket_prioridad; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_ticket_prioridad ON public.ticket USING btree (id_prioridad);


--
-- Name: idx_ticket_solicitante; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_ticket_solicitante ON public.ticket USING btree (id_usuario_solicitante);


--
-- Name: idx_ticket_tecnico; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_ticket_tecnico ON public.ticket USING btree (id_tecnico_asignado);


--
-- Name: idx_usuario_rol_rol; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_usuario_rol_rol ON public.usuario_rol USING btree (id_rol);


--
-- Name: idx_usuario_rol_usuario; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE INDEX idx_usuario_rol_usuario ON public.usuario_rol USING btree (id_usuario);


--
-- Name: uk_asignacion_activo_abierta; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE UNIQUE INDEX uk_asignacion_activo_abierta ON public.asignacion USING btree (id_activo) WHERE (fecha_finalizacion IS NULL);


--
-- Name: uq_notificacion_clave_evento; Type: INDEX; Schema: public; Owner: siget_dev
--

CREATE UNIQUE INDEX uq_notificacion_clave_evento ON public.notificacion USING btree (clave_evento);


--
-- Name: activo activo_id_estado_activo_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.activo
    ADD CONSTRAINT activo_id_estado_activo_fkey FOREIGN KEY (id_estado_activo) REFERENCES public.estado_activo(id_estado_activo) ON DELETE RESTRICT;


--
-- Name: activo activo_id_modelo_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.activo
    ADD CONSTRAINT activo_id_modelo_fkey FOREIGN KEY (id_modelo) REFERENCES public.modelo_activo(id_modelo) ON DELETE RESTRICT;


--
-- Name: activo activo_id_ubicacion_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.activo
    ADD CONSTRAINT activo_id_ubicacion_fkey FOREIGN KEY (id_ubicacion) REFERENCES public.ubicacion(id_ubicacion) ON DELETE RESTRICT;


--
-- Name: adjunto_ticket adjunto_ticket_id_ticket_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.adjunto_ticket
    ADD CONSTRAINT adjunto_ticket_id_ticket_fkey FOREIGN KEY (id_ticket) REFERENCES public.ticket(id_ticket) ON DELETE CASCADE;


--
-- Name: asignacion asignacion_id_activo_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.asignacion
    ADD CONSTRAINT asignacion_id_activo_fkey FOREIGN KEY (id_activo) REFERENCES public.activo(id_activo) ON DELETE RESTRICT;


--
-- Name: asignacion asignacion_id_estado_asignacion_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.asignacion
    ADD CONSTRAINT asignacion_id_estado_asignacion_fkey FOREIGN KEY (id_estado_asignacion) REFERENCES public.estado_asignacion(id_estado_asignacion) ON DELETE RESTRICT;


--
-- Name: asignacion asignacion_id_solicitud_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.asignacion
    ADD CONSTRAINT asignacion_id_solicitud_fkey FOREIGN KEY (id_solicitud) REFERENCES public.solicitud_asignacion(id_solicitud) ON DELETE RESTRICT;


--
-- Name: asignacion asignacion_id_tecnico_entrega_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.asignacion
    ADD CONSTRAINT asignacion_id_tecnico_entrega_fkey FOREIGN KEY (id_tecnico_entrega) REFERENCES public.usuario(id_usuario) ON DELETE RESTRICT;


--
-- Name: bitacora_auditoria bitacora_auditoria_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.bitacora_auditoria
    ADD CONSTRAINT bitacora_auditoria_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario(id_usuario) ON DELETE SET NULL;


--
-- Name: codigo_qr codigo_qr_id_activo_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.codigo_qr
    ADD CONSTRAINT codigo_qr_id_activo_fkey FOREIGN KEY (id_activo) REFERENCES public.activo(id_activo) ON DELETE CASCADE;


--
-- Name: comentario_ticket comentario_ticket_id_ticket_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.comentario_ticket
    ADD CONSTRAINT comentario_ticket_id_ticket_fkey FOREIGN KEY (id_ticket) REFERENCES public.ticket(id_ticket) ON DELETE CASCADE;


--
-- Name: comentario_ticket comentario_ticket_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.comentario_ticket
    ADD CONSTRAINT comentario_ticket_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario(id_usuario) ON DELETE RESTRICT;


--
-- Name: devolucion_activo devolucion_activo_id_asignacion_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.devolucion_activo
    ADD CONSTRAINT devolucion_activo_id_asignacion_fkey FOREIGN KEY (id_asignacion) REFERENCES public.asignacion(id_asignacion) ON DELETE RESTRICT;


--
-- Name: devolucion_activo devolucion_activo_id_estado_activo_resultante_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.devolucion_activo
    ADD CONSTRAINT devolucion_activo_id_estado_activo_resultante_fkey FOREIGN KEY (id_estado_activo_resultante) REFERENCES public.estado_activo(id_estado_activo) ON DELETE RESTRICT;


--
-- Name: devolucion_activo devolucion_activo_id_tecnico_receptor_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.devolucion_activo
    ADD CONSTRAINT devolucion_activo_id_tecnico_receptor_fkey FOREIGN KEY (id_tecnico_receptor) REFERENCES public.usuario(id_usuario) ON DELETE RESTRICT;


--
-- Name: diagnostico diagnostico_id_orden_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.diagnostico
    ADD CONSTRAINT diagnostico_id_orden_fkey FOREIGN KEY (id_orden) REFERENCES public.orden_trabajo(id_orden) ON DELETE CASCADE;


--
-- Name: diagnostico diagnostico_id_tecnico_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.diagnostico
    ADD CONSTRAINT diagnostico_id_tecnico_fkey FOREIGN KEY (id_tecnico) REFERENCES public.usuario(id_usuario) ON DELETE RESTRICT;


--
-- Name: evaluacion_csat evaluacion_csat_id_ticket_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.evaluacion_csat
    ADD CONSTRAINT evaluacion_csat_id_ticket_fkey FOREIGN KEY (id_ticket) REFERENCES public.ticket(id_ticket) ON DELETE CASCADE;


--
-- Name: evaluacion_csat evaluacion_csat_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.evaluacion_csat
    ADD CONSTRAINT evaluacion_csat_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario(id_usuario) ON DELETE RESTRICT;


--
-- Name: historial_estado_activo historial_estado_activo_id_activo_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.historial_estado_activo
    ADD CONSTRAINT historial_estado_activo_id_activo_fkey FOREIGN KEY (id_activo) REFERENCES public.activo(id_activo) ON DELETE CASCADE;


--
-- Name: historial_estado_activo historial_estado_activo_id_estado_activo_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.historial_estado_activo
    ADD CONSTRAINT historial_estado_activo_id_estado_activo_fkey FOREIGN KEY (id_estado_activo) REFERENCES public.estado_activo(id_estado_activo) ON DELETE RESTRICT;


--
-- Name: historial_estado_activo historial_estado_activo_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.historial_estado_activo
    ADD CONSTRAINT historial_estado_activo_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario(id_usuario) ON DELETE SET NULL;


--
-- Name: intervencion intervencion_id_orden_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.intervencion
    ADD CONSTRAINT intervencion_id_orden_fkey FOREIGN KEY (id_orden) REFERENCES public.orden_trabajo(id_orden) ON DELETE CASCADE;


--
-- Name: intervencion intervencion_id_tecnico_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.intervencion
    ADD CONSTRAINT intervencion_id_tecnico_fkey FOREIGN KEY (id_tecnico) REFERENCES public.usuario(id_usuario) ON DELETE RESTRICT;


--
-- Name: modelo_activo modelo_activo_id_categoria_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.modelo_activo
    ADD CONSTRAINT modelo_activo_id_categoria_fkey FOREIGN KEY (id_categoria) REFERENCES public.categoria_activo(id_categoria) ON DELETE RESTRICT;


--
-- Name: modelo_activo modelo_activo_id_marca_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.modelo_activo
    ADD CONSTRAINT modelo_activo_id_marca_fkey FOREIGN KEY (id_marca) REFERENCES public.marca(id_marca) ON DELETE RESTRICT;


--
-- Name: movimiento_repuesto movimiento_repuesto_id_repuesto_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.movimiento_repuesto
    ADD CONSTRAINT movimiento_repuesto_id_repuesto_fkey FOREIGN KEY (id_repuesto) REFERENCES public.repuesto(id_repuesto) ON DELETE RESTRICT;


--
-- Name: movimiento_repuesto movimiento_repuesto_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.movimiento_repuesto
    ADD CONSTRAINT movimiento_repuesto_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario(id_usuario) ON DELETE RESTRICT;


--
-- Name: notificacion notificacion_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.notificacion
    ADD CONSTRAINT notificacion_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario(id_usuario) ON DELETE CASCADE;


--
-- Name: orden_repuesto orden_repuesto_id_orden_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.orden_repuesto
    ADD CONSTRAINT orden_repuesto_id_orden_fkey FOREIGN KEY (id_orden) REFERENCES public.orden_trabajo(id_orden) ON DELETE CASCADE;


--
-- Name: orden_repuesto orden_repuesto_id_repuesto_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.orden_repuesto
    ADD CONSTRAINT orden_repuesto_id_repuesto_fkey FOREIGN KEY (id_repuesto) REFERENCES public.repuesto(id_repuesto) ON DELETE RESTRICT;


--
-- Name: orden_trabajo orden_trabajo_id_estado_ot_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.orden_trabajo
    ADD CONSTRAINT orden_trabajo_id_estado_ot_fkey FOREIGN KEY (id_estado_ot) REFERENCES public.estado_orden_trabajo(id_estado_ot) ON DELETE RESTRICT;


--
-- Name: orden_trabajo orden_trabajo_id_tecnico_responsable_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.orden_trabajo
    ADD CONSTRAINT orden_trabajo_id_tecnico_responsable_fkey FOREIGN KEY (id_tecnico_responsable) REFERENCES public.usuario(id_usuario) ON DELETE RESTRICT;


--
-- Name: orden_trabajo orden_trabajo_id_ticket_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.orden_trabajo
    ADD CONSTRAINT orden_trabajo_id_ticket_fkey FOREIGN KEY (id_ticket) REFERENCES public.ticket(id_ticket) ON DELETE RESTRICT;


--
-- Name: rol_permiso rol_permiso_id_permiso_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.rol_permiso
    ADD CONSTRAINT rol_permiso_id_permiso_fkey FOREIGN KEY (id_permiso) REFERENCES public.permiso(id_permiso) ON DELETE RESTRICT;


--
-- Name: rol_permiso rol_permiso_id_rol_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.rol_permiso
    ADD CONSTRAINT rol_permiso_id_rol_fkey FOREIGN KEY (id_rol) REFERENCES public.rol(id_rol) ON DELETE CASCADE;


--
-- Name: sla sla_id_prioridad_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.sla
    ADD CONSTRAINT sla_id_prioridad_fkey FOREIGN KEY (id_prioridad) REFERENCES public.prioridad_ticket(id_prioridad) ON DELETE RESTRICT;


--
-- Name: solicitud_asignacion solicitud_asignacion_id_administrador_resolutor_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.solicitud_asignacion
    ADD CONSTRAINT solicitud_asignacion_id_administrador_resolutor_fkey FOREIGN KEY (id_administrador_resolutor) REFERENCES public.usuario(id_usuario) ON DELETE SET NULL;


--
-- Name: solicitud_asignacion solicitud_asignacion_id_categoria_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.solicitud_asignacion
    ADD CONSTRAINT solicitud_asignacion_id_categoria_fkey FOREIGN KEY (id_categoria) REFERENCES public.categoria_activo(id_categoria) ON DELETE RESTRICT;


--
-- Name: solicitud_asignacion solicitud_asignacion_id_estado_solicitud_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.solicitud_asignacion
    ADD CONSTRAINT solicitud_asignacion_id_estado_solicitud_fkey FOREIGN KEY (id_estado_solicitud) REFERENCES public.estado_solicitud_asignacion(id_estado_solicitud) ON DELETE RESTRICT;


--
-- Name: solicitud_asignacion solicitud_asignacion_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.solicitud_asignacion
    ADD CONSTRAINT solicitud_asignacion_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario(id_usuario) ON DELETE RESTRICT;


--
-- Name: ticket ticket_id_activo_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.ticket
    ADD CONSTRAINT ticket_id_activo_fkey FOREIGN KEY (id_activo) REFERENCES public.activo(id_activo) ON DELETE SET NULL;


--
-- Name: ticket ticket_id_estado_ticket_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.ticket
    ADD CONSTRAINT ticket_id_estado_ticket_fkey FOREIGN KEY (id_estado_ticket) REFERENCES public.estado_ticket(id_estado_ticket) ON DELETE RESTRICT;


--
-- Name: ticket ticket_id_prioridad_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.ticket
    ADD CONSTRAINT ticket_id_prioridad_fkey FOREIGN KEY (id_prioridad) REFERENCES public.prioridad_ticket(id_prioridad) ON DELETE RESTRICT;


--
-- Name: ticket ticket_id_tecnico_asignado_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.ticket
    ADD CONSTRAINT ticket_id_tecnico_asignado_fkey FOREIGN KEY (id_tecnico_asignado) REFERENCES public.usuario(id_usuario) ON DELETE SET NULL;


--
-- Name: ticket ticket_id_usuario_solicitante_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.ticket
    ADD CONSTRAINT ticket_id_usuario_solicitante_fkey FOREIGN KEY (id_usuario_solicitante) REFERENCES public.usuario(id_usuario) ON DELETE RESTRICT;


--
-- Name: usuario_rol usuario_rol_id_rol_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.usuario_rol
    ADD CONSTRAINT usuario_rol_id_rol_fkey FOREIGN KEY (id_rol) REFERENCES public.rol(id_rol) ON DELETE RESTRICT;


--
-- Name: usuario_rol usuario_rol_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: siget_dev
--

ALTER TABLE ONLY public.usuario_rol
    ADD CONSTRAINT usuario_rol_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario(id_usuario) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict A6qd71F4Nawnw8vcgyQwYyNJYpA2POWbGFGLxcSLDUXdbigD6gPmJuVYSqyOCTz

