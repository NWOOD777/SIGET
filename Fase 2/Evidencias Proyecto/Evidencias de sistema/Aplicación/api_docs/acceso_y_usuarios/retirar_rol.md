# Retirar un rol de un usuario

Ruta: `/api/usuarios/{id}/roles/{id_rol}/`

| Método | Acceso | Respuesta correcta |
|---|---|---|
| `DELETE` | Administrador del sistema. | `200`, confirmación en `mensaje`. |

No recibe cuerpo. Retira la asociación con el rol indicado y conserva los demás roles. No permite quitar el último rol de la cuenta.

Un usuario, rol o asociación inexistente responde `404`. Intentar dejar la cuenta sin roles responde `400`. La operación conserva el rol en el catálogo y registra auditoría.

Consulta [autenticación y uso general](../uso_general.md) y [respuestas y errores](../respuestas_y_errores.md).

[Volver a acceso y usuarios](README.md) · [Índice general](../README.md)
