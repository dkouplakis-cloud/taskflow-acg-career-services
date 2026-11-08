
"use strict";

/**
 * TaskFlow | ACG Career Services
 * Main Application JavaScript
 *
 * Features:
 * - Application initialization
 * - Persistent dark/light mode
 * - Responsive mobile navigation
 * - Dynamic dashboard statistics
 * - Cross-tab synchronization
 * - Safe localStorage access
 */

// ========================================
// CONFIGURATION
// ========================================

const TASKS_STORAGE_KEY = "taskflow-tasks";
const THEME_STORAGE_KEY = "taskflow-theme";

// ========================================
// SAFE STORAGE HELPERS
// ========================================

/**
 * Safely retrieve a value from localStorage.
 */
function getStoredValue(key) {
  try {
    return localStorage.getItem(key);
  } catch (error) {
    console.warn(
      `Unable to read localStorage key: ${key}`,
      error
    );

    return null;
  }
}

/**
 * Safely save a value to localStorage.
 */
function setStoredValue(key, value) {
  try {
    localStorage.setItem(key, value);
    return true;
  } catch (error) {
    console.warn(
      `Unable to save localStorage key: ${key}`,
      error
    );

    return false;
  }
}

// ========================================
// DARK MODE
// ========================================

/**
 * Update the theme button's text and
 * accessibility state.
 */
function updateThemeButton(button) {
  const isDark =
    document.documentElement.getAttribute(
      "data-theme"
    ) === "dark";

  button.textContent =
    isDark ? "Light Mode" : "Dark Mode";

  button.setAttribute(
    "aria-pressed",
    String(isDark)
  );
}

/**
 * Initialize persistent dark/light mode.
 */
function initializeTheme() {
  const themeButton = document.querySelector(
    ".theme-toggle"
  );

  const savedTheme = getStoredValue(
    THEME_STORAGE_KEY
  );

  if (savedTheme === "dark") {
    document.documentElement.setAttribute(
      "data-theme",
      "dark"
    );
  } else {
    document.documentElement.setAttribute(
      "data-theme",
      "light"
    );
  }

  if (!themeButton) {
    return;
  }

  updateThemeButton(themeButton);

  themeButton.addEventListener("click", () => {
    const currentTheme =
      document.documentElement.getAttribute(
        "data-theme"
      );

    const newTheme =
      currentTheme === "dark"
        ? "light"
        : "dark";

    document.documentElement.setAttribute(
      "data-theme",
      newTheme
    );

    setStoredValue(
      THEME_STORAGE_KEY,
      newTheme
    );

    updateThemeButton(themeButton);
  });
}

// ========================================
// MOBILE NAVIGATION
// ========================================

/**
 * Initialize responsive navigation.
 */
function initializeMobileNavigation() {
  const menuButton = document.querySelector(
    ".menu-toggle"
  );

  const navigation = document.querySelector(
    ".main-navigation"
  );

  if (!menuButton || !navigation) {
    return;
  }

  /**
   * Open or close the mobile menu.
   */
  function setMenuState(isOpen) {
    navigation.classList.toggle(
      "is-open",
      isOpen
    );

    menuButton.setAttribute(
      "aria-expanded",
      String(isOpen)
    );
  }

  menuButton.addEventListener("click", () => {
    const isOpen = navigation.classList.contains(
      "is-open"
    );

    setMenuState(!isOpen);
  });

  /**
   * Close navigation when a link is selected.
   */
  navigation.querySelectorAll("a").forEach(
    (link) => {
      link.addEventListener("click", () => {
        setMenuState(false);
      });
    }
  );

  /**
   * Close navigation using Escape.
   */
  document.addEventListener("keydown", (event) => {
    if (
      event.key === "Escape" &&
      navigation.classList.contains("is-open")
    ) {
      setMenuState(false);
      menuButton.focus();
    }
  });

  /**
   * Close the mobile menu when returning
   * to desktop screen width.
   */
  window.addEventListener("resize", () => {
    if (window.innerWidth > 700) {
      setMenuState(false);
    }
  });
}

// ========================================
// TASK STORAGE
// ========================================

/**
 * Retrieve saved tasks from localStorage.
 */
function getSavedTasks() {
  const storedTasks = getStoredValue(
    TASKS_STORAGE_KEY
  );

  if (!storedTasks) {
    return [];
  }

  try {
    const tasks = JSON.parse(storedTasks);

    if (!Array.isArray(tasks)) {
      return [];
    }

    return tasks.filter(
      (task) =>
        task !== null &&
        typeof task === "object" &&
        !Array.isArray(task)
    );
  } catch (error) {
    console.error(
      "Unable to parse saved tasks:",
      error
    );

    return [];
  }
}

// ========================================
// DASHBOARD STATISTICS
// ========================================

/**
 * Calculate and display task statistics.
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

  // Only update pages containing dashboard cards.
  if (
    !totalElement ||
    !pendingElement ||
    !progressElement ||
    !completedElement
  ) {
    return;
  }

  const tasks = getSavedTasks();

  const totalTasks = tasks.length;

  const pendingTasks = tasks.filter(
    (task) => task.status === "pending"
  ).length;

  const progressTasks = tasks.filter(
    (task) => task.status === "progress"
  ).length;

  const completedTasks = tasks.filter(
    (task) => task.status === "completed"
  ).length;

  totalElement.textContent = String(
    totalTasks
  );

  pendingElement.textContent = String(
    pendingTasks
  );

  progressElement.textContent = String(
    progressTasks
  );

  completedElement.textContent = String(
    completedTasks
  );
}

// ========================================
// CROSS-TAB SYNCHRONIZATION
// ========================================

/**
 * Refresh statistics when tasks are changed
 * in another browser tab.
 */
function initializeStorageSynchronization() {
  window.addEventListener("storage", (event) => {
    if (event.key === TASKS_STORAGE_KEY) {
      updateDashboardStatistics();
    }

    if (event.key === THEME_STORAGE_KEY) {
      const newTheme =
        event.newValue === "dark"
          ? "dark"
          : "light";

      document.documentElement.setAttribute(
        "data-theme",
        newTheme
      );

      const themeButton = document.querySelector(
        ".theme-toggle"
      );

      if (themeButton) {
        updateThemeButton(themeButton);
      }
    }
  });

  /**
   * Refresh statistics when the user
   * returns to the page.
   */
  window.addEventListener("pageshow", () => {
    updateDashboardStatistics();
  });
}

// ========================================
// APPLICATION INITIALIZATION
// ========================================

/**
 * Initialize TaskFlow.
 */
function initializeApp() {
  initializeTheme();

  initializeMobileNavigation();

  updateDashboardStatistics();

  initializeStorageSynchronization();

  const statusElement = document.querySelector(
    "#app-status"
  );

  if (statusElement) {
    statusElement.textContent =
      "Application initialized successfully.";
  }

  console.info(
    "TaskFlow initialized successfully."
  );
}

// Start the application.
initializeApp();
