// =========================================================
// ACTIVOS
// =========================================================

console.log("SOPORTE.JS CARGADO");



let activosData = [];
let categoriasData = [];
let estadosData = [];

document.addEventListener("DOMContentLoaded", () => {

    const assetsTableBody = document.getElementById("assets-table-body");

    // Si no estamos en la pantalla de Activos, no hacemos nada.
    if (!assetsTableBody) {
        return;
    }

    cargarActivos();

    const searchInput = document.getElementById("asset-search");

    if (searchInput) {
        searchInput.addEventListener("input", aplicarFiltros);
    }

    const typeFilter = document.getElementById("asset-type-filter");

    if (typeFilter) {
        typeFilter.addEventListener("change", aplicarFiltros);
    }

    const statusFilter = document.getElementById("asset-status-filter");

    if (statusFilter) {
        statusFilter.addEventListener("change", aplicarFiltros);
    }

    cargarCategorias();
    cargarEstados();
    cargarModelosRegistro();
    cargarUbicacionesRegistro();
    cargarEstadosRegistro();
});

// =========================================================
// CARGAR ACTIVOS
// =========================================================

async function cargarActivos() {

    const tableBody = document.getElementById("assets-table-body");

    try {

        const response = await fetch("/api/activos/");

        if (!response.ok) {
            throw new Error("No se pudieron obtener los activos.");
        }

        activosData = await response.json();

        renderizarActivos(activosData);

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

// =========================================================
// CARGAR CATEGORÍAS
// =========================================================

async function cargarCategorias() {

    const typeFilter = document.getElementById("asset-type-filter");

    try {

        const response = await fetch("/api/activos/categorias/");

        if (!response.ok) {
            throw new Error("No se pudieron obtener las categorías.");
        }

        categoriasData = await response.json();

        categoriasData.forEach(categoria => {

            const option = document.createElement("option");

            option.value = categoria.nombre;
            option.textContent = categoria.nombre;

            typeFilter.appendChild(option);
        });

    } catch (error) {

        console.error("Error al cargar categorías:", error);
    }
}


// =========================================================
// CARGAR ESTADOS
// =========================================================

async function cargarEstados() {

    const statusFilter = document.getElementById("asset-status-filter");

    try {

        const response = await fetch("/api/activos/estados/");

        if (!response.ok) {
            throw new Error("No se pudieron obtener los estados.");
        }

        estadosData = await response.json();

        estadosData.forEach(estado => {

            const option = document.createElement("option");

            option.value = estado.id_estado_activo;
            option.textContent = estado.nombre;

            statusFilter.appendChild(option);
        });

    } catch (error) {

        console.error("Error al cargar estados:", error);
    }
}





// =========================================================
// MOSTRAR ACTIVOS
// =========================================================

function renderizarActivos(activos) {

    const tableBody = document.getElementById("assets-table-body");

    tableBody.innerHTML = "";

    if (activos.length === 0) {

        tableBody.innerHTML = `
            <tr>
                <td colspan="7" class="table-empty">
                    No se encontraron activos.
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
                ${activo.numero_serie || "-"}
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
                    onclick="verActivo(${activo.id_activo})"
                >
                    Ver
                </button>
            </td>
        `;

        tableBody.appendChild(row);
    });
}


// =========================================================
// DETALLE DE ACTIVO
// =========================================================

function verActivo(idActivo) {

    const activo = activosData.find(
        activo => activo.id_activo === idActivo
    );

    if (!activo) {
        console.error("No se encontró el activo:", idActivo);
        return;
    }

    // Tipo
    document.getElementById("detail-categoria").textContent =
        activo.categoria || "-";

    // Número de serie
    document.getElementById("detail-serie").textContent =
        activo.numero_serie || "-";

    // Estado
    document.getElementById("detail-estado").textContent =
        activo.estado || "-";

    // Usuario
    // Actualmente la API de activos no entrega el usuario asignado.
    document.getElementById("detail-usuario").textContent =
        "Sin información";

    // Ubicación
    document.getElementById("detail-ubicacion").textContent =
        activo.ubicacion || "-";

    // Fecha de registro
    document.getElementById("detail-fecha-registro").textContent =
        formatearFecha(activo.fecha_registro);

    // Garantía
    document.getElementById("detail-garantia").textContent =
        formatearFecha(activo.fecha_garantia);

    // Valor
    document.getElementById("detail-valor").textContent =
        formatearValor(activo.valor_adquisicion);

    // Abrir modal
    document.getElementById("asset-modal").style.display = "flex";
}


// =========================================================
// CERRAR MODAL
// =========================================================

function cerrarModalActivo() {

    const modal = document.getElementById("asset-modal");

    if (!modal) {
        return;
    }

    modal.style.display = "none";
}


// =========================================================
// FORMATEAR FECHA
// =========================================================

function formatearFecha(fecha) {

    if (!fecha) {
        return "-";
    }

    const fechaObj = new Date(fecha);

    if (isNaN(fechaObj.getTime())) {
        return "-";
    }

    return fechaObj.toLocaleDateString("es-CL");
}


// =========================================================
// FORMATEAR VALOR
// =================================================



// =========================================================
// FILTROS
// =========================================================

function aplicarFiltros() {

    const searchInput = document.getElementById("asset-search");
    const typeFilter = document.getElementById("asset-type-filter");
    const statusFilter = document.getElementById("asset-status-filter");

    const texto = searchInput
        ? searchInput.value.trim().toLowerCase()
        : "";

    const tipoSeleccionado = typeFilter
        ? typeFilter.value
        : "";

    const estadoSeleccionado = statusFilter
        ? statusFilter.value
        : "";

    const activosFiltrados = activosData.filter(activo => {

        const contenido = [
            activo.codigo_inventario,
            activo.numero_serie,
            activo.categoria,
            activo.marca,
            activo.modelo,
            activo.estado,
            activo.ubicacion
        ]
            .join(" ")
            .toLowerCase();

        const coincideBusqueda = contenido.includes(texto);

        const coincideTipo =
            !tipoSeleccionado ||
            activo.categoria === tipoSeleccionado;

        const coincideEstado =
            !estadoSeleccionado ||
            String(activo.id_estado_activo) === String(estadoSeleccionado);

        return coincideBusqueda &&
            coincideTipo &&
            coincideEstado;
    });

    renderizarActivos(activosFiltrados);
}

// =========================================================
// DETALLE DE ACTIVO
// =========================================================

function verActivo(idActivo) {

    const activo = activosData.find(
        activo => activo.id_activo === idActivo
    );

    if (!activo) {
        console.error("No se encontró el activo:", idActivo);
        return;
    }

    // Marca y modelo debajo del título
    const marcaModeloHeader =
        document.getElementById("detail-marca-modelo-header");

    if (marcaModeloHeader) {
        marcaModeloHeader.textContent =
            `${activo.marca || "-"} ${activo.modelo || ""}`.trim();
    }

    // Tipo

    document.getElementById("detail-codigo").textContent =
        activo.codigo_inventario || "-";


    document.getElementById("detail-categoria").textContent =
        activo.categoria || "-";

    // Número de serie
    document.getElementById("detail-serie").textContent =
        activo.numero_serie || "-";

    // Estado
    document.getElementById("detail-estado").textContent =
        activo.estado || "-";

    // Usuario
    document.getElementById("detail-usuario").textContent =
        "Sin información";

    // Marca / Modelo dentro del detalle
    const marcaModelo = document.getElementById("detail-marca-modelo");

    if (marcaModelo) {
        marcaModelo.textContent =
            `${activo.marca || "-"}${activo.modelo ? ` / ${activo.modelo}` : ""}`;
    }

    // Ubicación
    document.getElementById("detail-ubicacion").textContent =
        activo.ubicacion || "-";

    // Fecha de registro
    document.getElementById("detail-fecha-registro").textContent =
        formatearFecha(activo.fecha_registro);

    // Garantía
    document.getElementById("detail-garantia").textContent =
        formatearFecha(activo.fecha_garantia);

    // Valor
    document.getElementById("detail-valor").textContent =
        formatearValor(activo.valor_adquisicion);

    // Abrir modal
    const modal = document.getElementById("asset-modal");

    if (modal) {
        modal.style.display = "flex";
    }
}

// =========================================================
// CERRAR MODAL
// =========================================================

function cerrarModalActivo() {

    document.getElementById("asset-modal").style.display = "none";
}


// =========================================================
// FORMATEAR FECHA
// =========================================================

function formatearFecha(fecha) {

    if (!fecha) {
        return "-";
    }

    const fechaObj = new Date(fecha);

    return fechaObj.toLocaleDateString("es-CL");
}


// =========================================================
// FORMATEAR VALOR
// =========================================================

function formatearValor(valor) {

    if (valor === null || valor === undefined) {
        return "-";
    }

    return Number(valor).toLocaleString("es-CL", {
        style: "currency",
        currency: "CLP",
        maximumFractionDigits: 0
    });
}

function formatearValorInput(valor) {
    const numeros = valor.replace(/\D/g, "");

    if (!numeros) {
        return "";
    }

    return Number(numeros).toLocaleString("es-CL");
}

document.addEventListener("DOMContentLoaded", () => {
    const valorInput = document.getElementById("register-valor");

    if (!valorInput) {
        return;
    }

    valorInput.addEventListener("input", () => {
        valorInput.value = formatearValorInput(valorInput.value);
    });
});







// =========================================================
// MODAL REGISTRAR ACTIVO
// =========================================================

function abrirModalRegistroActivo() {

    const modal = document.getElementById("register-asset-modal");

    if (!modal) {
        console.error("No se encontró el modal de registro.");
        return;
    }

    modal.style.display = "flex";
}


// =========================================================
// CERRAR MODAL REGISTRAR ACTIVO
// =========================================================

function cerrarModalRegistroActivo() {

    const modal = document.getElementById("register-asset-modal");

    if (!modal) {
        return;
    }

    modal.style.display = "none";
}



// =========================================================
// REGISTRAR MODELO
// =========================================================

async function cargarModelosRegistro() {

    const selectModelo = document.getElementById("register-modelo");

    if (!selectModelo) {
        return;
    }

    try {

        const response = await fetch("/api/activos/modelos/");

        if (!response.ok) {
            throw new Error("No se pudieron obtener los modelos.");
        }

        const modelos = await response.json();

        modelos.forEach(modelo => {

            const option = document.createElement("option");

            option.value = modelo.id_modelo;
            option.textContent = modelo.nombre;

            selectModelo.appendChild(option);
        });

    } catch (error) {

        console.error("Error al cargar modelos:", error);
    }
}


async function cargarUbicacionesRegistro() {

    const selectUbicacion = document.getElementById("register-ubicacion");

    if (!selectUbicacion) {
        return;
    }

    try {

        const response = await fetch("/api/activos/ubicaciones/");

        if (!response.ok) {
            throw new Error("No se pudieron obtener las ubicaciones.");
        }

        const ubicaciones = await response.json();

        ubicaciones.forEach(ubicacion => {

            const option = document.createElement("option");

            option.value = ubicacion.id_ubicacion;
            option.textContent = ubicacion.nombre_area;

            selectUbicacion.appendChild(option);
        });

    } catch (error) {

        console.error("Error al cargar ubicaciones:", error);
    }
}

async function cargarEstadosRegistro() {

    const selectEstado = document.getElementById("register-estado");

    if (!selectEstado) {
        return;
    }

    try {

        const response = await fetch("/api/activos/estados/");

        if (!response.ok) {
            throw new Error("No se pudieron obtener los estados.");
        }

        const estados = await response.json();

        estados.forEach(estado => {

            const option = document.createElement("option");

            option.value = estado.id_estado_activo;
            option.textContent = estado.nombre;

            selectEstado.appendChild(option);
        });

    } catch (error) {

        console.error("Error al cargar estados:", error);
    }
}



// =========================================================
// Funcion para registro conecte con bd api/activos
// =========================================================

document.addEventListener("DOMContentLoaded", () => {

    const registerForm = document.getElementById("register-asset-form");

    if (!registerForm) {
        return;
    }

    registerForm.addEventListener("submit", registrarActivo);
});


async function registrarActivo(event) {

    event.preventDefault();

    const form = event.target;

    const datos = {
        numero_serie: document.getElementById("register-serie").value.trim(),
        id_modelo: Number(document.getElementById("register-modelo").value),
        id_ubicacion: Number(document.getElementById("register-ubicacion").value),
        valor_adquisicion: document
            .getElementById("register-valor")
            .value
            .replace(/\./g, ""),
        fecha_garantia: document.getElementById("register-garantia").value || null
    };

    try {

        const response = await fetch("/api/activos/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(datos)
        });

        const resultado = await response.json();

        if (!response.ok) {

            console.error("Error al registrar activo:", resultado);

            mostrarNotificacion(
                "No fue posible registrar el activo.",
                "error"
            );

            return;
        }

        console.log("Activo registrado:", resultado);

        mostrarNotificacion(
            `Activo registrado correctamente. Código generado: ${resultado.codigo_inventario}`,
            "success"
        );

        form.reset();

        cerrarModalRegistroActivo();

        await cargarActivos();

    } catch (error) {

        console.error("Error al registrar activo:", error);

        mostrarNotificacion(
            "Ocurrió un error al conectar con el servidor.",
            "error"
        );
    }
}

function mostrarNotificacion(mensaje, tipo = "success") {

    const fondo = document.createElement("div");

    fondo.className = "notification-overlay";

    const notificacion = document.createElement("div");

    notificacion.className = `support-notification ${tipo}`;

    notificacion.textContent = mensaje;

    fondo.appendChild(notificacion);

    document.body.appendChild(fondo);

    setTimeout(() => {
        notificacion.classList.add("show");
    }, 10);

    setTimeout(() => {

        notificacion.classList.remove("show");
        fondo.classList.add("hide");

        setTimeout(() => {
            fondo.remove();
        }, 300);

    }, 3500);
}