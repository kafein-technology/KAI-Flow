import { useEffect, useState, useCallback } from 'react';
import { config } from './config';

export const useLogStream = (isEnabled: boolean) => {
  const [logs, setLogs] = useState<string[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const clearLogs = useCallback(() => {
    setLogs([]);
  }, []);

  useEffect(() => {
    if (!isEnabled) {
      setIsConnected(false);
      return;
    }

    const base = config.API_BASE_URL;
    const version = config.API_VERSION;

    if (!base) {
      console.error("[LogStream] Connection error: API_BASE_URL is not defined in config.");
      setError(new Error("API_BASE_URL is not defined"));
      setIsConnected(false);
      return;
    }
    
    let baseUrl = base;
    if (baseUrl.startsWith('//')) {
      baseUrl = window.location.protocol + baseUrl;
    }
    
    const url = `${baseUrl}${version}/logs/stream`;
    console.log("[LogStream] Connecting EventSource to:", url);

    const eventSource = new EventSource(url);

    eventSource.onopen = () => {
      console.log("[LogStream] EventSource connection opened successfully");
      setIsConnected(true);
      setError(null);
    };

    eventSource.onmessage = (event) => {
      const logText = event.data;
      if (logText && logText !== 'ping') {
        setLogs((prev) => {
          const combined = [...prev, logText];
          // Keep a maximum of 2000 lines in UI memory
          if (combined.length > 2000) {
            return combined.slice(combined.length - 2000);
          }
          return combined;
        });
      }
    };

    eventSource.onerror = (err) => {
      console.error("[LogStream] EventSource encountered an error:", err);
      if (eventSource.readyState === EventSource.CLOSED) {
        setIsConnected(false);
        setError(new Error("Connection closed"));
      } else if (eventSource.readyState === EventSource.CONNECTING) {
        setIsConnected(false);
      }
    };

    return () => {
      console.log("[LogStream] Closing EventSource connection");
      eventSource.close();
      setIsConnected(false);
    };
  }, [isEnabled]);

  return {
    logs,
    isConnected,
    error,
    clearLogs,
    reconnect: () => {},
    disconnect: () => {},
  };
};
