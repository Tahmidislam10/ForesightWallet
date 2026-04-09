const chartData = JSON.parse(document.getElementById("trends-data").textContent);
const labels = chartData.labels;
const values = chartData.values;
const comparisonValues = chartData.comparisonValues;
const compareEnabled = chartData.compareEnabled;
const yearLabels = chartData.yearLabels;
const yearIncome = chartData.yearIncome;
const yearMonthlyAvg = chartData.yearMonthlyAvg;
const currentYearLabels = chartData.currentYearLabels;
const currentYearIncome = chartData.currentYearIncome;
const currentYearAvg = chartData.currentYearAvg;
const now = new Date();

const formattedLabels = labels.map(d => {
    const date = new Date(d);
    return date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
});

const monthNames = ['January','February','March','April','May','June','July','August','September','October','November','December'];
const selectedMonthIndex = parseInt(document.getElementById("trends-data").dataset.monthOption) - 1;
const prevMonthIndex = selectedMonthIndex === 0 ? 11 : selectedMonthIndex - 1;
const currentMonthName = monthNames[selectedMonthIndex];
const prevMonthName = monthNames[prevMonthIndex];

const incomeSeriesData = compareEnabled && comparisonValues.length > 0
    ? [{ name: currentMonthName, data: values }, { name: prevMonthName, data: comparisonValues }]
    : [{ name: currentMonthName, data: values }];

var incomeChart = new ApexCharts(document.querySelector("#incomeChart"), {
    chart: {
        type: 'area', height: 380,
        zoom: { enabled: true, type: 'x', autoScaleYaxis: true },
        animations: { enabled: true, easing: 'easeinout', speed: 600 },
        toolbar: { show: true, tools: { zoom: true, zoomin: true, zoomout: true, pan: true, reset: true, download: true } }
    },
    series: incomeSeriesData,
    xaxis: {
        categories: formattedLabels,
        title: { text: "Date" },
        labels: { rotate: -35, style: { fontSize: '11px' } },
        tickAmount: Math.min(labels.length, 15)
    },
    yaxis: {
        min: 0,
        max: values.every(v => v === 0) ? 10 : undefined,
        title: { text: "Amount (£)" },
        labels: { formatter: val => "£" + val.toFixed(2) }
    },
    stroke: { curve: 'smooth', width: 3 },
    colors: compareEnabled ? ['#1cc88a', '#a78bfa'] : ['#1cc88a'],
    fill: { type: 'gradient', gradient: { shadeIntensity: 1, opacityFrom: 0.45, opacityTo: 0.05, stops: [0, 100] } },
    markers: { size: 4, hover: { size: 7 } },
    tooltip: { shared: true, intersect: false, y: { formatter: val => "£" + val.toFixed(2) } },
    grid: { borderColor: '#e0e0e0', strokeDashArray: 4 },
    dataLabels: { enabled: false }
});
incomeChart.render();

function addIncomePdfMenuItem() {
    const menu = document.querySelector("#incomeChart .apexcharts-menu");
    if (menu && !menu.querySelector(".income-pdf-item")) {
        const pdfItem = document.createElement("div");
        pdfItem.className = "apexcharts-menu-item income-pdf-item";
        pdfItem.textContent = "Download PDF";
        pdfItem.addEventListener("click", async function() {
            try {
                const { jsPDF } = window.jspdf;
                const doc = new jsPDF({ orientation: "landscape", unit: "mm", format: "a4" });
                const pageW = doc.internal.pageSize.getWidth();
                const margin = 14;
                let y = margin;
                const chartEl = document.getElementById("incomeChart");
                const chartCanvas = await html2canvas(chartEl, { scale: 2, backgroundColor: "#ffffff", useCORS: true });
                const chartImg = chartCanvas.toDataURL("image/png");
                const chartW = pageW - margin * 2;
                const chartH = (chartCanvas.height / chartCanvas.width) * chartW;
                doc.setFontSize(12);
                doc.setFont("helvetica", "bold");
                doc.text("Income Trend", margin, y);
                y += 5;
                doc.addImage(chartImg, "PNG", margin, y, chartW, Math.min(chartH, 80));
                doc.save("income_trend.pdf");
            } catch(err) {
                console.error("PDF error:", err);
                alert("PDF generation failed. Please try again.");
            }
        });
        menu.appendChild(pdfItem);
    }
}

const incomeHamburger = document.querySelector("#incomeChart .apexcharts-toolbar");
if (incomeHamburger) {
    incomeHamburger.addEventListener("click", function() {
        setTimeout(addIncomePdfMenuItem, 50);
    });
}

document.getElementById("chartWrapper").addEventListener("wheel", e => {
    e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation();
}, { passive: false, capture: true });

let activeYearLabels = yearLabels;
let activeYearAvg = yearMonthlyAvg;

var yearChart = new ApexCharts(document.querySelector("#yearChart"), {
    chart: { type: 'bar', height: 380, toolbar: { show: true, tools: { zoom: false, zoomin: false, zoomout: false, pan: false, reset: false, download: true } }, animations: { enabled: true, easing: 'easeinout', speed: 600 } },
    series: [{ name: 'Income', data: yearIncome }],
    xaxis: { categories: yearLabels, title: { text: "Month" }, labels: { style: { fontSize: '11px' } } },
    yaxis: { min: 0, title: { text: "Amount (£)" }, labels: { formatter: val => "£" + val.toFixed(2) } },
    colors: ['#1cc88a'],
    plotOptions: { bar: { borderRadius: 6, columnWidth: '55%' } },
    annotations: {
        yaxis: [{ y: yearMonthlyAvg, borderColor: '#f97316', strokeDashArray: 6, borderWidth: 2,
            label: { text: `Avg: £${yearMonthlyAvg.toFixed(2)}`, style: { color: '#fff', background: '#f97316', fontSize: '11px' }, position: 'right', offsetX: -10 } }]
    },
    dataLabels: { enabled: false },
    tooltip: {
        custom: function({ series, seriesIndex, dataPointIndex }) {
            const month = activeYearLabels[dataPointIndex];
            const val = series[seriesIndex][dataPointIndex];
            const diff = val - activeYearAvg;
            const diffText = diff >= 0
                ? `<span style="color:#1cc88a">+£${diff.toFixed(2)} vs avg</span>`
                : `<span style="color:#e74a3b">-£${Math.abs(diff).toFixed(2)} vs avg</span>`;
            return `<div style="padding:10px 14px; font-size:13px;">
                <div style="font-weight:600; margin-bottom:4px;">${month}</div>
                <div>Income: <strong>£${val.toFixed(2)}</strong></div>
                <div>${diffText}</div>
            </div>`;
        }
    },
    grid: { borderColor: '#e0e0e0', strokeDashArray: 4 }
});
yearChart.render().then(function() {
    setTimeout(function() {
        const yearMenu = document.querySelector("#yearChart .apexcharts-menu");
        if (yearMenu) {
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
                    const yearEl = document.getElementById("yearChart");
                    const yearCanvas = await html2canvas(yearEl, { scale: 2, backgroundColor: "#ffffff", useCORS: true });
                    const yearImg = yearCanvas.toDataURL("image/png");
                    const chartW = pageW - margin * 2;
                    const chartH = (yearCanvas.height / yearCanvas.width) * chartW;
                    doc.setFontSize(12);
                    doc.setFont("helvetica", "bold");
                    doc.text("Year Overview — Income", margin, y);
                    y += 5;
                    doc.addImage(yearImg, "PNG", margin, y, chartW, Math.min(chartH, 80));
                    doc.save("year_overview_income.pdf");
                } catch(err) {
                    console.error("PDF error:", err);
                    alert("PDF generation failed. Please try again.");
                }
            });
            yearMenu.appendChild(pdfItem);
        }
    }, 500);
});

function updateYearChartForMode(mode) {
    const isCurrentYear = mode === 'currentyear';
    const data = isCurrentYear ? currentYearIncome : yearIncome;
    const labs = isCurrentYear ? currentYearLabels : yearLabels;
    const avg = isCurrentYear ? currentYearAvg : yearMonthlyAvg;
    activeYearLabels = labs;
    activeYearAvg = avg;
    yearChart.updateOptions({
        xaxis: { categories: labs },
        annotations: { yaxis: [{ y: avg, borderColor: '#f97316', strokeDashArray: 6, borderWidth: 2,
            label: { text: `Avg: £${avg.toFixed(2)}`, style: { color: '#fff', background: '#f97316', fontSize: '11px' }, position: 'right', offsetX: -10 } }] }
    });
    yearChart.updateSeries([{ name: 'Income', data: data }]);
    const periodLabel = isCurrentYear ? `${now.getFullYear()} · ` : 'Last 12 months · ';
    document.getElementById("yearSubtitle").innerHTML = `${periodLabel}Monthly avg: <strong>£${avg.toFixed(2)}</strong>`;
}

function switchYearView(mode) {
    if (mode === 'currentyear') {
        document.getElementById("btn12Months").className = "btn btn-sm btn-outline-secondary";
        document.getElementById("btnCurrentYear").className = "btn btn-sm btn-primary";
    } else {
        document.getElementById("btn12Months").className = "btn btn-sm btn-primary";
        document.getElementById("btnCurrentYear").className = "btn btn-sm btn-outline-secondary";
    }
    updateYearChartForMode(mode);
}

document.getElementById("rangeSelect").addEventListener("change", updatePage);
document.getElementById("monthSelect").addEventListener("change", updatePage);
document.getElementById("compareToggle").addEventListener("click", function() {
    const urlParams = new URLSearchParams(window.location.search);
    const compare = urlParams.get("compare") === "true";
    urlParams.set("compare", !compare);
    window.location.search = urlParams.toString();
});

function updatePage() {
    const range = document.getElementById("rangeSelect").value;
    const month = document.getElementById("monthSelect").value;
    let params = new URLSearchParams(window.location.search);
    params.set("range", range);
    params.set("month", month);
    window.location.search = params.toString();
}