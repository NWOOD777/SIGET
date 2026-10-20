# Asociar un permiso a un rol

Ruta: `/api/usuarios/roles/{id_rol}/permisos/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `POST` | Administrador del sistema. | `201`, confirmación en `mensaje`. |

Recibe el código de un permiso existente:

```json
{"codigo": "CATALOGO_CONSULTAR"}
```

También admite `{"id_permiso": 1}`. La operación modifica los permisos derivados del rol y queda auditada. No crea un permiso de catálogo.

Un rol inexistente responde `404`; datos o permiso no válidos responden `400`.

Consulta [autenticación y uso general](../uso_general.md) y [respuestas y errores](../respuestas_y_errores.md).

[Volver a acceso y usuarios](README.md) · [Índice general](../README.md)
