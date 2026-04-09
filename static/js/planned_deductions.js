const deductionsData = JSON.parse(document.getElementById("deductions-data").textContent);

function buildDeductionsSeries(data) {
    return [
        { name: 'Savings', data: data.map(d => d.savings) },
        { name: 'Bills', data: data.map(d => d.bills) },
        { name: 'Debts', data: data.map(d => d.debts) }
    ];
}

function buildDeductionsLabels(data) { return data.map(d => d.label); }

var deductionsChart = new ApexCharts(document.querySelector("#deductionsChart"), {
    chart: { type: 'bar', height: 350, stacked: true, toolbar: { show: true, tools: { zoom: false, zoomin: false, zoomout: false, pan: false, reset: false, download: true } }, animations: { enabled: true, easing: 'easeinout', speed: 600 } },
    series: buildDeductionsSeries(deductionsData.deductions6m),
    xaxis: { categories: buildDeductionsLabels(deductionsData.deductions6m), title: { text: "Month" } },
    yaxis: { min: 0, title: { text: "Amount (£)" }, labels: { formatter: val => "£" + val.toFixed(2) } },
    colors: ['#1cc88a', '#3b82f6', '#e74a3b'],
    plotOptions: { bar: { borderRadius: 4, columnWidth: '55%' } },
    dataLabels: { enabled: false },
    legend: { position: 'top' },
    tooltip: { y: { formatter: val => "£" + val.toFixed(2) } },
    grid: { borderColor: '#e0e0e0', strokeDashArray: 4 }
});
deductionsChart.render().then(function() {
    setTimeout(function() {
        const menu = document.querySelector("#deductionsChart .apexcharts-menu");
        if (menu) {
            const pdfItem = document.createElement("div");
            pdfItem.className = "apexcharts-menu-item";
            pdfItem.textContent = "Download PDF";
            pdfItem.addEventListener("click", async function() {
                try {
                    const { jsPDF } = window.jspdf;
                    const doc = new jsPDF({ orientation: "landscape", unit: "mm", format: "a4" });
                    const pageW = doc.internal.pageSize.getWidth();
                    const margin = 14;
                    let y = margin;
                    const chartEl = document.getElementById("deductionsChart");
                    const chartCanvas = await html2canvas(chartEl, { scale: 2, backgroundColor: "#ffffff", useCORS: true });
                    const chartImg = chartCanvas.toDataURL("image/png");
                    const chartW = pageW - margin * 2;
                    const chartH = (chartCanvas.height / chartCanvas.width) * chartW;
                    doc.setFontSize(12);
                    doc.setFont("helvetica", "bold");
                    doc.text("Planned Deductions Breakdown", margin, y);
                    y += 5;
                    doc.addImage(chartImg, "PNG", margin, y, chartW, Math.min(chartH, 80));
                    doc.save("planned_deductions.pdf");
                } catch(err) {
                    console.error("PDF error:", err);
                    alert("PDF generation failed. Please try again.");
                }
            });
            menu.appendChild(pdfItem);
        }
    }, 500);
});

function renderSummarySection(containerId, data, colorClass, emptyMsg) {
    const container = document.getElementById(containerId);
    container.innerHTML = "";
    if (!data || Object.keys(data).length === 0) {
        container.innerHTML = `<p class="text-muted small">${emptyMsg}</p>`;
    } else {
        Object.entries(data).forEach(([key, val]) => {
            const item = document.createElement("div");
            item.className = "d-flex justify-content-between align-items-center p-2 rounded mb-1";
            item.style.background = "#f8f9fa";
            item.innerHTML = `<span class="small">${key}</span><span class="fw-semibold ${colorClass} small">£${val.toFixed(2)}</span>`;
            container.appendChild(item);
        });
    }
}

function renderSummary(summary) {
    renderSummarySection("savingsSummaryItems", summary.savings, "text-success", "No savings data.");
    renderSummarySection("billsSummaryItems", summary.bills, "text-primary", "No bills data.");
    renderSummarySection("debtsSummaryItems", summary.debts, "text-danger", "No debt data.");
    document.getElementById("summaryBillsTotal").textContent = `£${summary.bills_total.toFixed(2)}`;
    document.getElementById("summaryDebtsTotal").textContent = `£${summary.debts_total.toFixed(2)}`;
}

function switchDeductionsView(mode, year) {
    let data, summary, subtitle;
    if (mode === '6m') {
        data = deductionsData.deductions6m; summary = deductionsData.summary6m;
        subtitle = 'Last 6 months · Savings, Bills & Debt';
        document.getElementById("deductions6mBtn").className = "btn btn-sm btn-primary";
        document.getElementById("deductions12mBtn").className = "btn btn-sm btn-outline-secondary";
        document.getElementById("deductionsYearBtn").textContent = "By Year";
    } else if (mode === '12m') {
        data = deductionsData.deductions12m; summary = deductionsData.summary12m;
        subtitle = 'Last 12 months · Savings, Bills & Debt';
        document.getElementById("deductions6mBtn").className = "btn btn-sm btn-outline-secondary";
        document.getElementById("deductions12mBtn").className = "btn btn-sm btn-primary";
        document.getElementById("deductionsYearBtn").textContent = "By Year";
    } else if (mode === 'year') {
        data = deductionsData.deductionsByYear[year]; summary = deductionsData.summaryByYear[year];
        subtitle = `${year} · Savings, Bills & Debt`;
        document.getElementById("deductions6mBtn").className = "btn btn-sm btn-outline-secondary";
        document.getElementById("deductions12mBtn").className = "btn btn-sm btn-outline-secondary";
        document.getElementById("deductionsYearBtn").textContent = year;
    }
    deductionsChart.updateOptions({ xaxis: { categories: buildDeductionsLabels(data) } });
    deductionsChart.updateSeries(buildDeductionsSeries(data));
    document.getElementById("deductionsSubtitle").textContent = subtitle;
    renderSummary(summary);
}

renderSummary(deductionsData.summary6m);