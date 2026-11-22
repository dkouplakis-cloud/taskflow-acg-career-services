
"use strict";

/**
 * TaskFlow - Task Deletion Confirmation
 *
 * Uses a native HTML dialog.
 * Django handles the actual deletion through
 * a POST request protected by a CSRF token.
 */

const initializeTaskDeletion = () => {
    const dialog = document.querySelector(
        "#tf-task-delete-dialog"
    );

    const form = document.querySelector(
        "#tf-task-delete-form"
    );

    const taskName = document.querySelector(
        "#tf-task-delete-name"
    );

    const cancelButton = document.querySelector(
        "#tf-task-delete-cancel"
    );

    const confirmButton = document.querySelector(
        ".tf-task-delete-confirm"
    );

    if (
        !dialog ||
        !form ||
        !taskName ||
        !cancelButton ||
        !confirmButton
    ) {
        return;
    }

    /**
     * Event delegation is used because live task
     * filtering replaces the task table.
     */
    document.addEventListener("click", (event) => {
        const trigger = event.target.closest(
            ".tf-tasklist-delete-trigger"
        );

        if (!trigger) {
            return;
        }

        const deleteUrl = trigger.dataset.deleteUrl;
        const selectedName = trigger.dataset.taskName;

        if (!deleteUrl) {
            return;
        }

        // The URL comes from Django's named route.
        const targetUrl = new URL(
            deleteUrl,
            window.location.href
        );

        // Prevent submitting to another origin.
        if (targetUrl.origin !== window.location.origin) {
            return;
        }

        form.action = targetUrl.href;

        // Use textContent to display task names safely.
        taskName.textContent = selectedName || "Selected task";

        confirmButton.disabled = false;

        dialog.showModal();
    });

    // Cancel without submitting anything.
    cancelButton.addEventListener("click", () => {
        dialog.close();
    });

    // Prevent repeated confirmation clicks.
    form.addEventListener("submit", () => {
        confirmButton.disabled = true;
    });
};

if (document.readyState === "loading") {
    document.addEventListener(
        "DOMContentLoaded",
        initializeTaskDeletion
    );
} else {
    initializeTaskDeletion();
}