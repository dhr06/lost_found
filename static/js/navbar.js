document.addEventListener("DOMContentLoaded", () => {
    const loginBtn = document.getElementById("loginBtn");
    const logoutBtn = document.getElementById("logoutBtn");

    if (!loginBtn || !logoutBtn) return;

    const token = localStorage.getItem("token");

    if (token) {
        loginBtn.classList.add("hidden");
        logoutBtn.classList.remove("hidden");
    } else {
        loginBtn.classList.remove("hidden");
        logoutBtn.classList.add("hidden");
    }

    logoutBtn.addEventListener("click", () => {
        localStorage.removeItem("token");
        localStorage.removeItem("user");
        window.location.href = "login.html";
    });
});
