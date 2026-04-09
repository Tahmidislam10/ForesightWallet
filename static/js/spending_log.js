document.addEventListener("DOMContentLoaded", function () {
    const chartCanvas = document.getElementById("categoryChart");
    const noChartDataMsg = document.getElementById("noChartDataMsg");
    const transactionsBody = document.getElementById("transactionsBody");
    const monthSelect = document.getElementById("monthSelect");
    const addEntryForm = document.getElementById("addEntryForm");
    const categorySelect = document.getElementById("categorySelect");
    const customInput = document.getElementById("customCategory");
    const filterButtons = document.querySelectorAll(".filter-btn");

    const stateEl = document.getElementById("spending-log-state");
    const currentState = {
        filter: stateEl.dataset.activeFilter,
        month: stateEl.dataset.activeMonth
    };

    let categoryChart = null;

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function setActiveFilterButton(activeFilter) {
        filterButtons.forEach((button) => {
            const isActive = button.dataset.filter === activeFilter;
            button.classList.toggle("btn-primary", isActive);
            button.classList.toggle("btn-outline-primary", !isActive);
        });
    }

    function renderTransactions(transactions) {
        if (!transactionsBody) return;

        if (!transactions || transactions.length === 0) {
            transactionsBody.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center text-muted">No transactions yet.</td>
                </tr>
            `;
            return;
        }

        transactionsBody.innerHTML = transactions.map((t) => `
            <tr data-id="${escapeHtml(t.id)}">
                <td class="date-cell">${escapeHtml(t.date)}</td>
                <td class="category-cell">${escapeHtml(t.category)}</td>
                <td class="description-cell">${escapeHtml(t.description)}</td>
                <td class="type-cell">
                    ${t.type === "expense"
                ? '<span class="badge bg-danger">Expense</span>'
                : '<span class="badge bg-success">Income</span>'}
                </td>
                <td class="amount-cell">£${escapeHtml(t.amount)}</td>
                <td class="text-end" style="white-space:nowrap;">
                    <button type="button" class="btn btn-sm btn-outline-primary me-1 edit-btn"><i class="bi bi-pencil"></i></button>
                    <button type="button" class="btn btn-sm btn-success me-1 save-btn" style="display:none;"><i class="bi bi-check-lg"></i></button>
                    <a href="/delete-transaction/${escapeHtml(t.id)}" class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></a>
                </td>
            </tr>
        `).join("");
    }

    function renderChart(labels, values) {
        if (!chartCanvas) return;

        const hasData = Array.isArray(values) && values.length > 0;

        chartCanvas.style.display = hasData ? "block" : "none";
        if (noChartDataMsg) {
            noChartDataMsg.style.display = hasData ? "none" : "block";
        }

        if (!hasData) {
            if (categoryChart) {
                categoryChart.destroy();
                categoryChart = null;
            }
            return;
        }

        if (typeof ApexCharts === "undefined") {
            chartCanvas.style.display = "none";
            if (noChartDataMsg) {
                noChartDataMsg.textContent = "Chart failed to load";
                noChartDataMsg.style.display = "block";
            }
            return;
        }

        if (categoryChart) {
            categoryChart.destroy();
        }

        const options = {
            series: values,
            chart: {
                type: 'donut',
                height: 350,
                animations: { enabled: true, easing: 'easeinout', speed: 800 }
            },
            labels: labels.map(l => String(l)),
            colors: ['#4e73df','#1cc88a','#36b9cc','#f6c23e','#e74a3b','#858796','#6610f2','#fd7e14','#20c997','#6f42c1'],
            legend: { position: 'bottom' },
            dataLabels: { enabled: false },
            plotOptions: {
                pie: {
                    donut: {
                        size: '65%',
                        labels: {
                            show: true,
                            value: {
                                formatter: function(val) { return '£' + parseFloat(val).toFixed(2); }
                            },
                            total: {
                                show: true,
                                label: 'Total',
                                formatter: function (w) {
                                    return '£' + parseFloat(w.globals.seriesTotals.reduce((a, b) => a + b, 0).toFixed(2)).toFixed(2);
                                }
                            }
                        }
                    }
                }
            },
            tooltip: {
                y: { formatter: function (val) { return "£" + val.toFixed(2); } }
            }
        };

        categoryChart = new ApexCharts(document.querySelector("#categoryChart"), options);
        categoryChart.render();
    }

    let incomeCategoryChart = null;

    function renderIncomeChart(labels, values) {
        const canvas = document.getElementById("incomeCategoryChart");
        const noMsg = document.getElementById("noIncomeChartMsg");
        const hasData = Array.isArray(values) && values.length > 0;
        if (canvas) canvas.style.display = hasData ? "block" : "none";
        if (noMsg) noMsg.style.display = hasData ? "none" : "block";
        if (!hasData) {
            if (incomeCategoryChart) { incomeCategoryChart.destroy(); incomeCategoryChart = null; }
            return;
        }
        if (incomeCategoryChart) incomeCategoryChart.destroy();
        incomeCategoryChart = new ApexCharts(document.querySelector("#incomeCategoryChart"), {
            series: values,
            chart: { type: 'donut', height: 350, animations: { enabled: true, easing: 'easeinout', speed: 800 } },
            labels: labels.map(l => String(l)),
            colors: ['#1cc88a','#2563eb','#36b9cc','#f6c23e','#6610f2','#fd7e14','#20c997','#6f42c1'],
            legend: { position: 'bottom' },
            dataLabels: { enabled: false },
            plotOptions: {
                pie: {
                    donut: {
                        size: '65%',
                        labels: {
                            show: true,
                            value: {
                                formatter: function(val) { return '£' + parseFloat(val).toFixed(2); }
                            },
                            total: {
                                show: true,
                                label: 'Total',
                                formatter: function(w) {
                                    return '£' + parseFloat(w.globals.seriesTotals.reduce((a, b) => a + b, 0).toFixed(2)).toFixed(2);
                                }
                            }
                        }
                    }
                }
            },
            tooltip: { y: { formatter: val => "£" + val.toFixed(2) } }
        });
        incomeCategoryChart.render();
    }

    async function loadSpendingData() {
        const params = new URLSearchParams();
        if (currentState.filter) params.set("filter", currentState.filter);
        if (currentState.month) params.set("month", currentState.month);
        params.set("format", "json");

        const response = await fetch(`/spending-log?${params.toString()}`, {
            headers: { "X-Requested-With": "XMLHttpRequest" }
        });
        if (!response.ok) return;

        const data = await response.json();
        renderTransactions(data.transactions || []);
        renderChart(data.chart_labels || [], data.chart_values || []);
        renderIncomeChart(data.income_chart_labels || [], data.income_chart_values || []);
        bindInlineEditHandlers();

        const activeFilter = data.active_filter || "all";
        currentState.filter = activeFilter;
        currentState.month = data.active_month ? String(data.active_month) : "";
        setActiveFilterButton(activeFilter);

        if (monthSelect) {
            monthSelect.value = currentState.month;
        }
    }

    function bindInlineEditHandlers() {
        document.querySelectorAll(".edit-btn").forEach((button) => {
            button.onclick = function () {
                const row = this.closest("tr");
                const id = row.dataset.id;

                const dateText = row.querySelector(".date-cell").innerText.trim();
                const categoryText = row.querySelector(".category-cell").innerText.trim();
                const descriptionText = row.querySelector(".description-cell").innerText.trim();
                const typeText = row.querySelector(".type-cell").innerText.trim();
                const amountText = row.querySelector(".amount-cell").innerText.replace(/[^\d.-]/g, "").trim();

                const dateParts = dateText.trim().split(" ");
                const months = {"Jan":"01","Feb":"02","Mar":"03","Apr":"04","May":"05","Jun":"06","Jul":"07","Aug":"08","Sep":"09","Oct":"10","Nov":"11","Dec":"12"};
                const formattedDate = `${dateParts[2]}-${months[dateParts[1]]}-${dateParts[0].padStart(2,"0")}`;

                row.querySelector(".date-cell").innerHTML =
                    `<input type="date" name="date" value="${formattedDate}" class="form-control form-control-sm" style="min-width:120px;">`;
                row.querySelector(".category-cell").innerHTML =
                    `<input type="text" name="category" value="${escapeHtml(categoryText)}" class="form-control form-control-sm" style="min-width:90px;">`;
                row.querySelector(".description-cell").innerHTML =
                    `<input type="text" name="description" value="${escapeHtml(descriptionText)}" class="form-control form-control-sm" style="min-width:100px;">`;
                row.querySelector(".type-cell").innerHTML =
                    `<select name="type" class="form-select form-select-sm" style="min-width:85px;">
                        <option value="expense" ${typeText.includes("Expense") ? "selected" : ""}>Expense</option>
                        <option value="income" ${typeText.includes("Income") ? "selected" : ""}>Income</option>
                    </select>`;
                row.querySelector(".amount-cell").innerHTML =
                    `<input type="number" step="0.01" name="amount" value="${amountText}" class="form-control form-control-sm" style="min-width:75px;">`;

                this.style.display = "none";
                const saveButton = row.querySelector(".save-btn");
                saveButton.style.display = "inline-block";

                saveButton.onclick = function () {
                    const formData = new FormData();
                    formData.append("date", row.querySelector("input[name='date']").value);
                    formData.append("category", row.querySelector("input[name='category']").value);
                    formData.append("description", row.querySelector("input[name='description']").value);
                    formData.append("type", row.querySelector("select[name='type']").value);
                    formData.append("amount", row.querySelector("input[name='amount']").value);

                    fetch(`/update-transaction/${id}`, {
                        method: "POST",
                        body: formData
                    }).then(() => loadSpendingData());
                };
            };
        });
    }

    if (categorySelect) {
        categorySelect.addEventListener("change", function () {
            if (this.value === "Other") {
                customInput.style.display = "block";
                customInput.required = true;
            } else {
                customInput.style.display = "none";
                customInput.required = false;
            }
        });
    }

    if (monthSelect) {
        monthSelect.addEventListener("change", function () {
            currentState.filter = "all";
            currentState.month = this.value;
            loadSpendingData();
        });
    }

    filterButtons.forEach((button) => {
        button.addEventListener("click", function (event) {
            event.preventDefault();
            currentState.filter = this.dataset.filter || "all";
            currentState.month = "";
            loadSpendingData();
        });
    });

    if (addEntryForm) {
        addEntryForm.addEventListener("submit", async function (event) {
            event.preventDefault();
            const response = await fetch("/spending-log", {
                method: "POST",
                body: new FormData(addEntryForm)
            });
            if (!response.ok) return;

            addEntryForm.reset();
            if (customInput) {
                customInput.style.display = "none";
                customInput.required = false;
            }
            await loadSpendingData();
        });
    }

    const initialLabels = chartCanvas ? JSON.parse(chartCanvas.dataset.labels || "[]") : [];
    const initialValues = chartCanvas ? JSON.parse(chartCanvas.dataset.values || "[]") : [];
    renderChart(initialLabels, initialValues);

    const incomeChartCanvas = document.getElementById("incomeCategoryChart");
    const initialIncomeLabels = incomeChartCanvas ? JSON.parse(incomeChartCanvas.dataset.labels || "[]") : [];
    const initialIncomeValues = incomeChartCanvas ? JSON.parse(incomeChartCanvas.dataset.values || "[]") : [];
    renderIncomeChart(initialIncomeLabels, initialIncomeValues);

    bindInlineEditHandlers();
    setActiveFilterButton(currentState.filter || "all");
});