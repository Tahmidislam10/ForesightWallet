function switchFeature(value) {
    document.getElementById("placeholderCard").classList.add("d-none");
    document.getElementById("forecastSection").classList.add("d-none");
    document.getElementById("categorySection").classList.add("d-none");
    document.getElementById("clusteringSection").classList.add("d-none");

    if (value === "forecast") {
        document.getElementById("forecastSection").classList.remove("d-none");
    } else if (value === "category") {
        document.getElementById("categorySection").classList.remove("d-none");
    } else if (value === "clustering") {
        document.getElementById("clusteringSection").classList.remove("d-none");
    } else {
        document.getElementById("placeholderCard").classList.remove("d-none");
    }
}

window.addEventListener("DOMContentLoaded", function() {
    const selector = document.getElementById("featureSelector");
    if (selector.value) {
        switchFeature(selector.value);
    }
});