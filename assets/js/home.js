
"use strict";

/**
 * TaskFlow | ACG Career Services
 * Home Page Functionality
 *
 * Features:
 * - Recent task activity
 * - Live remote job opportunities
 * - API loading and error handling
 * - Safe DOM manipulation
 */

import { loadTaskActivity } from "./task-activity.js";

// ========================================
// CONFIGURATION
// ========================================

const MAX_ACTIVITY_ITEMS = 5;
const MAX_JOB_ITEMS = 5;

const API_URL = "https://remotive.com/api/remote-jobs?limit=5";
const API_TIMEOUT_MS = 10000;

// ========================================
// RECENT TASK ACTIVITY
// ========================================

const ACTION_LABELS = {
  created: "Created",
  updated: "Updated",
  completed: "Completed",
  deleted: "Deleted",
  "status-changed": "Status changed"
};

/**
 * Format a timestamp into a readable date.
 */
function formatActivityDate(timestamp) {
  const date = new Date(timestamp);

  if (Number.isNaN(date.getTime())) {
    return "Unknown date";
  }

  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}

/**
 * Display the latest recorded task activities.
 */
function renderRecentActivity() {
  const activityList = document.querySelector(
    "#recent-activity-list"
  );

  const feedback = document.querySelector(
    "#activity-feedback"
  );

  if (!activityList) {
    return;
  }

  activityList.replaceChildren();

  const activities = loadTaskActivity()
    .sort((a, b) => {
      return new Date(b.timestamp) - new Date(a.timestamp);
    })
    .slice(0, MAX_ACTIVITY_ITEMS);

  if (activities.length === 0) {
    const emptyItem = document.createElement("li");

    emptyItem.className = "activity-empty";
    emptyItem.textContent =
      "No recent activity yet. Create or update a task to get started.";

    activityList.appendChild(emptyItem);

    if (feedback) {
      feedback.textContent = "";
    }

    return;
  }

  activities.forEach((activity) => {
    const item = document.createElement("li");
    item.className = "activity-item";

    const content = document.createElement("div");
    content.className = "activity-content";

    const action = document.createElement("strong");
    action.className = "activity-action";

    action.textContent =
      ACTION_LABELS[activity.action] || "Updated";

    const title = document.createElement("span");
    title.className = "activity-title";
    title.textContent = ` — ${activity.title}`;

    const date = document.createElement("time");
    date.className = "activity-date";
    date.dateTime = activity.timestamp;
    date.textContent = formatActivityDate(
      activity.timestamp
    );

    content.append(action, title);
    item.append(content, date);

    activityList.appendChild(item);
  });

  if (feedback) {
    feedback.textContent =
      `Showing ${activities.length} recent task activities.`;
  }
}

// ========================================
// LIVE CAREER INSIGHTS API
// ========================================

/**
 * Display a status message.
 */
function setApiStatus(message) {
  const status = document.querySelector("#api-status");

  if (status) {
    status.textContent = message;
  }
}

/**
 * Create a safe external job link.
 */
function createJobLink(job) {
  const link = document.createElement("a");

  link.textContent = "View Opportunity";
  link.className = "button button-primary";

  try {
    const url = new URL(job.url);

    if (
      url.protocol === "https:" ||
      url.protocol === "http:"
    ) {
      link.href = url.href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";

      return link;
    }
  } catch (error) {
    console.warn("Invalid job URL:", error);
  }

  link.removeAttribute("href");
  link.textContent = "Link unavailable";

  return link;
}

/**
 * Display remote job opportunities.
 */
function renderJobs(jobs) {
  const results = document.querySelector("#api-results");

  if (!results) {
    return;
  }

  results.replaceChildren();

  if (!Array.isArray(jobs) || jobs.length === 0) {
    setApiStatus(
      "No job opportunities are currently available."
    );

    return;
  }

  const fragment = document.createDocumentFragment();

  jobs.slice(0, MAX_JOB_ITEMS).forEach((job) => {
    if (!job || typeof job !== "object") {
      return;
    }

    const card = document.createElement("article");
    card.className = "job-card";

    const title = document.createElement("h4");
    title.className = "job-title";

    title.textContent =
      typeof job.title === "string"
        ? job.title.slice(0, 200)
        : "Untitled opportunity";

    const company = document.createElement("p");
    company.className = "job-company";

    company.textContent =
      typeof job.company_name === "string"
        ? `Company: ${job.company_name.slice(0, 150)}`
        : "Company: Not specified";

    const location = document.createElement("p");
    location.className = "job-location";

    location.textContent =
      typeof job.candidate_required_location === "string"
        ? `Location: ${job.candidate_required_location.slice(0, 150)}`
        : "Location: Remote";

    card.append(title, company, location);

    if (typeof job.url === "string") {
      card.appendChild(createJobLink(job));
    }

    fragment.appendChild(card);
  });

  results.appendChild(fragment);

  setApiStatus(
    `Showing ${results.children.length} live remote job opportunities.`
  );
}

/**
 * Fetch remote jobs from the public API.
 */
async function fetchCareerInsights() {
  const refreshButton = document.querySelector(
    "#refresh-insights"
  );

  const results = document.querySelector("#api-results");

  if (!results) {
    return;
  }

  if (refreshButton) {
    refreshButton.disabled = true;
    refreshButton.textContent = "Loading...";
  }

  setApiStatus("Loading career insights...");

  const controller = new AbortController();

  const timeoutId = setTimeout(() => {
    controller.abort();
  }, API_TIMEOUT_MS);

  try {
    const response = await fetch(API_URL, {
      method: "GET",
      signal: controller.signal,
      headers: {
        Accept: "application/json"
      }
    });

    if (!response.ok) {
      throw new Error(
        `API request failed with status ${response.status}`
      );
    }

    const data = await response.json();

    if (!data || !Array.isArray(data.jobs)) {
      throw new Error("Unexpected API response format.");
    }

    renderJobs(data.jobs);
  } catch (error) {
    console.error("Career insights error:", error);

    results.replaceChildren();

    if (error.name === "AbortError") {
      setApiStatus(
        "The request timed out. Please try again."
      );
    } else {
      setApiStatus(
        "Career insights are temporarily unavailable. " +
        "Please try refreshing."
      );
    }
  } finally {
    clearTimeout(timeoutId);

    if (refreshButton) {
      refreshButton.disabled = false;
      refreshButton.textContent = "Refresh Insights";
    }
  }
}

// ========================================
// INITIALIZATION
// ========================================

function initializeHomePage() {
  renderRecentActivity();

  const refreshButton = document.querySelector(
    "#refresh-insights"
  );

  if (refreshButton) {
    refreshButton.addEventListener(
      "click",
      fetchCareerInsights
    );
  }

  // Update activity when another tab changes storage.
  window.addEventListener("storage", (event) => {
    if (event.key === "taskflow-activity") {
      renderRecentActivity();
    }
  });

  // Refresh the activity feed when returning to this tab.
  window.addEventListener("pageshow", () => {
    renderRecentActivity();
  });

  fetchCareerInsights();
}

initializeHomePage();
