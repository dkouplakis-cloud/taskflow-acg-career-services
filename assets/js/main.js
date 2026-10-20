
"use strict";

/**
 * Initializes the TaskFlow application.
 */
function initializeApp() {
  const statusElement =
    document.getElementById("app-status");

  if (!statusElement) {
    console.warn(
      "TaskFlow: Status element was not found."
    );
    return;
  }

  statusElement.textContent =
    "Application initialized successfully.";
}

initializeApp();
