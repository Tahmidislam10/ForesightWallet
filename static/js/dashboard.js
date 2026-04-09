function updateKpiMonth() {
    const month = document.getElementById("kpiMonthSelect").value;
    const params = new URLSearchParams(window.location.search);
    params.set("kpi_month", month);
    window.location.search = params.toString();
}

function updateTotalsMonth() {
    const month = document.getElementById("totalsMonthSelect").value;
    const params = new URLSearchParams(window.location.search);
    params.set("totals_month", month);
    window.location.search = params.toString();
}

// Donut charts
const deductionsRaw = JSON.parse(document.getElementById("deductions-data").textContent);

function renderDonut(elementId, data, colors) {
    const labels = Object.keys(data).filter(k => data[k] > 0);
    const values = labels.map(k => data[k]);
    if (labels.length === 0) return;
    var chart = new ApexCharts(document.querySelector(elementId), {
        chart: { type: 'donut', height: 220, toolbar: { show: false } },
        series: values,
        labels: labels,
        colors: colors,
        legend: { position: 'bottom', fontSize: '11px' },
        dataLabels: { enabled: false },
        tooltip: { y: { formatter: val => "£" + val.toFixed(2) } },
        plotOptions: {
            pie: {
                donut: {
                    size: '60%',
                    labels: {
                        show: true,
                        total: {
                            show: true,
                            label: 'Total',
                            formatter: () => '£' + values.reduce((a,b) => a+b, 0).toFixed(2)
                        }
                    }
                }
            }
        }
    });
    chart.render();
}

renderDonut('#savingsDonut', deductionsRaw.savings, ['#059669', '#34d399', '#6ee7b7', '#a7f3d0']);
renderDonut('#billsDonut', deductionsRaw.bills, ['#2563eb', '#60a5fa', '#93c5fd', '#bfdbfe']);
renderDonut('#debtsDonut', deductionsRaw.debts, ['#dc2626', '#f87171', '#fca5a5', '#fecaca']);

// Bar chart
const barData = JSON.parse(document.getElementById("dashboard-bar-data").textContent);

var barChart = new ApexCharts(document.querySelector("#incomeExpenseChart"), {
    chart: { type: 'bar', height: 300, toolbar: { show: false } },
    series: [
        { name: 'Income', data: barData.income },
        { name: 'Expenses', data: barData.expenses }
    ],
    xaxis: { categories: barData.labels },
    yaxis: { labels: { formatter: val => "£" + val.toFixed(0) } },
    colors: ['#1cc88a', '#e74a3b'],
    plotOptions: { bar: { borderRadius: 4, columnWidth: '50%' } },
    dataLabels: { enabled: false },
    legend: { position: 'top', horizontalAlign: 'right' },
    tooltip: { y: { formatter: val => "£" + val.toFixed(2) } },
    grid: { borderColor: '#f1f5f9', strokeDashArray: 4 }
});

barChart.render();