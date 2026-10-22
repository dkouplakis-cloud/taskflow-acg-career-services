
"use strict";

/**
 * TaskFlow | ACG Career Services
 * Task Management Module
 *
 * Features:
 * - Create, display, edit, and delete tasks
 * - Store tasks persistently using localStorage
 * - Edit tasks through the existing accordion form
 * - Confirm before deleting a task
 * - Display color-coded priority and status badges
 * - Provide feedback after task operations
 */

const TASK_STORAGE_KEY = "taskflow-tasks";


/* ========================================
   1. LOCAL STORAGE
======================================== */

/**
 * Retrieve tasks saved in the browser.
 * Return an empty array if no valid data exists.
 */
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

/**
 * Save the task array to localStorage as JSON.
 * Return true if saving succeeds.
 */
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


/* ========================================
   2. TASK IDENTIFIERS
======================================== */

/**
 * Generate a unique identifier for each task.
 * Use crypto.randomUUID when supported.
 */
function createTaskId() {
    if (
        typeof crypto !== "undefined" &&
        typeof crypto.randomUUID === "function"
    ) {
        return crypto.randomUUID();
    }

    return `${Date.now()}-${Math.random()}`;
}


/* ========================================
   3. USER FEEDBACK
======================================== */

/**
 * Display task-related messages below the table.
 */
function showTaskMessage(message) {
    const statusElement = document.querySelector(
        "#task-list-status"
    );

    if (statusElement) {
        statusElement.textContent = message;
    }
}


/* ========================================
   4. DISPLAY TASKS
======================================== */

/**
 * Render the tasks inside the HTML table.
 *
 * User-entered content is inserted using
 * textContent rather than innerHTML to
 * prevent HTML injection.
 */
function renderTasks(tasks) {
    const tableBody = document.querySelector(
        "#task-table-body"
    );

    if (!tableBody) {
        return;
    }

    // Remove previously displayed rows.
    tableBody.replaceChildren();

    // Display an informative message if no tasks exist.
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

    // Human-readable priority labels.
    const priorityLabels = {
        low: "Low",
        medium: "Medium",
        high: "High"
    };

    // Human-readable status labels.
    const statusLabels = {
        pending: "Pending",
        progress: "In Progress",
        completed: "Completed"
    };

    // Build rows in memory before adding them to the table.
    const fragment = document.createDocumentFragment();

    tasks.forEach((task) => {
        const row = document.createElement("tr");

        /* ----------------------------------------
           4.1 TASK TITLE AND DESCRIPTION
        ---------------------------------------- */

        const titleCell = document.createElement("td");
        const title = document.createElement("strong");

        title.textContent = task.title;
        titleCell.appendChild(title);

        // Only display the description when one exists.
        if (task.description) {
            const description = document.createElement("p");

            description.className = "task-description";
            description.textContent = task.description;

            titleCell.appendChild(description);
        }

        /* ----------------------------------------
           4.2 TASK PRIORITY BADGE
        ---------------------------------------- */

        const priorityCell = document.createElement("td");
        const priorityBadge = document.createElement("span");

        // CSS classes determine the badge color.
        priorityBadge.className =
            `task-badge priority-${task.priority}`;

        priorityBadge.textContent =
            priorityLabels[task.priority] || "Medium";

        priorityCell.appendChild(priorityBadge);

        /* ----------------------------------------
           4.3 TASK STATUS BADGE
        ---------------------------------------- */

        const statusCell = document.createElement("td");
        const statusBadge = document.createElement("span");

        // Each status receives a different CSS class.
        statusBadge.className =
            `task-badge status-${task.status}`;

        statusBadge.textContent =
            statusLabels[task.status] || "Pending";

        statusCell.appendChild(statusBadge);

        /* ----------------------------------------
           4.4 TASK DUE DATE
        ---------------------------------------- */

        const dateCell = document.createElement("td");

        // Show a dash when no due date is provided.
        dateCell.textContent = task.dueDate || "—";

        /* ----------------------------------------
           4.5 EDIT AND DELETE BUTTONS
        ---------------------------------------- */

        const actionsCell = document.createElement("td");

        // Create the Edit button.
        const editButton = document.createElement("button");

        editButton.type = "button";
        editButton.className =
            "task-action-button edit-button";
        editButton.textContent = "Edit";

        // Associate the button with its task.
        editButton.dataset.taskId = task.id;

        // Create the Delete button.
        const deleteButton = document.createElement("button");

        deleteButton.type = "button";
        deleteButton.className =
            "task-action-button delete-button";
        deleteButton.textContent = "Delete";

        // Associate the button with its task.
        deleteButton.dataset.taskId = task.id;

        actionsCell.append(editButton, deleteButton);

        /* ----------------------------------------
           4.6 COMPLETE THE TABLE ROW
        ---------------------------------------- */

        row.append(
            titleCell,
            priorityCell,
            statusCell,
            dateCell,
            actionsCell
        );

        fragment.appendChild(row);
    });

    // Insert all completed rows into the table.
    tableBody.appendChild(fragment);
}


/* ========================================
   5. INITIALIZE TASK MANAGEMENT
======================================== */

/**
 * Connect task management functionality
 * to the Tasks page.
 */
function initializeTasks() {
    const form = document.querySelector("#task-form");

    // Stop initialization on pages without the task form.
    if (!form) {
        return;
    }

    /* ----------------------------------------
       5.1 SELECT FORM ELEMENTS
    ---------------------------------------- */

    const titleInput = document.querySelector(
        "#task-title"
    );

    const descriptionInput = document.querySelector(
        "#task-description"
    );

    const priorityInput = document.querySelector(
        "#task-priority"
    );

    const statusInput = document.querySelector(
        "#task-status"
    );

    const dueDateInput = document.querySelector(
        "#task-due-date"
    );

    // Select the table and accordion elements.
    const tableBody = document.querySelector(
        "#task-table-body"
    );

    const accordion = document.querySelector(
        "#create-task-accordion"
    );

    const accordionTitle = document.querySelector(
        ".accordion-title"
    );

    const submitButton = form.querySelector(
        'button[type="submit"]'
    );

    // Retrieve previously saved tasks.
    let tasks = loadTasks();

    // null means Create mode; an ID means Edit mode.
    let editingTaskId = null;

    // Display saved tasks when the page loads.
    renderTasks(tasks);


    /* ----------------------------------------
       5.2 CREATE CANCEL EDITING BUTTON
    ---------------------------------------- */

    /**
     * Create a button that allows the user
     * to leave Edit mode without saving.
     */
    const cancelEditButton = document.createElement(
        "button"
    );

    cancelEditButton.type = "button";
    cancelEditButton.id = "cancel-edit-button";
    cancelEditButton.className = "task-action-button";
    cancelEditButton.textContent = "Cancel Editing";
    cancelEditButton.hidden = true;

    // Position the button next to Save Changes.
    submitButton.insertAdjacentElement(
        "afterend",
        cancelEditButton
    );


    /* ----------------------------------------
       5.3 RESET FORM MODE
    ---------------------------------------- */

    /**
     * Restore the form to Create Task mode.
     */
    function resetFormMode() {
        editingTaskId = null;

        // Clear form fields and restore default values.
        form.reset();

        submitButton.textContent = "Create Task";

        if (accordionTitle) {
            accordionTitle.textContent = "Create a New Task";
        }

        cancelEditButton.hidden = true;
    }


    /* ----------------------------------------
       5.4 START EDITING A TASK
    ---------------------------------------- */

    /**
     * Locate a task and populate the form
     * with its existing information.
     */
    function startEditing(taskId) {
        const task = tasks.find(
            (item) => item.id === taskId
        );

        if (!task) {
            showTaskMessage("Selected task was not found.");
            return;
        }

        // Switch from Create mode to Edit mode.
        editingTaskId = task.id;

        // Populate the form with existing values.
        titleInput.value = task.title;
        descriptionInput.value = task.description || "";
        priorityInput.value = task.priority;
        statusInput.value = task.status;
        dueDateInput.value = task.dueDate || "";

        // Update the form's labels.
        submitButton.textContent = "Save Changes";

        if (accordionTitle) {
            accordionTitle.textContent = "Edit Task";
        }

        cancelEditButton.hidden = false;

        // Open the accordion and scroll to the form.
        if (accordion) {
            accordion.open = true;

            accordion.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });
        }

        // Place the cursor in the title field.
        titleInput.focus({
            preventScroll: true
        });

        showTaskMessage(`Editing "${task.title}".`);
    }


    /* ----------------------------------------
       5.5 CANCEL EDITING
    ---------------------------------------- */

    /**
     * Cancel editing without modifying
     * the saved task.
     */
    cancelEditButton.addEventListener("click", () => {
        resetFormMode();

        if (accordion) {
            accordion.open = false;
        }

        showTaskMessage("Editing cancelled.");
    });


    /* ----------------------------------------
       5.6 HANDLE EDIT AND DELETE BUTTONS
    ---------------------------------------- */

    /**
     * Use event delegation to handle clicks
     * on dynamically generated task buttons.
     *
     * This avoids attaching separate event
     * listeners to every table row.
     */
    if (tableBody) {
        tableBody.addEventListener("click", (event) => {
            const target = event.target;

            if (!(target instanceof Element)) {
                return;
            }

            // Check whether the Edit button was clicked.
            const editButton = target.closest(
                ".edit-button"
            );

            if (editButton) {
                startEditing(editButton.dataset.taskId);
                return;
            }

            // Check whether the Delete button was clicked.
            const deleteButton = target.closest(
                ".delete-button"
            );

            if (!deleteButton) {
                return;
            }

            const taskId = deleteButton.dataset.taskId;

            // Locate the selected task.
            const task = tasks.find(
                (item) => item.id === taskId
            );

            if (!task) {
                return;
            }

            // Ask the user to confirm deletion.
            const confirmed = window.confirm(
                `Are you sure you want to delete "${task.title}"?`
            );

            // Keep the task if deletion was cancelled.
            if (!confirmed) {
                return;
            }

            // Create an array without the deleted task.
            const updatedTasks = tasks.filter(
                (item) => item.id !== taskId
            );

            // Persist the deletion in localStorage.
            if (!saveTasks(updatedTasks)) {
                showTaskMessage(
                    "Unable to delete task. Please try again."
                );

                return;
            }

            // Update the in-memory task collection.
            tasks = updatedTasks;

            // Exit Edit mode if the edited task was deleted.
            if (editingTaskId === taskId) {
                resetFormMode();
            }

            // Refresh the task table.
            renderTasks(tasks);

            showTaskMessage(
                `"${task.title}" was deleted successfully.`
            );
        });
    }


    /* ----------------------------------------
       5.7 CREATE OR UPDATE A TASK
    ---------------------------------------- */

    /**
     * Handle both task creation and editing
     * using the same form.
     */
    form.addEventListener("submit", (event) => {
        // Prevent the browser from reloading the page.
        event.preventDefault();

        const title = titleInput.value.trim();

        // Validate the required task title.
        if (!title || title.length > 100) {
            showTaskMessage(
                "Please enter a valid task title (1–100 characters)."
            );

            titleInput.focus();
            return;
        }

        // Collect values entered by the user.
        const taskData = {
            title: title,
            description: descriptionInput.value.trim(),
            priority: priorityInput.value,
            status: statusInput.value,
            dueDate: dueDateInput.value
        };

        let updatedTasks;
        let successMessage;

        if (editingTaskId !== null) {
            /* UPDATE AN EXISTING TASK */

            const existingTask = tasks.find(
                (item) => item.id === editingTaskId
            );

            if (!existingTask) {
                showTaskMessage(
                    "The task being edited no longer exists."
                );

                resetFormMode();
                return;
            }

            // Preserve the task's original ID and
            // creation timestamp while updating its data.
            updatedTasks = tasks.map((task) => {
                if (task.id === editingTaskId) {
                    return {
                        ...task,
                        ...taskData,
                        updatedAt: new Date().toISOString()
                    };
                }

                return task;
            });

            successMessage = "Task updated successfully.";

        } else {
            /* CREATE A NEW TASK */

            const newTask = {
                id: createTaskId(),
                ...taskData,
                createdAt: new Date().toISOString()
            };

            // Add the new task to the existing collection.
            updatedTasks = [...tasks, newTask];

            successMessage = "Task created successfully.";
        }

        // Save changes before updating the interface.
        if (!saveTasks(updatedTasks)) {
            showTaskMessage(
                "Unable to save task. Please try again."
            );

            return;
        }

        // Update the task collection in memory.
        tasks = updatedTasks;

        // Display the updated task table.
        renderTasks(tasks);

        // Return the form to Create mode.
        resetFormMode();

        // Close the accordion after saving.
        if (accordion) {
            accordion.open = false;
        }

        // Inform the user that the operation succeeded.
        showTaskMessage(
            `${successMessage} ${tasks.length} task(s) total.`
        );
    });
}


/* ========================================
   6. START TASK MANAGEMENT
======================================== */

// Initialize the task module when it loads.
initializeTasks();
