
"use strict";

import { recordTaskActivity } from "./task-activity.js";

/**
 * TaskFlow | ACG Career Services
 * Kanban Board Module
 *
 * Features:
 * - Three workflow columns
 * - Drag-and-drop task movement
 * - Accessible status dropdowns
 * - Persistent localStorage synchronization
 * - Task activity logging
 * - Task modification timestamps
 * - Safe DOM rendering
 * - Cross-tab synchronization
 */

function initializeKanban() {
  const STORAGE_KEY = "taskflow-tasks";

  const VALID_STATUSES = [
    "pending",
    "progress",
    "completed"
  ];

  const STATUS_LABELS = {
    pending: "Pending",
    progress: "In Progress",
    completed: "Completed"
  };

  const EMPTY_MESSAGES = {
    pending: "No pending tasks.",
    progress: "No tasks in progress.",
    completed: "No completed tasks."
  };

  const board = document.querySelector("#kanban-board");
  const feedback = document.querySelector("#kanban-feedback");
  const totalElement = document.querySelector("#kanban-total");
  const completionElement = document.querySelector(
    "#kanban-completion-rate"
  );

  if (!board) {
    return;
  }

  let tasks = [];
  let draggedTaskId = null;

  /**
   * Display feedback safely.
   */
  function showFeedback(message) {
    if (feedback) {
      feedback.textContent = message;
    }
  }

  /**
   * Retrieve tasks from localStorage.
   */
  function loadTasks() {
    try {
      const storedValue = localStorage.getItem(STORAGE_KEY);

      if (!storedValue) {
        return [];
      }

      const parsedValue = JSON.parse(storedValue);

      if (!Array.isArray(parsedValue)) {
        showFeedback("Stored task data has an invalid format.");
        return [];
      }

      return parsedValue.filter((task) => {
        return (
          task !== null &&
          typeof task === "object" &&
          !Array.isArray(task) &&
          (typeof task.id === "string" ||
            typeof task.id === "number") &&
          typeof task.title === "string" &&
          VALID_STATUSES.includes(task.status)
        );
      });

    } catch (error) {
      console.error("Unable to load Kanban tasks:", error);

      showFeedback(
        "Unable to read saved tasks. Stored data was not changed."
      );

      return [];
    }
  }

  /**
   * Save updated tasks.
   */
  function saveTasks(updatedTasks) {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify(updatedTasks)
      );

      return true;

    } catch (error) {
      console.error("Unable to save Kanban tasks:", error);

      showFeedback(
        "Unable to save changes. Please check browser storage."
      );

      return false;
    }
  }

  /**
   * Create an HTML element with safe text content.
   */
  function createTextElement(tagName, className, value) {
    const element = document.createElement(tagName);

    element.className = className;
    element.textContent = String(value ?? "");

    return element;
  }

  /**
   * Update a task's status.
   *
   * Saves the change before updating the interface
   * or recording activity.
   */
  function updateTaskStatus(taskId, newStatus) {
    if (!VALID_STATUSES.includes(newStatus)) {
      showFeedback("Invalid task status.");
      renderBoard();
      return;
    }

    const task = tasks.find((item) => {
      return String(item.id) === String(taskId);
    });

    if (!task) {
      showFeedback("The selected task could not be found.");
      renderBoard();
      return;
    }

    if (task.status === newStatus) {
      return;
    }

    try {
      // Read the latest stored data before updating.
      const storedValue = localStorage.getItem(STORAGE_KEY);

      const originalTasks = storedValue
        ? JSON.parse(storedValue)
        : [];

      if (!Array.isArray(originalTasks)) {
        showFeedback("Invalid stored task data.");
        renderBoard();
        return;
      }

      const matchingTasks = originalTasks.filter((item) => {
        return (
          item !== null &&
          typeof item === "object" &&
          String(item.id) === String(taskId)
        );
      });

      if (matchingTasks.length !== 1) {
        showFeedback(
          "Task data has changed or contains duplicate IDs."
        );

        tasks = loadTasks();
        renderBoard();
        return;
      }

      const storedTask = matchingTasks[0];

      if (!VALID_STATUSES.includes(storedTask.status)) {
        showFeedback("The stored task has an invalid status.");
        tasks = loadTasks();
        renderBoard();
        return;
      }

      if (storedTask.status !== task.status) {
        showFeedback(
          "Task status changed elsewhere. Board refreshed."
        );

        tasks = loadTasks();
        renderBoard();
        return;
      }

      const timestamp = new Date().toISOString();

      const updatedTasks = originalTasks.map((item) => {
        if (
          item !== null &&
          typeof item === "object" &&
          String(item.id) === String(taskId)
        ) {
          return {
            ...item,
            status: newStatus,
            updatedAt: timestamp
          };
        }

        return item;
      });

      // Never update the interface if saving fails.
      if (!saveTasks(updatedTasks)) {
        renderBoard();
        return;
      }

      // Reload the successfully saved task records.
      tasks = loadTasks();

      // Record activity after successful persistence.
      const activityAction =
        newStatus === "completed"
          ? "completed"
          : "status-changed";

      recordTaskActivity(
        activityAction,
        storedTask.title
      );

      renderBoard();

      showFeedback(
        `Task "${storedTask.title.slice(0, 100)}" moved to ${STATUS_LABELS[newStatus]}.`
      );

    } catch (error) {
      console.error("Unable to update task:", error);

      showFeedback(
        "Task update failed. Existing data was preserved."
      );

      tasks = loadTasks();
      renderBoard();
    }
  }

  /**
   * Create a Kanban task card.
   */
  function createTaskCard(task) {
    const card = document.createElement("article");

    card.className = "kanban-card";
    card.draggable = true;
    card.dataset.taskId = String(task.id);

    // Task title.
    const title = createTextElement(
      "h4",
      "kanban-card-title",
      task.title.slice(0, 100)
    );

    card.appendChild(title);

    // Task description.
    if (typeof task.description === "string") {
      const description = createTextElement(
        "p",
        "kanban-card-description",
        task.description.slice(0, 2000)
      );

      card.appendChild(description);
    }

    // Task metadata.
    const metadata = document.createElement("div");
    metadata.className = "kanban-card-meta";

    const priorityValue = String(
      task.priority ?? "medium"
    ).slice(0, 20);

    const formattedPriority =
      priorityValue.charAt(0).toUpperCase() +
      priorityValue.slice(1).toLowerCase();

    const priority = createTextElement(
      "span",
      "kanban-card-priority",
      `Priority: ${formattedPriority}`
    );

    metadata.appendChild(priority);

    // Format the due date safely.
    if (
      typeof task.dueDate === "string" &&
      /^\d{4}-\d{2}-\d{2}$/.test(task.dueDate)
    ) {
      const dateParts = task.dueDate.split("-");

      const year = Number(dateParts[0]);
      const month = Number(dateParts[1]);
      const day = Number(dateParts[2]);

      const date = new Date(
        Date.UTC(year, month - 1, day)
      );

      const validDate =
        date.getUTCFullYear() === year &&
        date.getUTCMonth() === month - 1 &&
        date.getUTCDate() === day;

      if (validDate) {
        const formattedDate = date.toLocaleDateString(
          "en-GB",
          {
            day: "2-digit",
            month: "short",
            year: "numeric",
            timeZone: "UTC"
          }
        );

        const dueDate = createTextElement(
          "span",
          "kanban-card-date",
          `Due: ${formattedDate}`
        );

        metadata.appendChild(dueDate);
      }
    }

    card.appendChild(metadata);

    /**
     * Accessible status selector.
     */
    const label = document.createElement("label");

    label.className = "kanban-status-label";
    label.textContent = "Change status";

    const selector = document.createElement("select");

    selector.className = "kanban-status-select";

    selector.setAttribute(
      "aria-label",
      `Change status for ${task.title.slice(0, 100)}`
    );

    VALID_STATUSES.forEach((status) => {
      const option = document.createElement("option");

      option.value = status;
      option.textContent = STATUS_LABELS[status];

      selector.appendChild(option);
    });

    selector.value = task.status;

    selector.addEventListener("change", () => {
      updateTaskStatus(task.id, selector.value);
    });

    label.appendChild(selector);
    card.appendChild(label);

    /**
     * Drag-and-drop events.
     */
    card.addEventListener("dragstart", (event) => {
      draggedTaskId = String(task.id);

      if (event.dataTransfer) {
        event.dataTransfer.effectAllowed = "move";

        event.dataTransfer.setData(
          "text/plain",
          draggedTaskId
        );
      }

      card.classList.add("is-dragging");
    });

    card.addEventListener("dragend", () => {
      draggedTaskId = null;
      card.classList.remove("is-dragging");
    });

    return card;
  }

  /**
   * Render the Kanban board.
   */
  function renderBoard() {
    VALID_STATUSES.forEach((status) => {
      const taskList = document.querySelector(
        `#${status}-tasks`
      );

      const countElement = document.querySelector(
        `#${status}-count`
      );

      if (!taskList) {
        return;
      }

      taskList.replaceChildren();

      const columnTasks = tasks.filter((task) => {
        return task.status === status;
      });

      if (countElement) {
        countElement.textContent = String(
          columnTasks.length
        );
      }

      if (columnTasks.length === 0) {
        const emptyMessage = createTextElement(
          "p",
          "kanban-empty",
          EMPTY_MESSAGES[status]
        );

        taskList.appendChild(emptyMessage);

      } else {
        const fragment = document.createDocumentFragment();

        columnTasks.forEach((task) => {
          fragment.appendChild(createTaskCard(task));
        });

        taskList.appendChild(fragment);
      }
    });

    // Update board statistics.
    const totalTasks = tasks.length;

    const completedTasks = tasks.filter((task) => {
      return task.status === "completed";
    }).length;

    const completionRate = totalTasks > 0
      ? Math.round((completedTasks / totalTasks) * 100)
      : 0;

    if (totalElement) {
      totalElement.textContent = String(totalTasks);
    }

    if (completionElement) {
      completionElement.textContent =
        `${completionRate}%`;
    }
  }

  /**
   * Configure drag-and-drop zones.
   */
  function initializeDropZones() {
    const dropZones = board.querySelectorAll(
      ".kanban-task-list"
    );

    dropZones.forEach((zone) => {
      zone.addEventListener("dragover", (event) => {
        if (!draggedTaskId) {
          return;
        }

        event.preventDefault();

        if (event.dataTransfer) {
          event.dataTransfer.dropEffect = "move";
        }

        zone.classList.add("is-drag-over");
      });

      zone.addEventListener("dragleave", (event) => {
        if (!zone.contains(event.relatedTarget)) {
          zone.classList.remove("is-drag-over");
        }
      });

      zone.addEventListener("drop", (event) => {
        event.preventDefault();

        zone.classList.remove("is-drag-over");

        if (!draggedTaskId) {
          return;
        }

        const newStatus = zone.dataset.status;

        updateTaskStatus(draggedTaskId, newStatus);

        draggedTaskId = null;
      });
    });
  }

  /**
   * Refresh when another tab changes saved tasks.
   */
  window.addEventListener("storage", (event) => {
    if (event.key !== STORAGE_KEY) {
      return;
    }

    tasks = loadTasks();

    renderBoard();

    showFeedback(
      "The Kanban board was updated from another tab."
    );
  });

  // Initial setup.
  tasks = loadTasks();

  initializeDropZones();
  renderBoard();
}

// Initialize Kanban.
initializeKanban();
