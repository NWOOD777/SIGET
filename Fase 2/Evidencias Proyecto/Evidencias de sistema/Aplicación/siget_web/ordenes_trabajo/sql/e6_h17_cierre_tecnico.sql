-- E6-H17: instalación aditiva pendiente de revisión. No ejecutar el esquema inicial.
-- Ejecutar una sola vez, con respaldo y autorización, en el esquema de SIGET.
-- Si la tabla ya existe, falla deliberadamente: no oculta versiones incompatibles.
BEGIN;
CREATE TABLE cierre_tecnico (
    id_cierre_tecnico SERIAL PRIMARY KEY,
    id_orden INT NOT NULL CONSTRAINT uq_cierre_tecnico_orden UNIQUE
        REFERENCES orden_trabajo(id_orden) ON DELETE RESTRICT,
    id_tecnico INT NOT NULL REFERENCES usuario(id_usuario) ON DELETE RESTRICT,
    resultado VARCHAR(32) NOT NULL,
    solucion_aplicada TEXT,
    pruebas_realizadas TEXT,
    informe_descarte TEXT,
    fecha_cierre TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_cierre_tecnico_resultado CHECK (resultado IN ('REPARACION_EXITOSA', 'NO_REPARABLE')),
    CONSTRAINT ck_cierre_tecnico_contenido CHECK (
        (resultado <> 'REPARACION_EXITOSA' OR (
            solucion_aplicada IS NOT NULL AND length(translate(solucion_aplicada, U&'\0009\000a\000b\000c\000d\001c\001d\001e\001f\0020\0085\00a0\1680\2000\2001\2002\2003\2004\2005\2006\2007\2008\2009\200a\2028\2029\202f\205f\3000', '')) > 0
            AND pruebas_realizadas IS NOT NULL AND length(translate(pruebas_realizadas, U&'\0009\000a\000b\000c\000d\001c\001d\001e\001f\0020\0085\00a0\1680\2000\2001\2002\2003\2004\2005\2006\2007\2008\2009\200a\2028\2029\202f\205f\3000', '')) > 0
        )) AND
        (resultado <> 'NO_REPARABLE' OR (
            informe_descarte IS NOT NULL AND length(translate(informe_descarte, U&'\0009\000a\000b\000c\000d\001c\001d\001e\001f\0020\0085\00a0\1680\2000\2001\2002\2003\2004\2005\2006\2007\2008\2009\200a\2028\2029\202f\205f\3000', '')) > 0
        ))
    )
);
COMMENT ON TABLE cierre_tecnico IS 'Resultado final único por OT, conservando ejecutor y fecha sin sobrescribir el diagnóstico.';
COMMIT;
