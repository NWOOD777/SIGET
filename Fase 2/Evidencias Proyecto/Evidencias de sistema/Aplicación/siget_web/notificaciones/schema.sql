-- Ampliación idempotente y aditiva; no borra ni reinicializa datos.
ALTER TABLE notificacion
    ADD COLUMN IF NOT EXISTS clave_evento VARCHAR(255),
    ADD COLUMN IF NOT EXISTS datos_envio JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS referencia JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS id_proveedor VARCHAR(100),
    ADD COLUMN IF NOT EXISTS reintento_permitido BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS proximo_intento TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS fecha_primer_intento TIMESTAMPTZ;
CREATE UNIQUE INDEX IF NOT EXISTS uq_notificacion_clave_evento ON notificacion(clave_evento);
