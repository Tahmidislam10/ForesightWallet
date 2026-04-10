document.getElementById("sidebarToggle").addEventListener("click", function () {
    const sidebar = document.getElementById("sidebar");
    const overlay = document.getElementById("sidebarOverlay");
    const isMobile = window.innerWidth <= 768;

    if (isMobile) {
        sidebar.classList.toggle("mobile-open");
        overlay.classList.toggle("active");
    } else {
        sidebar.classList.toggle("collapsed");
    }
});

function closeSidebarMobile() {
    document.getElementById("sidebar").classList.remove("mobile-open");
    document.getElementById("sidebarOverlay").classList.remove("active");
}

document.querySelectorAll(".sidebar a").forEach(function (link) {
    link.addEventListener("click", function () {
        if (window.innerWidth <= 768) {
            closeSidebarMobile();
        }
    });
});

window.addEventListener("resize", function () {
    if (window.innerWidth > 768) {
        document.getElementById("sidebar").classList.remove("mobile-open");
        document.getElementById("sidebarOverlay").classList.remove("active");
    }
});