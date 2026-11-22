
"use strict";

/**
 * TaskFlow - Project Team Selection
 *
 * Prevent the Project Manager from being
 * selected as a project collaborator.
 */

function initializeProjectTeamSelection() {

    const form = document.querySelector(
        ".project-form"
    );

    if (!form) {
        return;
    }

    const managerSelect = form.querySelector(
        'select[name="project_manager"]'
    );

    const collaboratorOptions = [
        ...form.querySelectorAll(
            ".project-collaborator-option"
        )
    ];

    if (!managerSelect) {
        return;
    }

    function updateAvailableCollaborators() {

        const managerId = managerSelect.value;

        collaboratorOptions.forEach((option) => {

            const checkbox = option.querySelector(
                'input[name="collaborators"]'
            );

            if (!checkbox) {
                return;
            }

            const isManager = (
                managerId !== "" &&
                checkbox.value === managerId
            );

            if (isManager) {
                checkbox.checked = false;
            }

            checkbox.disabled = isManager;
            option.hidden = isManager;

        });

    }

    managerSelect.addEventListener(
        "change",
        updateAvailableCollaborators
    );

    // Apply the restriction when the page first opens.
    updateAvailableCollaborators();

    console.info(
        "Project team selection initialized."
    );
}

if (document.readyState === "loading") {
    document.addEventListener(
        "DOMContentLoaded",
        initializeProjectTeamSelection
    );
} else {
    initializeProjectTeamSelection();
}