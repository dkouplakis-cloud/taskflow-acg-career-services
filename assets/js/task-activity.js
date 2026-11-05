
"use strict";

/**
 * TaskFlow | ACG Career Services
 * Shared task activity module.
 *
 * Stores a bounded history of task changes.
 * Activity history is separate from saved tasks.
 */

const ACTIVITY_STORAGE_KEY = "taskflow-activity";
const MAX_ACTIVITY_RECORDS = 50;
const MAX_ACTIVITY_TITLE_LENGTH = 100;

const ALLOWED_ACTIONS = new Set([
  "created",
  "updated",
  "completed",
  "deleted",
  "status-changed"
]);

/**
 * Retrieve activity records safely.
 *
 * @returns {Array} Valid saved activity records.
 */
export function loadTaskActivity() {
  try {
    const stored = localStorage.getItem(
      ACTIVITY_STORAGE_KEY
    );

    if (!stored) {
      return [];
    }

    const parsed = JSON.parse(stored);

    if (!Array.isArray(parsed)) {
      return [];
    }

    return parsed
      .filter((entry) => {
        return (
          entry !== null &&
          typeof entry === "object" &&
          typeof entry.title === "string" &&
          typeof entry.timestamp === "string" &&
          ALLOWED_ACTIONS.has(entry.action) &&
          !Number.isNaN(Date.parse(entry.timestamp))
        );
      })
      .slice(0, MAX_ACTIVITY_RECORDS);

  } catch (error) {
    console.error(
      "Unable to load task activity:",
      error
    );

    return [];
  }
}

/**
 * Record an activity after a successful task change.
 *
 * @param {string} action - Activity type.
 * @param {string} title - Task title.
 * @returns {boolean} Whether the record was saved.
 */
export function recordTaskActivity(action, title) {
  if (!ALLOWED_ACTIONS.has(action)) {
    return false;
  }

  const safeTitle = String(title ?? "")
    .trim()
    .slice(0, MAX_ACTIVITY_TITLE_LENGTH);

  if (!safeTitle) {
    return false;
  }

  const entry = {
    id:
      typeof crypto !== "undefined" &&
      typeof crypto.randomUUID === "function"
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random()}`,
    action,
    title: safeTitle,
    timestamp: new Date().toISOString()
  };

  try {
    const existing = loadTaskActivity();

    const updated = [
      entry,
      ...existing
    ].slice(0, MAX_ACTIVITY_RECORDS);

    localStorage.setItem(
      ACTIVITY_STORAGE_KEY,
      JSON.stringify(updated)
    );

    return true;

  } catch (error) {
    console.error(
      "Unable to record task activity:",
      error
    );

    return false;
  }
}
