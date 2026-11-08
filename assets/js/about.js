
"use strict";

/* ==========================================
   TASKFLOW | ACG CAREER SERVICES
   ABOUT PAGE CAROUSEL
   ========================================== */

/**
 * Carousel slides and their content.
 */
const carouselSlides = [
  {
    title: "Organize Tasks",
    description:
      "Create tasks, assign priorities, and manage deadlines efficiently.",
    image: "assets/images/team/carousel/tasks.png",
    alt: "TaskFlow Tasks page showing task management features"
  },
  {
    title: "Visualize Workflows",
    description:
      "Move tasks between Pending, In Progress, and Completed using the interactive Kanban board.",
    image: "assets/images/team/carousel/kanban.png",
    alt: "TaskFlow Kanban board showing workflow columns"
  },
  {
    title: "Monitor Progress",
    description:
      "Review task statistics, completion rates, and priorities using the Analytics dashboard.",
    image: "assets/images/team/carousel/analytics.png",
    alt: "TaskFlow Analytics dashboard showing task statistics"
  }
];

/**
 * Initialize the About page carousel.
 */
function initializeAboutCarousel() {

  // Carousel elements
  const slide = document.querySelector(
    "#about-carousel-slide"
  );

  const image = document.querySelector(
    "#about-carousel-img"
  );

  const title = document.querySelector(
    "#about-carousel-title"
  );

  const description = document.querySelector(
    "#about-carousel-description"
  );

  const featureLabel = document.querySelector(
    "#about-carousel-feature"
  );

  // Navigation buttons
  const previousButton = document.querySelector(
    "#carousel-previous"
  );

  const nextButton = document.querySelector(
    "#carousel-next"
  );

  // Slide indicators
  const indicators = [
    ...document.querySelectorAll(
      ".about-carousel-indicator"
    )
  ];

  // Accessible status announcements
  const status = document.querySelector(
    "#carousel-status"
  );

  // Stop if required elements are missing.
  if (
    !slide ||
    !image ||
    !title ||
    !description ||
    !previousButton ||
    !nextButton
  ) {
    console.warn(
      "TaskFlow carousel: Required HTML elements were not found."
    );

    return;
  }

  // Current slide index
  let currentSlide = 0;

  /**
   * Display the selected carousel slide.
   *
   * @param {number} index - Requested slide index.
   */
  function showSlide(index) {

    // Keep the index within the available slides.
    currentSlide =
      ((index % carouselSlides.length) +
        carouselSlides.length) %
      carouselSlides.length;

    const selected = carouselSlides[currentSlide];

    // Update the screenshot.
    image.src = selected.image;
    image.alt = selected.alt;

    // Update the slide content.
    title.textContent = selected.title;
    description.textContent = selected.description;

    // Update the feature number.
    if (featureLabel) {
      featureLabel.textContent =
        `FEATURE ${String(currentSlide + 1).padStart(2, "0")}`;
    }

    // Update the slide's accessibility label.
    slide.setAttribute(
      "aria-label",
      `Slide ${currentSlide + 1} of ${carouselSlides.length}`
    );

    // Update navigation indicators.
    indicators.forEach((indicator, position) => {

      const isActive = position === currentSlide;

      indicator.classList.toggle(
        "is-active",
        isActive
      );

      if (isActive) {
        indicator.setAttribute(
          "aria-current",
          "true"
        );
      } else {
        indicator.removeAttribute(
          "aria-current"
        );
      }

    });

    // Announce slide changes to screen readers.
    if (status) {
      status.textContent =
        `${selected.title}, slide ${currentSlide + 1} of ${carouselSlides.length}.`;
    }
  }

  /* ==========================================
     PREVIOUS BUTTON
     ========================================== */

  previousButton.addEventListener("click", () => {
    showSlide(currentSlide - 1);
  });

  /* ==========================================
     NEXT BUTTON
     ========================================== */

  nextButton.addEventListener("click", () => {
    showSlide(currentSlide + 1);
  });

  /* ==========================================
     SLIDE INDICATORS
     ========================================== */

  indicators.forEach((indicator, position) => {

    indicator.addEventListener("click", () => {

      const requestedIndex = Number(
        indicator.dataset.slide
      );

      // Use the indicator position if no valid
      // data-slide attribute is provided.
      const index = (
        indicator.dataset.slide !== undefined &&
        Number.isInteger(requestedIndex) &&
        requestedIndex >= 0 &&
        requestedIndex < carouselSlides.length
      )
        ? requestedIndex
        : position;

      if (index < carouselSlides.length) {
        showSlide(index);
      }

    });

  });

  /* ==========================================
     INITIAL DISPLAY
     ========================================== */

  showSlide(0);

  console.info(
    "TaskFlow About carousel initialized successfully."
  );
}

/**
 * Start the carousel after the HTML is available.
 */
if (document.readyState === "loading") {
  document.addEventListener(
    "DOMContentLoaded",
    initializeAboutCarousel
  );
} else {
  initializeAboutCarousel();
}
