# Retirar un permiso de un rol

Ruta: `/api/usuarios/roles/{id_rol}/permisos/{id_permiso}/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `DELETE` | Administrador del sistema. | `200`, confirmación en `mensaje`. |

No recibe cuerpo. Elimina la asociación entre el rol y el permiso y registra auditoría. El permiso permanece en el catálogo.

Un rol, permiso o asociación inexistente responde `404`. Los permisos efectivos de las cuentas se resuelven según las asociaciones vigentes.

Consulta [autenticación y uso general](../uso_general.md) y [respuestas y errores](../respuestas_y_errores.md).

[Volver a acceso y usuarios](README.md) · [Índice general](../README.md)
