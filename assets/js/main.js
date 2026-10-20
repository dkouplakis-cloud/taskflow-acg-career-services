
"use strict";

/**
 * TaskFlow | ACG Career Services
 * Initializes the application.
 */

function initializeApp() {
  const statusElement =
    document.querySelector("#app-status");

  if (!statusElement) {
    console.warn("TaskFlow: Status element was not found.");
    return;
  }

  statusElement.textContent =
    "Application initialized successfully.";
}

initializeApp();
