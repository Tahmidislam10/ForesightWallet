document.addEventListener("DOMContentLoaded", function () {

    // Line Chart
    const trendCtx = document.getElementById('trendChart');
    if (trendCtx) {
        new Chart(trendCtx, {
            type: 'line',
            data: {
                labels: ['Week 1', 'Week 2', 'Week 3', 'Week 4'],
                datasets: [{
                    label: 'Spending (£)',
                    data: [300, 450, 400, 500],
                    borderWidth: 2,
                    tension: 0.3
                }]
            }
        });
    }

    // Pie Chart
    const categoryCtx = document.getElementById('categoryChart');
    if (categoryCtx) {
        new Chart(categoryCtx, {
            type: 'pie',
            data: {
                labels: ['Food', 'Travel', 'Bills', 'Leisure'],
                datasets: [{
                    data: [400, 200, 500, 350]
                }]
            }
        });
    }

});