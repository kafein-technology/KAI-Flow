# @kaiflow/widget

A customizable, React-based chat widget developed for the KAI Fusion AI platform. This component allows you to easily integrate your KAI Fusion workflows into your website.

## Features

- 🚀 **Easy Integration:** Add to your site with a single React component.
- 🎨 **Customizable:** Settings for color, title, and position.
- 📝 **Markdown Support:** Support for mathematical formulas (KaTeX), code blocks (Syntax Highlighting), and GFM.
- 📱 **Responsive:** Modern design compatible with mobile and desktop.
- ⚡ **Real-Time:** Fast interaction with streaming response support.

## Installation

You can use your favorite package manager to add the package to your project:

```bash
npm install @kaiflow/widget
# or
yarn add @kaiflow/widget
# or
pnpm add @kaiflow/widget
```

## Requirements

This package requires the following peer dependencies:

- React >= 18.0.0
- React DOM >= 18.0.0

## Usage

You can add the component to your React application as follows:

```tsx
import { KaiChatWidget } from "@kaiflow/widget";
// import '@kaiflow/widget/dist/style.css'; // Don't forget to include the style file if needed

function App() {
  return (
    <div className="App">
      {/* Other application content */}

      <KaiChatWidget
        targetUrl="http://localhost:8000" // Backend API address
        workflowId="your-workflow-id-value" // ID of the workflow to execute
        authToken="your-api-key-or-token" // API authorization key or token
        title="KAI Assistant" // (Optional) Widget title
        position="right" // (Optional) 'left' or 'right'
        color="#526cfe" // (Optional) Main theme color hex code
        icon={"💬"} // (Optional) Custom icon for the toggle button
      />
    </div>
  );
}

export default App;
```

## Props

| Prop         | Type                | Required | Default         | Description                                                                  |
| ------------ | ------------------- | -------- | --------------- | ---------------------------------------------------------------------------- |
| `targetUrl`  | `string`            | **Yes**  | -               | The address of the KAI Fusion backend API (e.g., `https://api.example.com`). |
| `workflowId` | `string`            | **Yes**  | -               | Unique identifier (UUID) of the workflow to run.                             |
| `authToken`  | `string`            | **Yes**  | -               | Bearer token or API Key for API access.                                      |
| `title`      | `string`            | No       | `"ChatBot"`     | Title of the widget window.                                                  |
| `position`   | `"left" \| "right"` | No       | `"right"`       | Position of the widget on the screen (bottom-left or bottom-right).          |
| `color`      | `string`            | No       | `"#526cfe"`     | Main theme color of the widget (Hex code).                                   |
| `icon`       | `ReactNode`         | No       | `MessageSquare` | Custom icon for the toggle button.                                           |

## Standalone Usage (HTML / MkDocs)

You can also use the widget in non-React projects or static sites (like MkDocs) by including the standalone script.

### HTML Integration

Add the following script tag to your HTML file:

```html
<script
  src="https://cdn.jsdelivr.net/npm/@kaiflow/widget@1.0.6/dist/widget.iife.js"
  data-title="KAI Fusion Assistant"
  data-auth-token="your-auth-token"
  data-workflow-id="your-workflow-id"
  data-target-url="http://localhost:8000"
  data-position="right"
  data-color="#526cfe"
  defer
></script>
```

### MkDocs Integration

For MkDocs, you can inject the script dynamically using JavaScript.

1. Create a javascript file (e.g `docs/js/kai-widget.js`) with the following content:

```javascript
document.addEventListener("DOMContentLoaded", function () {
  const script = document.createElement("script");
  script.src =
    "https://cdn.jsdelivr.net/npm/@kaiflow/widget@1.0.6/dist/widget.iife.js"; // Adjust URL to your source
  script.dataset.title = "KAI Fusion Assistant";
  script.dataset.authToken = "your-auth-token";
  script.dataset.workflowId = "your-workflow-id";
  script.dataset.targetUrl = "http://localhost:8000";
  script.dataset.position = "right";
  script.dataset.color = "#526cfe";
  document.body.appendChild(script);
});
```

2. Register the script in your `mkdocs.yml`:

```yaml
extra_javascript:
  - js/kai-widget.js
```
