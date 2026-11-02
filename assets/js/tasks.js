
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
 * - Search tasks by title and description
 * - Debounce searches to improve performance
 * - Safely handle extremely long search inputs
 * - Provide feedback after task operations
 */

const TASK_STORAGE_KEY = "taskflow-tasks";
const SEARCH_MAX_LENGTH = 200;
const SEARCH_DEBOUNCE_MS = 300;


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
 * Save the task array to localStorage.
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
 * Render tasks inside the HTML table.
 *
 * User-entered content is inserted using
 * textContent instead of innerHTML to
 * prevent HTML injection.
 */
function renderTasks(tasks, emptyMessage = "No tasks have been created yet.") {
    const tableBody = document.querySelector(
        "#task-table-body"
    );

    if (!tableBody) {
        return;
    }

    // Remove previously displayed rows.
    tableBody.replaceChildren();

    // Display an informative message when no tasks exist.
    if (tasks.length === 0) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");

        cell.colSpan = 5;
        cell.className = "empty-state";
        cell.textContent = emptyMessage;

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

        statusBadge.className =
            `task-badge status-${task.status}`;

        statusBadge.textContent =
            statusLabels[task.status] || "Pending";

        statusCell.appendChild(statusBadge);

        /* ----------------------------------------
           4.4 TASK DUE DATE
        ---------------------------------------- */

        const dateCell = document.createElement("td");

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
        editButton.dataset.taskId = task.id;

        // Create the Delete button.
        const deleteButton = document.createElement("button");

        deleteButton.type = "button";
        deleteButton.className =
            "task-action-button delete-button";
        deleteButton.textContent = "Delete";
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

    // Insert completed rows into the table.
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

    const tableBody = document.querySelector(
        "#task-table-body"
    );

    const accordion = document.querySelector(
        "#create-task-accordion"
    );

    const accordionTitle = document.querySelector(
        ".accordion-title"
    );

    const accordionDescription = document.querySelector(
        "#create-task-accordion .section-description"
    );

    const submitButton = form.querySelector(
        'button[type="submit"]'
    );

    /* ----------------------------------------
       5.2 SELECT SEARCH ELEMENTS
    ---------------------------------------- */

    const searchInput = document.querySelector(
        "#task-search"
    );

    const searchFeedback = document.querySelector(
        "#task-search-feedback"
    );

    // Retrieve previously saved tasks.
    let tasks = loadTasks();

    // null means Create mode; an ID means Edit mode.
    let editingTaskId = null;

    // Store the debounce timer.
    let searchTimer = null;

    // Store the current search query.
    let currentSearchQuery = "";

    /**
     * Display a search-related message.
     */
    function showSearchMessage(message) {
        if (searchFeedback) {
            searchFeedback.textContent = message;
        }
    }

    /* ----------------------------------------
       5.3 FILTER TASKS
    ---------------------------------------- */

    /**
     * Return tasks matching the search query.
     * Search is case-insensitive.
     */
    
    function filterTasks(query) {
        const statusFilter = document.querySelector("#task-status-filter");
        const priorityFilter = document.querySelector("#task-priority-filter");

        const selectedStatus = statusFilter ? statusFilter.value : "all";
        const selectedPriority = priorityFilter ? priorityFilter.value : "all";

        const normalizedQuery = String(query ?? "").toLowerCase();

        return tasks.filter((task) => {
            const title = String(task.title ?? "").toLowerCase();
            const description = String(task.description ?? "").toLowerCase();

            const matchesSearch =
                !normalizedQuery ||
                title.includes(normalizedQuery) ||
                description.includes(normalizedQuery);

            const matchesStatus =
                selectedStatus === "all" ||
                task.status === selectedStatus;

            const matchesPriority =
                selectedPriority === "all" ||
                task.priority === selectedPriority;

            return matchesSearch && matchesStatus && matchesPriority;
        });
    }
    
    /**
     * Sort tasks without modifying the original array.
     * Tasks without due dates appear last.
     */
    function sortTasks(taskList) {
    const sortSelect = document.querySelector("#task-sort");
    const sortOrder = sortSelect ? sortSelect.value : "default";

    const sortedTasks = [...taskList];

    if (sortOrder === "name-asc") {
        sortedTasks.sort((a, b) =>
        String(a.title ?? "").localeCompare(String(b.title ?? ""))
        );
    } else if (sortOrder === "name-desc") {
        sortedTasks.sort((a, b) =>
        String(b.title ?? "").localeCompare(String(a.title ?? ""))
        );
    } else if (sortOrder === "date-asc" || sortOrder === "date-desc") {
        sortedTasks.sort((a, b) => {
        const dateA = String(a.dueDate ?? "");
        const dateB = String(b.dueDate ?? "");

        if (!dateA && !dateB) return 0;
        if (!dateA) return 1;
        if (!dateB) return -1;

        return sortOrder === "date-asc"
            ? dateA.localeCompare(dateB)
            : dateB.localeCompare(dateA);
        });
    }

    return sortedTasks;
    }

    /**
     * Refresh the task table using the
     * currently active search query.
     */
    function refreshTaskTable() {
        const filteredTasks = filterTasks(
            currentSearchQuery
        );
        const sortedTasks = sortTasks(filteredTasks);
        const emptyMessage = currentSearchQuery
            ? "No tasks match your search."
            : "No tasks have been created yet.";

        renderTasks(sortedTasks, emptyMessage);

        if (searchInput && currentSearchQuery) {
            showSearchMessage(
                `${filteredTasks.length} of ${tasks.length} task(s) found.`
            );
        } else {
            showSearchMessage("");
        }
    }
    
    const statusFilter = document.querySelector("#task-status-filter");
    const priorityFilter = document.querySelector("#task-priority-filter");

    if (statusFilter) {
        statusFilter.addEventListener("change", refreshTaskTable);
    }

    if (priorityFilter) {
        priorityFilter.addEventListener("change", refreshTaskTable);
    }

    // Update the task table whenever the sorting option changes.
    const sortSelect = document.querySelector("#task-sort");

    if (sortSelect) {
    sortSelect.addEventListener("change", refreshTaskTable);
    }
    // Display saved tasks when the page loads.
    refreshTaskTable();


    /* ----------------------------------------
       5.4 HANDLE SEARCH INPUT
    ---------------------------------------- */

    /**
     * Search after the user stops typing.
     * Extremely long inputs are truncated
     * before being processed.
     */
    if (searchInput) {
        searchInput.maxLength = SEARCH_MAX_LENGTH;

        searchInput.addEventListener("input", () => {
            // Cancel any pending search.
            clearTimeout(searchTimer);

            let query = searchInput.value;

            // Enforce the length limit in JavaScript.
            if (query.length > SEARCH_MAX_LENGTH) {
                query = query.slice(
                    0,
                    SEARCH_MAX_LENGTH
                );

                searchInput.value = query;
            }

            // Normalize the query once.
            currentSearchQuery = query
                .trim()
                .toLowerCase();

            // Provide immediate feedback for empty searches.
            if (!currentSearchQuery) {
                refreshTaskTable();
                return;
            }

            // Delay filtering until typing stops.
            searchTimer = setTimeout(() => {
                refreshTaskTable();
            }, SEARCH_DEBOUNCE_MS);
        });
    }


    /* ----------------------------------------
       5.5 CREATE CANCEL EDITING BUTTON
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
       5.6 RESET FORM MODE
    ---------------------------------------- */

    /**
     * Restore the form to Create Task mode.
     */
    function resetFormMode() {
        editingTaskId = null;

        form.reset();

        submitButton.textContent = "Create Task";

        if (accordionTitle) {
            accordionTitle.textContent = "Create a New Task";
        }

        if (accordionDescription) {
            accordionDescription.textContent =
                "Complete the following fields to create a new Career Services task.";
        }

        cancelEditButton.hidden = true;
    }


    /* ----------------------------------------
       5.7 START EDITING A TASK
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

        editingTaskId = task.id;

        titleInput.value = task.title;
        descriptionInput.value = task.description || "";
        priorityInput.value = task.priority;
        statusInput.value = task.status;
        dueDateInput.value = task.dueDate || "";

        submitButton.textContent = "Save Changes";

        if (accordionTitle) {
            accordionTitle.textContent = "Edit Task";
        }

        if (accordionDescription) {
            accordionDescription.textContent =
                "Update the following fields to modify this Career Services task.";
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

        titleInput.focus({
            preventScroll: true
        });

        showTaskMessage(`Editing "${task.title}".`);
    }


    /* ----------------------------------------
       5.8 CANCEL EDITING
    ---------------------------------------- */

    cancelEditButton.addEventListener("click", () => {
        resetFormMode();

        if (accordion) {
            accordion.open = false;
        }

        showTaskMessage("Editing cancelled.");
    });


    /* ----------------------------------------
       5.9 HANDLE EDIT AND DELETE BUTTONS
    ---------------------------------------- */

    /**
     * Use event delegation for dynamically
     * generated task buttons.
     */
    if (tableBody) {
        tableBody.addEventListener("click", (event) => {
            const target = event.target;

            if (!(target instanceof Element)) {
                return;
            }

            // Handle Edit.
            const editButton = target.closest(
                ".edit-button"
            );

            if (editButton) {
                startEditing(editButton.dataset.taskId);
                return;
            }

            // Handle Delete.
            const deleteButton = target.closest(
                ".delete-button"
            );

            if (!deleteButton) {
                return;
            }

            const taskId = deleteButton.dataset.taskId;

            const task = tasks.find(
                (item) => item.id === taskId
            );

            if (!task) {
                return;
            }

            const confirmed = window.confirm(
                `Are you sure you want to delete "${task.title}"?`
            );

            if (!confirmed) {
                return;
            }

            const updatedTasks = tasks.filter(
                (item) => item.id !== taskId
            );

            if (!saveTasks(updatedTasks)) {
                showTaskMessage(
                    "Unable to delete task. Please try again."
                );
                return;
            }

            tasks = updatedTasks;

            if (editingTaskId === taskId) {
                resetFormMode();
            }

            // Preserve the active search filter.
            refreshTaskTable();

            showTaskMessage(
                `"${task.title}" was deleted successfully.`
            );
        });
    }


    /* ----------------------------------------
       5.10 CREATE OR UPDATE A TASK
    ---------------------------------------- */

    form.addEventListener("submit", (event) => {
        event.preventDefault();

        const title = titleInput.value.trim();

        // Validate the required title.
        if (!title || title.length > 100) {
            showTaskMessage(
                "Please enter a valid task title (1–100 characters)."
            );

            titleInput.focus();
            return;
        }

        const description = descriptionInput.value.trim();

        // Validate description length.
        if (description.length > 2000) {
            showTaskMessage(
                "Task descriptions cannot exceed 2,000 characters."
            );

            descriptionInput.focus();
            return;
        }

        // Collect the task data.
        const taskData = {
            title: title,
            description: description,
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

        tasks = updatedTasks;

        // Preserve the current search filter.
        refreshTaskTable();

        // Return the form to Create mode.
        resetFormMode();

        if (accordion) {
            accordion.open = false;
        }

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
