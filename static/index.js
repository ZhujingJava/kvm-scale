document.addEventListener("DOMContentLoaded", function () {
    const refreshBtn = document.getElementById("refresh-btn");
    if (refreshBtn) {
        refreshBtn.addEventListener("click", () => {
            location.reload();
        });
    }
});