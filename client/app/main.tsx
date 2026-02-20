import { createRoot } from "react-dom/client";
import App from "./App";
import { BrowserRouter } from "react-router";

const basePath = window.VITE_BASE_PATH;

createRoot(document.getElementById("root")!).render(
  <BrowserRouter basename={basePath}>
    <App />
  </BrowserRouter>
);
