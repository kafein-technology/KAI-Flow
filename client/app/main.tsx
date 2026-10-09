import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { BrowserRouter } from "react-router";

// VITE_ENABLE_LOGGING now governs the application's browser console output,
// instead of only one API-client error branch.
if (window.VITE_ENABLE_LOGGING !== "true") {
  console.debug = () => {};
  console.log = () => {};
  console.info = () => {};
  console.warn = () => {};
  console.error = () => {};
}

const basePath = window.VITE_BASE_PATH;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter basename={basePath}>
      <App />
    </BrowserRouter>
  </StrictMode>
);
