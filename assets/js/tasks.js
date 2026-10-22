
"use strict";

/**
 * TaskFlow | ACG Career Services
 * Task management functionality
 */

const TASK_STORAGE_KEY = "taskflow-tasks";

/* Retrieve previously saved tasks */
function loadTasks() {
  try {
    const saved = localStorage.getItem(TASK_STORAGE_KEY);

    if (!saved) {
      return [];
    }

    const parsed = JSON.parse(saved);

    return Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    console.error("Unable to load tasks:", error);
    return [];
  }
}

/* Save tasks to browser storage */
function saveTasks(tasks) {
  try {
    localStorage.setItem(
      TASK_STORAGE_KEY,
      JSON.stringify(tasks)
    );

    return true;
  } catch (error) {
    console.error("Unable to save tasks:", error);
    return false;
  }
}

/* Create a unique task identifier */
function createTaskId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random()}`;
}

/* Display tasks in the table */
function renderTasks(tasks) {
  const tableBody =
    document.querySelector("#task-table-body");

  if (!tableBody) {
    return;
  }

  tableBody.replaceChildren();

  if (tasks.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");

    cell.colSpan = 5;
    cell.className = "empty-state";
    cell.textContent = "No tasks have been created yet.";

    row.appendChild(cell);
    tableBody.appendChild(row);
    return;
  }

  const priorityLabels = {
    low: "Low",
    medium: "Medium",
    high: "High"
  };

  const statusLabels = {
    pending: "Pending",
    progress: "In Progress",
    completed: "Completed"
  };

  const fragment = document.createDocumentFragment();

  tasks.forEach((task) => {
    const row = document.createElement("tr");

    const titleCell = document.createElement("td");
    const title = document.createElement("strong");

    title.textContent = task.title;
    titleCell.appendChild(title);

    if (task.description) {
      const description = document.createElement("p");
      description.className = "task-description";
      description.textContent = task.description;
      titleCell.appendChild(description);
    }

    const priorityCell = document.createElement("td");
    priorityCell.textContent =
      priorityLabels[task.priority] || "Medium";

    const statusCell = document.createElement("td");
    statusCell.textContent =
      statusLabels[task.status] || "Pending";

    const dateCell = document.createElement("td");
    dateCell.textContent = task.dueDate || "—";

    const actionsCell = document.createElement("td");
    actionsCell.textContent = "—";

    row.append(
      titleCell,
      priorityCell,
      statusCell,
      dateCell,
      actionsCell
    );

    fragment.appendChild(row);
  });

  tableBody.appendChild(fragment);
}

/* Initialize task creation */
function initializeTasks() {
  const form = document.querySelector("#task-form");

  if (!form) {
    return;
  }

  let tasks = loadTasks();

  renderTasks(tasks);

  form.addEventListener("submit", (event) => {
    event.preventDefault();

    const titleInput =
      document.querySelector("#task-title");

    const descriptionInput =
      document.querySelector("#task-description");

    const priorityInput =
      document.querySelector("#task-priority");

    const statusInput =
      document.querySelector("#task-status");

    const dueDateInput =
      document.querySelector("#task-due-date");

    const statusMessage =
      document.querySelector("#task-list-status");

    const title = titleInput.value.trim();

    if (!title || title.length > 100) {
      if (statusMessage) {
        statusMessage.textContent =
          "Please enter a valid task title (1–100 characters).";
      }
      titleInput.focus();
      return;
    }

    const newTask = {
      id: createTaskId(),
      title: title,
      description: descriptionInput.value.trim(),
      priority: priorityInput.value,
      status: statusInput.value,
      dueDate: dueDateInput.value,
      createdAt: new Date().toISOString()
    };

    const updatedTasks = [...tasks, newTask];

    if (!saveTasks(updatedTasks)) {
      if (statusMessage) {
        statusMessage.textContent =
          "Task could not be saved. Please try again.";
      }
      return;
    }

    tasks = updatedTasks;
    renderTasks(tasks);

    form.reset();

    if (statusMessage) {
      statusMessage.textContent =
        `Task created successfully. ${tasks.length} task(s) total.`;
    }

    const accordion =
      document.querySelector("#create-task-accordion");

    if (accordion) {
      accordion.open = false;
    }
  });
}

/* Start task management */
initializeTasks();
