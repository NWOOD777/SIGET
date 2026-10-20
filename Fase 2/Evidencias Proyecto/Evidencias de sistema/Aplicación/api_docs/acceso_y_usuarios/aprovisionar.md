# Aprovisionar un usuario

Ruta: `/api/usuarios/aprovisionar/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `POST` | Administrador del sistema. | `201`, ficha de acceso del usuario creado. |

`POST /api/usuarios/aprovisionar/`

```json
{
  "nombres": "Camila",
  "apellidos": "Rojas",
  "correo": "camila.rojas@example.com",
  "rut": "12.345.678-5",
  "rol": "Usuario solicitante"
}
```

Todos los campos son obligatorios. El rol debe ser `Usuario solicitante`, `Técnico de soporte` o `Administrador del sistema`. Se validan el correo, el RUT y los duplicados antes de completar el registro. Al crear la cuenta se solicita a Auth0 el envío de instrucciones para configurar la contraseña inicial.

La respuesta utiliza la [ficha de acceso del usuario](acceso_usuario.md).

Un usuario duplicado produce `409`; los datos inválidos, `400`; un fallo de comunicación con Auth0, `502`; y un error de persistencia, `500`.

Consulta [autenticación y uso general](../uso_general.md) y [respuestas y errores](../respuestas_y_errores.md).

[Volver a acceso y usuarios](README.md) · [Índice general](../README.md)
