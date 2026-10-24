"use strict";

// Solicita revisión antes de guardar y evita reenvíos mientras se procesa el formulario.
(() => {
    const modal = document.getElementById("confirmacion-operacion");
    if (!(modal instanceof HTMLDialogElement)) return;
    const pregunta = document.getElementById("confirmacion-pregunta");
    const resumen = document.getElementById("confirmacion-resumen");
    const cancelar = document.getElementById("confirmacion-cancelar");
    const confirmar = document.getElementById("confirmacion-aceptar");
    let pendiente = null;

    function restaurar(form) {
        delete form.dataset.enviando;
        delete form.dataset.confirmado;
        form.querySelectorAll("[data-bloqueado-confirmacion]").forEach((boton) => {
            boton.disabled = false;
            delete boton.dataset.bloqueadoConfirmacion;
        });
    }

    document.addEventListener("submit", (event) => {
        const form = event.target;
        if (!(form instanceof HTMLFormElement) || !form.dataset.confirm || event.defaultPrevented) return;
        if (form.dataset.enviando === "true") {
            event.preventDefault();
            return;
        }
        if (form.dataset.confirmado === "true") {
            delete form.dataset.confirmado;
            form.dataset.enviando = "true";
            form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach((boton) => {
                if (!boton.disabled) {
                    boton.dataset.bloqueadoConfirmacion = "true";
                    boton.disabled = true;
                }
            });
            return;
        }
        event.preventDefault();
        if (pendiente) return;
        const campos = Array.from(form.elements).filter((campo) =>
            campo.name && campo.name !== "csrfmiddlewaretoken" && !campo.disabled &&
            !["hidden", "submit", "button", "reset", "password"].includes(campo.type) &&
            (!["checkbox", "radio"].includes(campo.type) || campo.checked)
        );
        pregunta.textContent = form.dataset.confirm;
        resumen.replaceChildren();
        campos.forEach((campo) => {
            const etiqueta = campo.labels?.[0]?.textContent?.trim() || campo.name;
            const valor = campo instanceof HTMLSelectElement
                ? Array.from(campo.selectedOptions).map((opcion) => opcion.textContent.trim()).join(", ")
                : campo.value.trim();
            if (!valor) return;
            const termino = document.createElement("dt");
            const detalle = document.createElement("dd");
            termino.textContent = etiqueta;
            detalle.textContent = valor;
            resumen.append(termino, detalle);
        });
        resumen.hidden = !resumen.children.length;
        pendiente = { form, boton: event.submitter };
        modal.showModal();
        cancelar.focus();
    });

    cancelar.addEventListener("click", () => modal.close());
    modal.addEventListener("close", () => {
        const origen = pendiente?.boton;
        pendiente = null;
        if (origen?.isConnected) origen.focus();
    });
    confirmar.addEventListener("click", () => {
        if (!pendiente) return;
        const { form, boton } = pendiente;
        pendiente = null;
        modal.close();
        form.dataset.confirmado = "true";
        try {
            if (boton && boton.form === form && !boton.disabled) form.requestSubmit(boton);
            else form.requestSubmit();
        } finally {
            delete form.dataset.confirmado;
        }
    });

    window.addEventListener("pageshow", () => {
        pendiente = null;
        if (modal.open) modal.close();
        document.querySelectorAll("form[data-confirm]").forEach(restaurar);
    });
})();
