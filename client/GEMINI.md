# KAI-Flow Client

This document provides an overview of the KAI-Flow client project, its structure, and key commands.

## Overview

This project is a React-based web client for KAI-Flow, a workflow management tool. It uses React Router for navigation, Zustand for state management, and Vite for the build tooling. The application features a canvas for building flows, various modals for configuration, and a dashboard for managing workflows.

## Commands

-   **`npm run dev`**: Starts the development server with hot reloading.
-   **`npm run build`**: Builds the application for production.
-   **`npm run test`**: Runs the test suite using Vitest.
-   **`npm run lint`**: Lints the codebase using ESLint to enforce code quality.
-   **`npm run typecheck`**: Runs the TypeScript compiler to check for type errors.

## Key Dependencies

### Core

-   **`react`**: The core library for building the user interface.
-   **`react-router`**: For handling routing and navigation within the application.
-   **`axios`**: For making HTTP requests to the backend API.
-   **`@xyflow/react`**: For the interactive flow canvas.

### UI

-   **`tailwindcss`**: For styling the application.
-   **`daisyui`**: A component library for Tailwind CSS.
-   **`lucide-react`**: For icons.
-   **`recharts`**: For charts and data visualization.

### State Management

-   **`zustand`**: For lightweight, global state management.
-   **`@tanstack/react-query`**: For managing server state, including caching, refetching, and optimistic updates.

### Development

-   **`vite`**: The build tool and development server.
-   **`vitest`**: The testing framework.
-   **`eslint`**: For static code analysis and enforcing code style.
-   **`typescript`**: For static typing.

## Project Structure

-   **`app/`**: Contains the core application code.
    -   **`components/`**: Reusable React components.
        -   **`canvas/`**: Components related to the main flow canvas.
        -   **`common/`**: Shared components like Navbar, Sidebar, etc.
        -   **`modals/`**: Modals for configuring different node types.
        -   **`nodes/`**: Components that represent the different nodes on the canvas.
    -   **`lib/`**: Utility functions and API client configuration.
    -   **`routes/`**: Top-level route components.
    -   **`services/`**: Services for interacting with the backend API.
    -   **`stores/`**: Zustand stores for managing application state.
-   **`src/`**: Contains setup and configuration files.
-   **`public/`**: Static assets that are publicly accessible.
