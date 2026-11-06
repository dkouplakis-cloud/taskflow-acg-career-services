
"use strict";

/**
 * TaskFlow | ACG Career Services
 * Main application JavaScript
 *
 * Features:
 * - Application initialization
 * - Persistent dark/light mode
 * - Responsive mobile navigation
 * - Dynamic dashboard statistics
 */

/**
 * Initialize the application and its features.
 */
function initializeApp() {
  const statusElement = document.querySelector("#app-status");

  if (statusElement) {
    statusElement.textContent =
      "Application initialized successfully.";
  }

  initializeTheme();
  initializeMobileNavigation();
  updateDashboardStatistics();

  console.info("TaskFlow initialized successfully.");
}

/**
 * Initialize the dark/light theme.
 * The selected theme is stored in localStorage.
 */
function initializeTheme() {
  const themeButton = document.querySelector(".theme-toggle");

  if (!themeButton) {
    return;
  }

  // Retrieve the previously selected theme.
  const savedTheme = localStorage.getItem("taskflow-theme");

  if (savedTheme === "dark") {
    document.documentElement.setAttribute(
      "data-theme",
      "dark"
    );
  }

  updateThemeButton(themeButton);

  // Switch between light and dark mode.
  themeButton.addEventListener("click", () => {
    const currentTheme =
      document.documentElement.getAttribute("data-theme");

    const newTheme =
      currentTheme === "dark" ? "light" : "dark";

    document.documentElement.setAttribute(
      "data-theme",
      newTheme
    );

    // Save the selected theme for future visits.
    localStorage.setItem("taskflow-theme", newTheme);

    updateThemeButton(themeButton);
  });
}

/**
 * Update the theme button's label and accessibility state.
 *
 * @param {HTMLButtonElement} button - Theme toggle button.
 */
function updateThemeButton(button) {
  const isDark =
    document.documentElement.getAttribute("data-theme") ===
    "dark";

  button.textContent = isDark ? "Light Mode" : "Dark Mode";

  button.setAttribute("aria-pressed", String(isDark));
}

/**
 * Initialize responsive mobile navigation.
 */
function initializeMobileNavigation() {
  const menuButton = document.querySelector(".menu-toggle");
  const navigation = document.querySelector(".main-navigation");

  if (!menuButton || !navigation) {
    return;
  }

  // Open or close the navigation menu.
  menuButton.addEventListener("click", () => {
    const isOpen = navigation.classList.toggle("is-open");

    menuButton.setAttribute(
      "aria-expanded",
      String(isOpen)
    );
  });

  // Close the menu when a navigation link is selected.
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

/**
 * Retrieve saved tasks from localStorage.
 *
 * @returns {Array} An array of saved tasks.
 */
function getSavedTasks() {
  try {
    // Use the same storage key as the task management module.
    const storedTasks = localStorage.getItem("taskflow-tasks");

    if (!storedTasks) {
      return [];
    }

    const tasks = JSON.parse(storedTasks);

    // Ensure the retrieved value is an array.
    return Array.isArray(tasks) ? tasks : [];
  } catch (error) {
    console.error("Unable to load saved tasks:", error);

    return [];
  }
}

/**
 * Calculate and display dashboard statistics.
 *
 * Statistics are based on the tasks saved in localStorage.
 */
function updateDashboardStatistics() {
  const totalElement = document.querySelector(
    '[data-stat="total"]'
  );

  const pendingElement = document.querySelector(
    '[data-stat="pending"]'
  );

  const progressElement = document.querySelector(
    '[data-stat="progress"]'
  );

  const completedElement = document.querySelector(
    '[data-stat="completed"]'
  );

  // Dashboard statistics are only displayed on the homepage.
  if (
    !totalElement ||
    !pendingElement ||
    !progressElement ||
    !completedElement
  ) {
    return;
  }

  // Retrieve all saved tasks.
  const tasks = getSavedTasks();

  // Calculate the total number of tasks.
  const totalTasks = tasks.length;

  // Count tasks according to their current status.
  const pendingTasks = tasks.filter(
    (task) => task.status === "pending"
  ).length;

  const progressTasks = tasks.filter(
    (task) => task.status === "progress"
  ).length;

  const completedTasks = tasks.filter(
    (task) => task.status === "completed"
  ).length;

  // Update the dashboard elements.
  totalElement.textContent = String(totalTasks);
  pendingElement.textContent = String(pendingTasks);
  progressElement.textContent = String(progressTasks);
  completedElement.textContent = String(completedTasks);
}

<script type="module" src="assets/js/about.js"></script>
/**
 * Start the application.
 */
initializeApp();
