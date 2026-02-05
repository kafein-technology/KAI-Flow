import React, { useState } from "react";
import { AlertTriangle, AlertCircle, Bug, Zap, RefreshCw, Info, X } from "~/icons/index";

interface ErrorDetails {
  message: string;
  type?: string;
  nodeId?: string;
  nodeType?: string;
  timestamp?: string;
  stackTrace?: string;
  suggestions?: string[];
}

interface ErrorDisplayComponentProps {
  error: ErrorDetails | string | null;
  onRetry?: () => void;
  onDismiss?: () => void;
  className?: string;
}

const getErrorIcon = (errorType?: string) => {
  switch (errorType?.toLowerCase()) {
    case "validation":
      return <AlertCircle className="h-5 w-5 text-orange-500" />;
    case "network":
      return <Zap className="h-5 w-5 text-blue-500" />;
    case "execution":
      return <Bug className="h-5 w-5 text-red-500" />;
    default:
      return <AlertTriangle className="h-5 w-5 text-red-500" />;
  }
};

const getErrorColor = (errorType?: string) => {
  switch (errorType?.toLowerCase()) {
    case "validation":
      return "bg-orange-50 border-orange-200 text-orange-800";
    case "network":
      return "bg-blue-50 border-blue-200 text-blue-800";
    case "execution":
      return "bg-red-50 border-red-200 text-red-800";
    default:
      return "bg-red-50 border-red-200 text-red-800";
  }
};

const getErrorSuggestions = (
  errorType?: string,
  nodeType?: string
): string[] => {
  const baseSuggestions = [
    "Check your workflow configuration",
    "Verify all required credentials are set",
    "Ensure all nodes are properly connected",
  ];

  switch (errorType?.toLowerCase()) {
    case "validation":
      return [
        "Review node configuration settings",
        "Check input/output data types",
        "Verify required fields are filled",
      ];
    case "network":
      return [
        "Check your internet connection",
        "Verify API endpoints are accessible",
        "Check API rate limits and quotas",
      ];
    case "execution":
      return [
        "Review node execution order",
        "Check for circular dependencies",
        "Verify input data format",
      ];
    default:
      return baseSuggestions;
  }

  // Node-specific suggestions
  if (nodeType) {
    switch (nodeType?.toLowerCase()) {
      case "openainode":
        return [
          ...baseSuggestions,
          "Verify OpenAI API key",
          "Check API quota limits",
        ];
      case "webscraper":
        return [
          ...baseSuggestions,
          "Check target URL accessibility",
          "Verify scraping permissions",
        ];
      case "documentloader":
        return [
          ...baseSuggestions,
          "Check file path and permissions",
          "Verify file format support",
        ];
      default:
        return baseSuggestions;
    }
  }

  return baseSuggestions;
};

export default function ErrorDisplayComponent({
  error,
  onRetry,
  onDismiss,
  className = "",
}: ErrorDisplayComponentProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!error) return null;

  // Normalize error to ErrorDetails format
  const errorDetails: ErrorDetails =
    typeof error === "string" ? { message: error } : error;

  const {
    message,
    type = "execution",
    nodeId,
    nodeType,
    timestamp = new Date().toLocaleTimeString(),
    stackTrace,
    suggestions = getErrorSuggestions(type, nodeType),
  } = errorDetails;

  const errorColor = getErrorColor(type);
  const errorIcon = getErrorIcon(type);

  return (
    <div className={`absolute top-20 left-4 z-50 max-w-lg ${className}`}>
      <div
        className={`${errorColor} border rounded-lg shadow-lg overflow-hidden`}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-current border-opacity-20">
          <div className="flex items-center space-x-2">
            {errorIcon}
            <div>
              <h3 className="font-semibold text-sm capitalize">{type} Error</h3>
              {nodeId && (
                <p className="text-xs opacity-75">
                  Node: {nodeId} {nodeType && `(${nodeType})`}
                </p>
              )}
            </div>
          </div>
          <div className="flex items-center space-x-2">
            {onRetry && (
              <button
                onClick={onRetry}
                className="p-1 hover:bg-current hover:bg-opacity-10 rounded transition-colors"
                title="Retry execution"
              >
                <RefreshCw className="h-4 w-4" />
              </button>
            )}
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="p-1 hover:bg-current hover:bg-opacity-10 rounded transition-colors"
              title={isExpanded ? "Collapse" : "Expand"}
            >
              <Info className="h-4 w-4" />
            </button>
            {onDismiss && (
              <button
                onClick={onDismiss}
                className="p-1 hover:bg-current hover:bg-opacity-10 rounded transition-colors"
                title="Dismiss error"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>

        {/* Error Message */}
        <div className="p-4">
          <p className="text-sm font-medium mb-3">{message}</p>

          {/* Timestamp */}
          <p className="text-xs opacity-60 mb-3">
            Error occurred at {timestamp}
          </p>

          {/* Expandable Details */}
          {isExpanded && (
            <div className="space-y-3 pt-3 border-t border-current border-opacity-20">
              {/* Suggestions */}
              {suggestions.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold mb-2 opacity-75">
                    Suggested Solutions:
                  </h4>
                  <ul className="text-xs space-y-1">
                    {suggestions.map((suggestion, index) => (
                      <li key={index} className="flex items-start space-x-2">
                        <span className="text-current opacity-60">•</span>
                        <span>{suggestion}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Stack Trace (if available) */}
              {stackTrace && (
                <div>
                  <h4 className="text-xs font-semibold mb-2 opacity-75">
                    Technical Details:
                  </h4>
                  <pre className="text-xs bg-current bg-opacity-5 p-2 rounded overflow-auto max-h-32">
                    {stackTrace}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
