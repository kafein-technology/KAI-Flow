import React, { useState, useCallback, useEffect } from "react";
import { config } from "../../lib/config";
import { useReactFlow } from "@xyflow/react";
import { useSnackbar } from "notistack";
import GenericVisual from "./GenericVisual";
import type { GenericData, GenericNodeProps } from "./types";
import GenericNodeForm from "./GenericNodeForm";
import { validate } from "uuid";

interface TimerStatus {
  timer_id: string;
  status: "initialized" | "running" | "stopped" | "error" | "completed";
  next_execution?: string;
  last_execution?: string;
  execution_count: number;
  is_active: boolean;
}

interface WebhookEvent {
  webhook_id: string;
  correlation_id: string;
  event_type: string;
  data: any;
  received_at: string;
  client_ip: string;
}

interface ScrapedDocument {
  url: string;
  title?: string;
  content: string;
  contentLength: number;
  domain: string;
  scrapedAt: string;
  status: "success" | "failed" | "processing";
}

interface ScrapingProgress {
  totalUrls: number;
  completedUrls: number;
  failedUrls: number;
  currentUrl?: string;
  startTime: Date;
  estimatedTimeRemaining: number;
  avgProcessingTime: number;
  totalContentExtracted: number;
}

export default function GenericNode({ data, id }: GenericNodeProps) {
  const { setNodes, getEdges, getNodes } = useReactFlow();
  const [isConfigMode, setIsConfigMode] = useState(false);
  const [configData, setConfigData] = useState<GenericData>(data);
  const { enqueueSnackbar } = useSnackbar();
  const [isHovered, setIsHovered] = useState(false);
  const edges = getEdges?.() ?? [];
  const [isActive, setIsActive] = useState(false);
  const [timerStatus, setTimerStatus] = useState<TimerStatus | null>(null);
  const [countdown, setCountdown] = useState<number>(0);
  const [isListening, setIsListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [events, setEvents] = useState<WebhookEvent[]>([]);
  const [isScraping, setIsScraping] = useState(false);
  const [scrapedDocuments, setScrapedDocuments] = useState<ScrapedDocument[]>(
    []
  );
  const [progress, setProgress] = useState<ScrapingProgress | null>(null);

  // Update configData when data prop changes, but prevent infinite loops
  useEffect(() => {
    setConfigData((prevData) => {
      // Only update if the data actually changed
      if (JSON.stringify(prevData) !== JSON.stringify(data)) {
        return data;
      }
      return prevData;
    });
  }, [data]);

  const handleSaveConfig = (values: Partial<GenericData>) => {
    console.log(values);
    const updatedData = { ...data, ...values };
    // Update node data without affecting local configData to prevent loops
    setNodes((nodes) =>
      nodes.map((node) =>
        node.id === id ? { ...node, data: updatedData } : node
      )
    );
    setIsConfigMode(false);
  };

  const handleDeleteNode = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      setNodes((nodes) => nodes.filter((node) => node.id !== id));
      enqueueSnackbar("Generic node silindi", {
        variant: "info",
        autoHideDuration: 2000,
      });
    },
    [setNodes, id, enqueueSnackbar]
  );

  const isHandleConnected = useCallback(
    (handleId: string, isSource = false) =>
      edges.some((edge) =>
        isSource
          ? edge.source === id && edge.sourceHandle === handleId
          : edge.target === id && edge.targetHandle === handleId
      ),
    [edges, id]
  );

  const generateCurlCommand = useCallback(() => {
    if (!configData.url) return "";

    let curl = `curl -X ${configData.method || "GET"}`;

    // Add headers
    if (configData.content_type) {
      curl += ` -H "Content-Type: ${configData.content_type}"`;
    }

    if (configData.api_key_header && configData.api_key_value) {
      curl += ` -H "${configData.api_key_header}: ${configData.api_key_value}"`;
    }

    // Add custom headers
    if (configData.custom_headers) {
      try {
        const customHeaders = JSON.parse(configData.custom_headers);
        Object.entries(customHeaders).forEach(([key, value]) => {
          curl += ` -H "${key}: ${value}"`;
        });
      } catch (e) {
        console.warn("Failed to parse custom headers for cURL:", e);
      }
    }

    // Add body
    if (
      ["POST", "PUT", "PATCH"].includes(configData.method || "GET") &&
      configData.body
    ) {
      curl += ` -d '${configData.body}'`;
    }

    // Add URL
    curl += ` "${configData.url}"`;

    return curl;
  }, [configData]);

  const copyToClipboard = useCallback(
    async (text: string, type: string) => {
      try {
        await navigator.clipboard.writeText(text);
        enqueueSnackbar(`${type} copied to clipboard`, {
          variant: "success",
          autoHideDuration: 2000,
        });
      } catch (err) {
        console.error("Failed to copy:", err);
        enqueueSnackbar("Failed to copy to clipboard", {
          variant: "error",
          autoHideDuration: 2000,
        });
      }
    },
    [enqueueSnackbar]
  );

  // Real-time countdown to next execution
  useEffect(() => {
    if (!timerStatus?.next_execution || !isActive) return;

    const interval = setInterval(() => {
      const next = new Date(timerStatus.next_execution!);
      const now = new Date();
      const diff = Math.max(
        0,
        Math.floor((next.getTime() - now.getTime()) / 1000)
      );
      setCountdown(diff);
    }, 1000);

    return () => clearInterval(interval);
  }, [timerStatus, isActive]);

  // Timer status güncelleme
  useEffect(() => {
    if (data?.timer_id) {
      fetchTimerStatus();
    }
  }, [data?.timer_id]);

  const fetchTimerStatus = async () => {
    try {
      const response = await fetch(`/${config.API_START}/timers/${data.timer_id}/status`);
      if (response.ok) {
        const status = await response.json();
        setTimerStatus(status);
        setIsActive(status.is_active);
      }
    } catch (err) {
      console.error("Failed to fetch timer status:", err);
    }
  };

  const startTimer = async () => {
    try {
      const response = await fetch(`/${config.API_START}/timers/${data.timer_id}/start`, {
        method: "POST",
      });

      if (response.ok) {
        setIsActive(true);
        fetchTimerStatus();
      }
    } catch (err) {
      console.error("Failed to start timer:", err);
    }
  };

  const stopTimer = async () => {
    try {
      const response = await fetch(`/${config.API_START}/timers/${data.timer_id}/stop`, {
        method: "POST",
      });

      if (response.ok) {
        setIsActive(false);
        fetchTimerStatus();
      }
    } catch (err) {
      console.error("Failed to stop timer:", err);
    }
  };

  const triggerNow = async () => {
    try {
      const response = await fetch(`/${config.API_START}/timers/${data.timer_id}/trigger`, {
        method: "POST",
      });

      if (response.ok) {
        // Refresh status after manual trigger
        fetchTimerStatus();
      }
    } catch (err) {
      console.error("Failed to trigger timer:", err);
    }
  };

  const startListening = async () => {
    const webhookId = data?.webhook_id || id;

    setIsListening(true);
    setError(null);
    setEvents([]);

    try {
      // Backend'e listening başlatma isteği gönder
      const backendUrl =
        process.env.NODE_ENV === "development"
          ? "http://localhost:8000"
          : window.location.origin;
      const response = await fetch(
        `${backendUrl}/${config.API_START}/${config.API_VERSION_ONLY}/webhooks/${webhookId}/start-listening`,
        {
          method: "POST",
        }
      );

      if (!response.ok) {
        throw new Error("Failed to start listening");
      }

      enqueueSnackbar("Started listening for webhook events", {
        variant: "success",
        autoHideDuration: 2000,
      });
    } catch (err) {
      setError("Failed to start listening");
      setIsListening(false);
      enqueueSnackbar("Failed to start listening", { variant: "error" });
    }
  };

  const stopListening = async () => {
    setIsListening(false);

    try {
      const webhookId = data?.webhook_id || id;
      const backendUrl =
        process.env.NODE_ENV === "development"
          ? "http://localhost:8000"
          : window.location.origin;
      // Backend'e listening durdurma isteği gönder
      await fetch(`${backendUrl}/${config.API_START}/${config.API_VERSION_ONLY}/webhooks/${webhookId}/stop-listening`, {
        method: "POST",
      });
    } catch (err) {
      console.error("Failed to stop listening:", err);
    }
  };

  // Input edge'lerinden gelen verileri al
  const getInputData = () => {
    const nodes = getNodes();
    const edges = getEdges();
    const inputEdges = edges.filter((edge) => edge.target === id);
    const inputData: any = {};

    inputEdges.forEach((edge) => {
      const sourceNode = nodes.find((node) => node.id === edge.source);
      if (sourceNode && sourceNode.data) {
        if (edge.targetHandle === "urls") {
          inputData.urls =
            sourceNode.data.output ||
            sourceNode.data.urls ||
            sourceNode.data.content;
        } else if (edge.targetHandle === "config") {
          inputData.config =
            sourceNode.data.output || sourceNode.data.config || sourceNode.data;
        }
      }
    });

    return inputData;
  };

  const scrapeUrls = async () => {
    const inputData = getInputData();
    const urlsToScrape = inputData.urls || data?.urls || data?.input_urls;

    if (!urlsToScrape) {
      console.error("No URLs to scrape");
      return;
    }

    setIsScraping(true);
    setScrapedDocuments([]);
    setProgress(null);

    try {
      const response = await fetch(`/${config.API_START}/web-scraper/${id}/scrape`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          urls:
            typeof urlsToScrape === "string"
              ? urlsToScrape
              : urlsToScrape.join("\n"),
          input_urls: Array.isArray(urlsToScrape) ? urlsToScrape : [],
          user_agent:
            inputData.config?.user_agent ||
            data?.user_agent ||
            "Default KAI-Fusion",
          remove_selectors:
            inputData.config?.remove_selectors || data?.remove_selectors || "",
          min_content_length:
            inputData.config?.min_content_length ||
            data?.min_content_length ||
            100,
          max_concurrent:
            inputData.config?.max_concurrent || data?.max_concurrent || 5,
          timeout_seconds:
            inputData.config?.timeout_seconds || data?.timeout_seconds || 30,
          retry_attempts:
            inputData.config?.retry_attempts || data?.retry_attempts || 3,
        }),
      });

      if (response.ok) {
        const result = await response.json();
        setScrapedDocuments(result.documents || []);
        setProgress(result.progress);
      } else {
        const errorData = await response.json();
        console.error("Scraping failed:", errorData.error);
      }
    } catch (err) {
      console.error("Network error during scraping:", err);
    } finally {
      setIsScraping(false);
    }
  };

  if (isConfigMode) {
    return (
      <GenericNodeForm
        configData={configData}
        initialValues={{
          ...configData,
          text_input: configData.text_input || "",
        }}
        validate={validate}
        onSubmit={handleSaveConfig}
        onCancel={() => setIsConfigMode(false)}
      />
    );
  }

  return (
    <GenericVisual
      data={data}
      isHovered={isHovered}
      onDoubleClick={() => { }} // Disabled: Don't open config modal on double-click
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onDelete={handleDeleteNode}
      isHandleConnected={isHandleConnected}
      generateCurlCommand={generateCurlCommand}
      onCopyToClipboard={copyToClipboard}
      isScraping={isScraping}
      onScrape={scrapeUrls}
      isListening={isListening}
      onStartListening={startListening}
      onStopListening={stopListening}
      isActive={isActive}
      startTimer={startTimer}
      stopTimer={stopTimer}
      triggerNow={triggerNow}
    />
  );
}
