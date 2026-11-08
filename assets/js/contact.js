
"use strict";

/**
 * TaskFlow | ACG Career Services
 * Contact form validation and confirmation popup.
 *
 * Demonstration only: no email is sent.
 */

function isValidEmail(email) {
  if (email.length === 0 || email.length > 150) {
    return false;
  }

  if (email.includes("..")) {
    return false;
  }

  const emailPattern =
    /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+$/;

  return emailPattern.test(email);
}

/**
 * Create an accessible confirmation dialog.
 * Uses safe DOM methods instead of innerHTML.
 */
function createConfirmationDialog() {
  const dialog = document.createElement("dialog");
  dialog.className = "contact-confirmation-dialog";
  dialog.setAttribute(
    "aria-labelledby",
    "contact-confirmation-title"
  );

  const heading = document.createElement("h2");
  heading.id = "contact-confirmation-title";
  heading.textContent = "Message Confirmation";

  const notice = document.createElement("p");
  notice.textContent =
    "Your message passed validation. " +
    "This is a demonstration form; no email was sent.";

  const details = document.createElement("dl");
  details.className = "contact-confirmation-details";

  function addDetail(label, value) {
    const term = document.createElement("dt");
    term.textContent = label;

    const description = document.createElement("dd");
    description.textContent = value;

    details.append(term, description);
  }

  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.className = "contact-confirmation-close";
  closeButton.textContent = "Close";

  closeButton.addEventListener("click", () => {
    dialog.close();
  });

  dialog.append(heading, notice, details, closeButton);
  document.body.appendChild(dialog);

  return {
    dialog,
    details,
    addDetail,
    closeButton
  };
}

/**
 * Initialize contact form.
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

  const confirmation = createConfirmationDialog();

  /**
   * Display feedback beneath the form.
   */
  function showFeedback(message, type = "error") {
    feedback.textContent = message;

    feedback.classList.remove(
      "contact-feedback-error",
      "contact-feedback-success"
    );

    feedback.classList.add(
      type === "success"
        ? "contact-feedback-success"
        : "contact-feedback-error"
    );
  }

  /**
   * Mark an invalid field and focus it.
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
   * Clear previous feedback.
   */
  function clearFeedback() {
    feedback.textContent = "";

    feedback.classList.remove(
      "contact-feedback-error",
      "contact-feedback-success"
    );
  }

  /**
   * Remove error indicators when fields are edited.
   */
  fields.forEach((field) => {
    const eventType =
      field.tagName === "SELECT" ? "change" : "input";

    field.addEventListener(eventType, () => {
      field.classList.remove("contact-input-error");
      field.removeAttribute("aria-invalid");
      clearFeedback();
    });
  });

  /**
   * Validate and process form submission.
   */
  form.addEventListener("submit", (event) => {
    event.preventDefault();

    const nameValue = nameInput.value.trim();
    const emailValue = emailInput.value.trim();
    const subjectValue = subjectInput.value;
    const messageValue = messageInput.value.trim();

    fields.forEach((field) => {
      field.classList.remove("contact-input-error");
      field.removeAttribute("aria-invalid");
    });

    clearFeedback();

    // 1. Validate name.
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

    // 2. Validate email.
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
    const selectedSubject =
      subjectInput.selectedOptions[0]?.textContent?.trim()
      || subjectValue;

    // Remove details from any previous submission.
    confirmation.details.replaceChildren();

    confirmation.addDetail("Full Name", nameValue);
    confirmation.addDetail("Email Address", emailValue);
    confirmation.addDetail("Subject", selectedSubject);
    confirmation.addDetail("Message", messageValue);

    showFeedback(
      "Your message passed validation. " +
      "This is a demonstration form; no email was sent.",
      "success"
    );

    // Display the confirmation popup.
    if (typeof confirmation.dialog.showModal === "function") {
      confirmation.dialog.showModal();
    } else {
      // Fallback for browsers without dialog support.
      window.alert(
        "Message Confirmation\n\n" +
        `Full Name: ${nameValue}\n` +
        `Email: ${emailValue}\n` +
        `Subject: ${selectedSubject}\n` +
        `Message: ${messageValue}\n\n` +
        "Demonstration only: no email was sent."
      );
    }

    // Reset the form only after validation succeeds.
    form.reset();

    console.info(
      "Contact form validated successfully. No email was sent."
    );
  });
}

initializeContactForm();
