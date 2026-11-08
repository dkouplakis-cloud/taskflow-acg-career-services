# TaskFlow | ACG Career Services

TaskFlow is a student-developed web application designed to support task management, activity coordination, and progress monitoring for the ACG Career Services Office at The American College of Greece.

The application provides a centralized workspace for organizing responsibilities, managing deadlines, visualizing task progress, and accessing live remote job opportunities.

## 1. Project Information

- **Course:** ITC4214 – Internet Programming
- **Project:** Midterm Group Coursework
- **Application:** TaskFlow
- **Organization:** ACG Career Services Office
- **Project Type:** Front-End Web Application
- **Status:** Functional academic prototype

## 2. Project Objectives

TaskFlow aims to:

- Simplify the creation, editing, and management of tasks.
- Support task prioritization and deadline tracking.
- Provide searching, sorting, and filtering functionality.
- Visualize task progress through an interactive Kanban board.
- Present task statistics and analytics.
- Display recent task activity.
- Retrieve live remote job opportunities from a public API.
- Provide responsive and accessible user interfaces.

## 3. Application Pages

### Home (`index.html`)

The Home page introduces TaskFlow and provides an overview of the application.

Features include:

- Welcome section and navigation buttons.
- Dashboard showing total, pending, in-progress, and completed tasks.
- Recent task activity.
- Live remote job opportunities retrieved from the Remotive API.
- Company logos, job titles, locations, and external opportunity links.
- Overview of the application's main features.

### Tasks (`tasks.html`)

The Tasks page provides task management functionality.

Features include:

- Creating new tasks.
- Editing existing tasks.
- Deleting tasks.
- Marking tasks as completed.
- Setting task priorities and due dates.
- Searching, filtering, and sorting tasks.
- Viewing task information in a structured table.
- Persisting task information using browser localStorage.

### Analytics (`analytics.html`)

The Analytics page visualizes task-related information.

Features include:

- Total task statistics.
- Task completion rate.
- Task status distribution.
- Priority-based task information.
- Visual representations of task progress.

### Kanban (`kanban.html`)

The Kanban page provides a visual task management interface.

Tasks are organized into three workflow stages:

- Pending
- In Progress
- Completed

Users can manage task progress through interactive cards, status controls, and drag-and-drop functionality.

Task status changes are synchronized with the shared task data.

### About (`about.html`)

The About page presents information about TaskFlow and its intended organizational context.

Features include:

- Application description.
- Overview of TaskFlow features.
- ACG Career Services team information.
- Interactive image carousel demonstrating the application.

### Contact (`contact.html`)

The Contact page provides a demonstration contact form and information about the ACG Career Services Office.

Features include:

- Form fields for name, email, subject, and message.
- Client-side form validation.
- Confirmation popup displaying submitted information.
- Career Services contact information.
- Embedded Google Maps.
- Official website and Instagram links.

The contact form is a demonstration feature and does not send messages to an email server.

## 4. Technologies Used

- **HTML5:** Semantic page structure.
- **CSS3:** External stylesheets and custom responsive design.
- **Bootstrap 5:** CSS framework and responsive utilities.
- **JavaScript ES6+:** Application functionality and DOM manipulation.
- **Chart.js:** Task data visualization.
- **Browser localStorage:** Client-side task and preference persistence.
- **Fetch API:** Retrieval of external job opportunities.
- **Git:** Version control.
- **GitHub:** Source code repository and collaboration.

## 5. Project Structure

```text
taskflow-acg-career-services/
│
├── index.html
├── tasks.html
├── analytics.html
├── kanban.html
├── about.html
├── contact.html
├── README.md
│
└── assets/
    ├── css/
    │   └── styles.css
    │
    ├── js/
    │   ├── main.js
    │   ├── home.js
    │   ├── tasks.js
    │   ├── analytics.js
    │   ├── kanban.js
    │   ├── about.js
    │   ├── contact.js
    │   └── task-activity.js
    │
    └── images/
        └── team/
            └── carousel/
                ├── tasks.png
                ├── kanban.png
                └── analytics.png
```

Additional image assets may be present in the images directory.

## 6. Installation and Execution

### Prerequisites

- A modern web browser, such as Google Chrome or Microsoft Edge.
- Visual Studio Code.
- The Live Server extension for Visual Studio Code.
- Internet access for external libraries and live API data.

### Instructions

1. Clone the GitHub repository:

   ```bash
   git clone https://github.com/dkouplakis-cloud/taskflow-acg-career-services.git
   ```

2. Open the project folder in Visual Studio Code.

3. Install the Live Server extension if it is not already installed.

4. Right-click `index.html` and select **Open with Live Server**.

5. The application should open in the browser at an address similar to:

   `http://127.0.0.1:5500/index.html`

6. Use the navigation menu to access the application's six pages.

No backend server or database installation is required.

## 7. Data Storage

TaskFlow uses browser localStorage to persist application data.

This allows users to retain task information and selected preferences when refreshing or reopening the application in the same browser environment.

Because the application is a front-end academic prototype, data is not automatically synchronized between different devices or browsers.

## 8. External API Integration

The Home page retrieves live remote job opportunities from the public Remotive API.

**API endpoint:**

`https://remotive.com/api/remote-jobs?limit=5`

The application dynamically displays available opportunities and provides links to their original listings.

The implementation includes loading feedback, response validation, request timeout handling, and error messages.

Job information is supplied by an external service and may change or become temporarily unavailable.

## 9. Development Standards

The project follows these development practices:

- Semantic HTML5 structure.
- External CSS stylesheets.
- No inline JavaScript event handlers.
- Modular JavaScript files.
- DOM selection using `querySelector()` and related methods.
- Event handling using `addEventListener()`.
- Client-side input validation.
- Safe DOM manipulation.
- Responsive layout techniques.
- Accessibility attributes and descriptive labels.
- Git-based version control.

## 10. Testing and Validation

The application should be tested for:

- Task creation, editing, deletion, and completion.
- Task search, sorting, and filtering.
- Data persistence after page refresh.
- Synchronization between Tasks, Analytics, and Kanban.
- Contact form validation and confirmation.
- Dark mode persistence.
- Mobile navigation and responsive layouts.
- Handling of unusually long user inputs.
- API loading and error handling.
- Accessibility and browser compatibility.

Browser Developer Tools and Lighthouse can be used to evaluate application quality.

## 11. Limitations

TaskFlow is a front-end academic prototype.

- Task information is stored locally in the user's browser.
- The contact form does not send actual emails.
- Live job opportunities depend on the availability of the Remotive API.
- The application does not provide user accounts or a production backend.

## 12. Academic Disclaimer

TaskFlow was developed as an academic coursework project for ITC4214 Internet Programming at The American College of Greece.

The application uses ACG Career Services as its organizational context but is not an officially deployed or endorsed ACG service.

## 13. Repository

GitHub:

https://github.com/dkouplakis-cloud/taskflow-acg-career-services
