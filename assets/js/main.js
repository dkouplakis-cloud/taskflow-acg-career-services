
"use strict";

/**
 * TaskFlow | ACG Career Services
 * Main application JavaScript
 */

/* Initialize application */
function initializeApp() {
  const statusElement =
    document.querySelector("#app-status");

  if (statusElement) {
    statusElement.textContent =
      "Application initialized successfully.";
  }

  initializeTheme();
  initializeMobileNavigation();

  console.info("TaskFlow initialized successfully.");
}

/* Dark mode functionality */
function initializeTheme() {
  const themeButton =
    document.querySelector(".theme-toggle");

  if (!themeButton) {
    return;
  }

  // Retrieve previously selected theme
  const savedTheme = localStorage.getItem("taskflow-theme");

  if (savedTheme === "dark") {
    document.documentElement.setAttribute(
      "data-theme",
      "dark"
    );
  }

  updateThemeButton(themeButton);

  // Toggle theme when button is clicked
  themeButton.addEventListener("click", () => {
    const currentTheme =
      document.documentElement.getAttribute("data-theme");

    const newTheme =
      currentTheme === "dark" ? "light" : "dark";

    document.documentElement.setAttribute(
      "data-theme",
      newTheme
    );

    localStorage.setItem("taskflow-theme", newTheme);

    updateThemeButton(themeButton);
  });
}

/* Update dark mode button */
function updateThemeButton(button) {
  const isDark =
    document.documentElement.getAttribute("data-theme")
    === "dark";

  button.textContent = isDark ? "Light Mode" : "Dark Mode";

  button.setAttribute(
    "aria-pressed",
    String(isDark)
  );
}

/* Mobile navigation functionality */
function initializeMobileNavigation() {
  const menuButton =
    document.querySelector(".menu-toggle");

  const navigation =
    document.querySelector(".main-navigation");

  if (!menuButton || !navigation) {
    return;
  }

  menuButton.addEventListener("click", () => {
    const isOpen =
      navigation.classList.toggle("is-open");

    menuButton.setAttribute(
      "aria-expanded",
      String(isOpen)
    );
  });

  // Close mobile menu after selecting a link
  navigation.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      navigation.classList.remove("is-open");

      menuButton.setAttribute(
        "aria-expanded",
        "false"
      );
    });
  });
}

/* Start application */
initializeApp();