
"use strict";

/**
 * TaskFlow | ACG Career Services
 * Contact form validation and submission handling.
 *
 * This is a demonstration form.
 * No messages are sent to a server.
 */

/**
 * Validate an email address.
 *
 * @param {string} email
 * @returns {boolean}
 */
function isValidEmail(email) {
  if (email.length === 0 || email.length > 150) {
    return false;
  }

  if (email.includes("..")) {
    return false;
  }

  // Require a valid local part and a domain with a suffix.
  const emailPattern =
    /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+$/;

  return emailPattern.test(email);
}

/**
 * Initialize the contact form.
 */
function initializeContactForm() {
  const form = document.querySelector("#contact-form");
  const feedback = document.querySelector("#contact-feedback");

  if (!form || !feedback) {
    return;
  }

  const nameInput = form.querySelector("#contact-name");
  const emailInput = form.querySelector("#contact-email");
  const subjectInput = form.querySelector("#contact-subject");
  const messageInput = form.querySelector("#contact-message");

  if (
    !nameInput ||
    !emailInput ||
    !subjectInput ||
    !messageInput
  ) {
    console.error("Contact form fields are missing.");
    return;
  }

  const fields = [
    nameInput,
    emailInput,
    subjectInput,
    messageInput
  ];

  const allowedSubjects = [
    "feedback",
    "suggestion",
    "issue",
    "other"
  ];

  /**
   * Display a feedback message.
   *
   * @param {string} message
   * @param {string} type
   */
  function showFeedback(message, type = "error") {
    feedback.textContent = message;

    feedback.classList.remove(
      "contact-feedback-error",
      "contact-feedback-success"
    );

    if (type === "success") {
      feedback.classList.add("contact-feedback-success");
    } else {
      feedback.classList.add("contact-feedback-error");
    }
  }

  /**
   * Mark a field as invalid.
   *
   * @param {HTMLElement} field
   * @param {string} message
   */
  function showFieldError(field, message) {
    fields.forEach((input) => {
      input.classList.remove("contact-input-error");
      input.removeAttribute("aria-invalid");
    });

    field.classList.add("contact-input-error");
    field.setAttribute("aria-invalid", "true");

    showFeedback(message, "error");
    field.focus();
  }

  /**
   * Remove previous validation feedback.
   */
  function clearFeedback() {
    feedback.textContent = "";

    feedback.classList.remove(
      "contact-feedback-error",
      "contact-feedback-success"
    );
  }

  /**
   * Clear a field's error state when edited.
   */
  fields.forEach((field) => {
    const eventType =
      field.tagName === "SELECT" ? "change" : "input";

    field.addEventListener(eventType, () => {
      field.classList.remove("contact-input-error");
      field.removeAttribute("aria-invalid");

      // Remove old feedback when the user edits the form.
      clearFeedback();
    });
  });

  /**
   * Handle form submission.
   */
  form.addEventListener("submit", (event) => {
    event.preventDefault();

    // Read and normalize the form values.
    const nameValue = nameInput.value.trim();
    const emailValue = emailInput.value.trim();
    const subjectValue = subjectInput.value;
    const messageValue = messageInput.value.trim();

    // Clear previous error indicators.
    fields.forEach((field) => {
      field.classList.remove("contact-input-error");
      field.removeAttribute("aria-invalid");
    });

    clearFeedback();

    // 1. Validate full name.
    if (nameValue.length === 0) {
      showFieldError(
        nameInput,
        "Please enter your full name."
      );
      return;
    }

    if (nameValue.length > 100) {
      showFieldError(
        nameInput,
        "Your full name must not exceed 100 characters."
      );
      return;
    }

    // 2. Validate email address.
    if (emailValue.length === 0) {
      showFieldError(
        emailInput,
        "Please enter your email address."
      );
      return;
    }

    if (emailValue.length > 150) {
      showFieldError(
        emailInput,
        "Your email address must not exceed 150 characters."
      );
      return;
    }

    if (!isValidEmail(emailValue)) {
      showFieldError(
        emailInput,
        "Please enter a valid email address, such as name@example.com."
      );
      return;
    }

    // 3. Validate subject.
    if (!allowedSubjects.includes(subjectValue)) {
      showFieldError(
        subjectInput,
        "Please select a valid subject."
      );
      return;
    }

    // 4. Validate message.
    if (messageValue.length === 0) {
      showFieldError(
        messageInput,
        "Please enter your message."
      );
      return;
    }

    if (messageValue.length < 10) {
      showFieldError(
        messageInput,
        "Your message must contain at least 10 characters."
      );
      return;
    }

    if (messageValue.length > 2000) {
      showFieldError(
        messageInput,
        "Your message must not exceed 2,000 characters."
      );
      return;
    }

    // 5. All validation checks passed.
    showFeedback(
      "Your message passed validation. " +
      "This is a demonstration form; no email was sent.",
      "success"
    );

    // Reset the form after successful validation.
    form.reset();

    console.info(
      "Contact form validated successfully. No message was sent."
    );
  });
}

// Initialize contact form functionality.
initializeContactForm();
