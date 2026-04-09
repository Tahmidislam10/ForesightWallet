// Apply progress bar width from data attributes
document.querySelectorAll(".progress-bar[data-width]").forEach(bar => {
    const width = bar.dataset.width;
    bar.style.width = width + "%";
    bar.style.borderRadius = "8px";
});

document.querySelectorAll(".edit-toggle").forEach(btn => {
    btn.addEventListener("click", function () {
        const section = this.dataset.section;
        const form = document.getElementById(`${section}Form`);
        const isEditing = form.classList.contains("editing");
        if (isEditing) {
            form.classList.remove("editing");
            form.querySelectorAll(".edit-cell").forEach(el => {
                el.style.display = "none";
                el.querySelectorAll("input, button").forEach(i => i.disabled = true);
            });
            form.querySelectorAll(".view-cell").forEach(el => {
                el.style.display = "";
                el.querySelectorAll("input").forEach(i => i.disabled = false);
            });
            this.innerHTML = '<i class="bi bi-pencil"></i> Edit';
            this.classList.remove("btn-warning");
            this.classList.add("btn-outline-primary");
        } else {
            form.classList.add("editing");
            form.querySelectorAll(".edit-cell").forEach(el => {
                el.style.display = "";
                el.querySelectorAll("input, button").forEach(i => i.disabled = false);
            });
            form.querySelectorAll(".view-cell").forEach(el => {
                el.style.display = "none";
                el.querySelectorAll("input").forEach(i => i.disabled = true);
            });
            this.innerHTML = '✕ Cancel';
            this.classList.remove("btn-outline-primary");
            this.classList.add("btn-warning");
        }
    });
});

const placeholders = {
    savings: "e.g. Pension Fund",
    bills: "e.g. Council Tax",
    debts: "e.g. Car Finance"
};

document.querySelectorAll(".add-row").forEach(btn => {
    btn.addEventListener("click", function () {
        const tableId = this.dataset.table;
        const section = this.dataset.section;
        const tbody = document.querySelector(`#${tableId} tbody`);
        const placeholder = placeholders[section] || "Name";
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td class="edit-cell ps-0">
                <input type="text" name="${section}_key" class="form-control form-control-sm" placeholder="${placeholder}">
            </td>
            <td>
                <input type="number" name="${section}_val" step="0.01" class="form-control form-control-sm text-end" value="0.00">
            </td>
            <td class="edit-cell" style="width:40px;">
                <button type="button" class="btn btn-sm btn-outline-danger remove-row">🗑</button>
            </td>
        `;
        tbody.appendChild(tr);
        tr.querySelector(".remove-row").addEventListener("click", function () {
            this.closest("tr").remove();
        });
    });
});

document.querySelectorAll(".remove-row").forEach(btn => {
    btn.addEventListener("click", function () {
        this.closest("tr").remove();
    });
});