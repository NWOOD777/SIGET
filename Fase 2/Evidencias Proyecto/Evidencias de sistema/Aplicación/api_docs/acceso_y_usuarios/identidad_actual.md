# Consultar identidad y acceso propios

Ruta: `/api/usuarios/me/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `GET` | Cuenta SIGET activa; no exige rol administrativo. | `200`, identidad, roles y permisos efectivos. |

`GET /api/usuarios/me/`

Permite a la aplicación de escritorio y a la plataforma Web obtener los datos consolidados del usuario autenticado sin requerir permisos administrativos ni exponer datos confidenciales de terceros.

Respuesta (`200 OK`):

```json
{
  "id_usuario": 2,
  "nombres": "Tomás",
  "apellidos": "Técnico",
  "nombre_completo": "Tomás Técnico",
  "correo": "tomas.tecnico@siget.cl",
  "roles": [
    "Técnico de soporte"
  ],
  "permisos": [
    "CATALOGO_CONSULTAR",
    "DEVOLUCION_REGISTRAR",
    "ENTREGA_REGISTRAR",
    "OT_GESTIONAR",
    "TICKET_ATENDER"
  ],
  "acceso_escritorio": true,
  "metodo_autenticacion": "bearer"
}
```

El campo `acceso_escritorio` es `true` si el usuario posee al menos uno de los roles autorizados para la aplicación de escritorio (`Técnico de soporte` o `Administrador del sistema`). Un usuario con rol exclusivo de `Usuario solicitante` recibe `acceso_escritorio: false`.

Consultar [autenticación y uso general](../uso_general.md) y [respuestas y errores](../respuestas_y_errores.md).

[Volver a acceso y usuarios](README.md) · [Índice general](../README.md)
