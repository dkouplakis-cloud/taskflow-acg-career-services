
"use strict";

/**
 * TaskFlow | ACG Career Services
 * Analytics page functionality
 *
 * Displays performance statistics and visual charts
 * using tasks saved in localStorage.
 */

const STORAGE_KEY = "taskflow-tasks";

/**
 * Retrieve saved tasks from localStorage.
 *
 * @returns {Array} List of saved tasks.
 */
function getSavedTasks() {
  try {
    const storedTasks = localStorage.getItem(STORAGE_KEY);

    if (!storedTasks) {
      return [];
    }

    const tasks = JSON.parse(storedTasks);

    return Array.isArray(tasks) ? tasks : [];
  } catch (error) {
    console.error("Unable to load analytics data:", error);
    return [];
  }
}

/**
 * Count tasks matching a specific property and value.
 *
 * @param {Array} tasks - All saved tasks.
 * @param {string} property - Property to examine.
 * @param {string} value - Expected property value.
 * @returns {number} Number of matching tasks.
 */
function countTasks(tasks, property, value) {
  return tasks.filter((task) => task[property] === value).length;
}

/**
 * Update the performance overview cards.
 *
 * @param {Array} tasks - All saved tasks.
 */
function updateAnalyticsOverview(tasks) {
  const total = tasks.length;
  const completed = countTasks(tasks, "status", "completed");
  const high = countTasks(tasks, "priority", "high");

  // Avoid division by zero when no tasks exist.
  const completionRate =
    total === 0 ? 0 : Math.round((completed / total) * 100);

  document.querySelector('[data-analytics="total"]').textContent =
    String(total);

  document.querySelector('[data-analytics="completed"]').textContent =
    String(completed);

  document.querySelector('[data-analytics="rate"]').textContent =
    `${completionRate}%`;

  document.querySelector('[data-analytics="high"]').textContent =
    String(high);
}

/**
 * Build a horizontal bar chart using HTML elements.
 *
 * @param {string} selector - Chart container selector.
 * @param {Array} items - Chart categories and counts.
 * @param {number} total - Total number of tasks.
 */
function renderBarChart(selector, items, total) {
  const container = document.querySelector(selector);

  if (!container) {
    return;
  }

  // Remove the initial placeholder message.
  container.replaceChildren();

  if (total === 0) {
    const message = document.createElement("p");
    message.textContent = "No tasks available for analysis.";
    container.appendChild(message);
    return;
  }

  items.forEach((item) => {
    const percentage = (item.count / total) * 100;

    // Create the container for one chart category.
    const row = document.createElement("div");
    row.className = "analytics-bar-row";

    // Display the category label and task count.
    const heading = document.createElement("div");
    heading.className = "analytics-bar-heading";

    const label = document.createElement("span");
    label.textContent = item.label;

    const count = document.createElement("span");
    count.textContent = `${item.count} (${Math.round(percentage)}%)`;

    heading.append(label, count);

    // Create the background track.
    const track = document.createElement("div");
    track.className = "analytics-bar-track";

    // Create the colored bar representing the percentage.
    const fill = document.createElement("div");
    fill.className = `analytics-bar-fill ${item.className}`;
    fill.style.width = `${percentage}%`;

    track.appendChild(fill);
    row.append(heading, track);
    container.appendChild(row);
  });
}

/**
 * Initialize all analytics calculations and charts.
 */
function initializeAnalytics() {
  const tasks = getSavedTasks();

  // Update summary statistics.
  updateAnalyticsOverview(tasks);

  // Calculate the number of tasks in each status.
  const statusItems = [
    {
      label: "Pending",
      count: countTasks(tasks, "status", "pending"),
      className: "analytics-pending"
    },
    {
      label: "In Progress",
      count: countTasks(tasks, "status", "progress"),
      className: "analytics-progress"
    },
    {
      label: "Completed",
      count: countTasks(tasks, "status", "completed"),
      className: "analytics-completed"
    }
  ];

  // Calculate the number of tasks in each priority.
  const priorityItems = [
    {
      label: "Low",
      count: countTasks(tasks, "priority", "low"),
      className: "analytics-low"
    },
    {
      label: "Medium",
      count: countTasks(tasks, "priority", "medium"),
      className: "analytics-medium"
    },
    {
      label: "High",
      count: countTasks(tasks, "priority", "high"),
      className: "analytics-high"
    }
  ];

  // Render the two analytics charts.
  renderBarChart("#status-chart", statusItems, tasks.length);
  renderBarChart("#priority-chart", priorityItems, tasks.length);

  console.info("TaskFlow analytics initialized successfully.");
}

// Start analytics when the page loads.
initializeAnalytics();
