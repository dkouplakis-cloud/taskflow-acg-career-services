
"use strict";

/**
 * TaskFlow | ACG Career Services
 * Contact form validation and submission handling.
 *
 * This form demonstrates client-side validation.
 * No messages are transmitted to a server.
 */

/**
 * Check whether an email address has a valid structure.
 *
 * @param {string} email - Email address to validate.
 * @returns {boolean} Whether the format is acceptable.
 */
function isValidEmail(email) {
  const emailPattern =
    /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+$/;

  return (
    email.length <= 254 &&
    !email.includes("..") &&
    emailPattern.test(email)
  );
}

/**
 * Initialize contact form validation.
 */
function initializeContactForm() {
  const form = document.querySelector("#contact-form");
  const feedback = document.querySelector("#contact-feedback");

  if (!form || !feedback) {
    return;
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();

    const name = document.querySelector("#contact-name");
    const email = document.querySelector("#contact-email");
    const subject = document.querySelector("#contact-subject");
    const message = document.querySelector("#contact-message");

    // Remove unnecessary whitespace.
    const nameValue = name.value.trim();
    const emailValue = email.value.trim();
    const messageValue = message.value.trim();

    // Validate the full name.
    if (!nameValue) {
      feedback.textContent = "Please enter your full name.";
      name.focus();
      return;
    }

    // Validate email structure.
    if (!isValidEmail(emailValue)) {
      feedback.textContent =
        "Please enter a valid email address, such as name@example.com.";

      email.focus();
      return;
    }

    // Validate subject selection.
    if (!subject.value) {
      feedback.textContent = "Please select a subject.";
      subject.focus();
      return;
    }

    // Validate message length.
    if (messageValue.length < 10) {
      feedback.textContent =
        "Your message must contain at least 10 characters.";

      message.focus();
      return;
    }

    // Demonstration only: no email is sent.
    feedback.textContent =
      "Your message passed validation. " +
      "This is a demonstration form; no email was sent.";

    form.reset();
  });
}

// Initialize contact form functionality.
initializeContactForm();
