// =========================================================
// ACTIVOS
// =========================================================

document.addEventListener("DOMContentLoaded", () => {

    const assetsTableBody = document.getElementById("assets-table-body");

    // Si no estamos en la pantalla de Activos, no hacemos nada.
    if (!assetsTableBody) {
        return;
    }

    cargarActivos();
});


async function cargarActivos() {

    const tableBody = document.getElementById("assets-table-body");

    try {

        const response = await fetch("/api/activos/");

        if (!response.ok) {
            throw new Error("No se pudieron obtener los activos.");
        }

        const activos = await response.json();

        tableBody.innerHTML = "";

        if (activos.length === 0) {

            tableBody.innerHTML = `
                <tr>
                    <td colspan="7" class="table-empty">
                        No hay activos registrados.
                    </td>
                </tr>
            `;

            return;
        }

        activos.forEach(activo => {

            const row = document.createElement("tr");

            row.innerHTML = `
                <td>${activo.codigo_inventario}</td>

                <td>
                    ${activo.categoria || "-"}
                </td>

                <td>
                    ${activo.marca || "-"}
                    ${activo.modelo ? ` / ${activo.modelo}` : ""}
                </td>

                <td>
                    ${activo.numero_serie}
                </td>

                <td>
                    ${activo.estado || "-"}
                </td>

                <td>
                    ${activo.ubicacion || "-"}
                </td>

                <td>
                    <button
                        class="asset-action"
                        type="button"
                    >
                        Ver
                    </button>
                </td>
            `;

            tableBody.appendChild(row);
        });

    } catch (error) {

        console.error("Error al cargar activos:", error);

        tableBody.innerHTML = `
            <tr>
                <td colspan="7" class="table-empty">
                    No fue posible cargar los activos.
                </td>
            </tr>
        `;
    }
}