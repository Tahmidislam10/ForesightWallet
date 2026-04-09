const forecastRaw = JSON.parse(document.getElementById("forecast-data").textContent);

const formatLabel = d => {
    const date = new Date(d + "T00:00:00");
    return date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
};

const allLabels = [...forecastRaw.actualLabels, ...forecastRaw.predictedLabels];
const categories = allLabels.map(formatLabel);

const lastActual = forecastRaw.actualValues[forecastRaw.actualValues.length - 1];
const actualFull = [
    ...forecastRaw.actualValues,
    ...new Array(forecastRaw.predictedLabels.length).fill(null)
];
const predictedFull = [
    ...new Array(forecastRaw.actualValues.length - 1).fill(null),
    lastActual,
    ...forecastRaw.predictedValues
];

const series = [
    { name: "Actual (this month)", data: actualFull },
    { name: "Predicted (next 30 days)", data: predictedFull }
];

var forecastChart = new ApexCharts(document.querySelector("#forecastChart"), {
    chart: {
        type: 'area',
        height: 380,
        toolbar: { show: true, tools: { zoom: false, zoomin: false, zoomout: false, pan: false, reset: false, download: true } },
        animations: { enabled: true, easing: 'easeinout', speed: 600 }
    },
    series: series,
    xaxis: {
        categories: categories,
        title: { text: "Date" },
        labels: { rotate: -35, style: { fontSize: '11px' } },
        tickAmount: Math.min(categories.length, 20)
    },
    yaxis: {
        min: 0,
        title: { text: "Amount (£)" },
        labels: { formatter: val => val !== null ? "£" + val.toFixed(2) : "" }
    },
    stroke: { curve: 'smooth', width: 3 },
    colors: ['#3b82f6', '#f97316'],
    fill: {
        type: 'gradient',
        gradient: { shadeIntensity: 1, opacityFrom: 0.45, opacityTo: 0.05, stops: [0, 100] }
    },
    markers: { size: 4, hover: { size: 7 } },
    legend: { position: 'top' },
    tooltip: {
        shared: true,
        intersect: false,
        y: { formatter: val => val !== null ? "£" + val.toFixed(2) : "No data" }
    },
    grid: { borderColor: '#e0e0e0', strokeDashArray: 4 },
    dataLabels: { enabled: false }
});
forecastChart.render().then(function() {
    setTimeout(function() {
        const menu = document.querySelector("#forecastChart .apexcharts-menu");
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
                    const chartEl = document.getElementById("forecastChart");
                    const chartCanvas = await html2canvas(chartEl, { scale: 2, backgroundColor: "#ffffff", useCORS: true });
                    const chartImg = chartCanvas.toDataURL("image/png");
                    const chartW = pageW - margin * 2;
                    const chartH = (chartCanvas.height / chartCanvas.width) * chartW;
                    doc.setFontSize(12);
                    doc.setFont("helvetica", "bold");
                    doc.text("Spending Forecast", margin, y);
                    y += 5;
                    doc.addImage(chartImg, "PNG", margin, y, chartW, Math.min(chartH, 80));
                    doc.save("spending_forecast.pdf");
                } catch(err) {
                    console.error("PDF error:", err);
                    alert("PDF generation failed. Please try again.");
                }
            });
            menu.appendChild(pdfItem);
        }
    }, 500);
});