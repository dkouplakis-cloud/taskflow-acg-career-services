
"use strict";

/**
 * TaskFlow | ACG Career Services
 * Live Project Task Search and Filtering
 *
 * Uses the existing Django GET endpoint.
 * No localStorage or duplicate filtering logic.
 */

const initializeTaskFilters = () => {

    const form = document.querySelector(".tf-taskfilter");
    const resultsSelector = "#tf-task-results";

    // Only initialize on pages containing task filters.
    if (!form || !document.querySelector(resultsSelector)) {
        return;
    }

    const searchInput = form.querySelector(
        'input[name="q"]'
    );

    const dropdowns = form.querySelectorAll(
        'select[name="status"], ' +
        'select[name="priority"], ' +
        'select[name="sort"]'
    );

    // Accessible feedback for asynchronous updates.
    const feedback = document.createElement("p");

    feedback.className = "tf-taskfilter-live";
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-live", "polite");

    form.appendChild(feedback);

    let debounceTimer = null;
    let activeController = null;
    let requestVersion = 0;

    /**
     * Build a URL containing the selected filters.
     */
    const buildFilterUrl = () => {

        const url = new URL(
            form.action,
            window.location.href
        );

        const parameters = new URLSearchParams(
            new FormData(form)
        );

        url.search = parameters.toString();

        return url;
    };

    /**
     * Fetch the filtered HTML from Django.
     */
    const updateTaskResults = async (url, version) => {

        const controller = new AbortController();
        activeController = controller;

        const existingResults = document.querySelector(
            resultsSelector
        );

        if (existingResults) {
            existingResults.setAttribute(
                "aria-busy",
                "true"
            );
        }

        feedback.textContent = "Updating tasks...";

        try {

            const response = await fetch(
                url.toString(),
                {
                    method: "GET",
                    credentials: "same-origin",
                    headers: {
                        "Accept": "text/html",
                        "X-Requested-With": "XMLHttpRequest"
                    },
                    signal: controller.signal
                }
            );

            if (!response.ok) {
                throw new Error(
                    `Request failed: ${response.status}`
                );
            }

            const html = await response.text();

            // Ignore results from outdated requests.
            if (
                version !== requestVersion ||
                controller.signal.aborted
            ) {
                return;
            }

            const parser = new DOMParser();

            const newDocument = parser.parseFromString(
                html,
                "text/html"
            );

            const newResults = newDocument.querySelector(
                resultsSelector
            );

            const newFooter = newDocument.querySelector(
                ".tf-taskfilter-footer"
            );

            const currentResults = document.querySelector(
                resultsSelector
            );

            const currentFooter = form.querySelector(
                ".tf-taskfilter-footer"
            );

            // Ensure the server returned the expected page.
            if (
                !newResults ||
                !newFooter ||
                !currentResults ||
                !currentFooter
            ) {
                throw new Error(
                    "Filtered task content was not found."
                );
            }

            // Replace only the results and task count.
            // Preserve the form and current input focus.
            currentResults.replaceWith(
                document.importNode(newResults, true)
            );

            currentFooter.replaceWith(
                document.importNode(newFooter, true)
            );

            // Keep the URL synchronized with the filters.
            // This also preserves filters after refresh.
            window.history.replaceState(
                window.history.state,
                "",
                url.pathname + url.search
            );

            feedback.textContent = "Task results updated.";

        } catch (error) {

            // Aborted requests are expected during typing.
            if (
                error.name === "AbortError" ||
                version !== requestVersion
            ) {
                return;
            }

            console.error(
                "Unable to update task results:",
                error
            );

            // Fall back to the standard Django GET request.
            window.location.assign(
                url.toString()
            );

        } finally {

            if (version === requestVersion) {

                const results = document.querySelector(
                    resultsSelector
                );

                if (results) {
                    results.setAttribute(
                        "aria-busy",
                        "false"
                    );
                }

                if (activeController === controller) {
                    activeController = null;
                }
            }
        }
    };

    /**
     * Schedule a filtered request.
     *
     * A delay prevents excessive requests while typing.
     */
    const scheduleUpdate = (delay = 350) => {

        window.clearTimeout(debounceTimer);

        // Invalidate previous results immediately.
        requestVersion += 1;

        if (activeController) {
            activeController.abort();
        }

        const version = requestVersion;
        const url = buildFilterUrl();

        debounceTimer = window.setTimeout(() => {

            updateTaskResults(url, version);

        }, delay);
    };

    // Search after the user stops typing.
    if (searchInput) {

        searchInput.addEventListener(
            "input",
            () => scheduleUpdate(400)
        );
    }

    // Dropdown changes apply immediately.
    dropdowns.forEach((dropdown) => {

        dropdown.addEventListener(
            "change",
            () => scheduleUpdate(0)
        );

    });

    // The Apply Filters button also works without JS.
    // With JS enabled, it updates without a page refresh.
    form.addEventListener("submit", (event) => {

        event.preventDefault();
        scheduleUpdate(0);

    });
};

// Initialize when the DOM is ready.
if (document.readyState === "loading") {

    document.addEventListener(
        "DOMContentLoaded",
        initializeTaskFilters
    );

} else {

    initializeTaskFilters();

}