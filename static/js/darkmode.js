document.addEventListener("DOMContentLoaded", () => {
    const toggle = document.getElementById("darkModeToggle");
    if (!toggle) return;

    // apply saved theme
    if (localStorage.getItem("theme") === "dark") {
        document.documentElement.classList.add("dark");
    }

    toggle.addEventListener("click", () => {
        document.documentElement.classList.toggle("dark");

        localStorage.setItem(
            "theme",
            document.documentElement.classList.contains("dark") ? "dark" : "light"
        );
    });
});
