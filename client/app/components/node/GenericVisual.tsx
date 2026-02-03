import React, { useMemo } from "react";
import { Position } from "@xyflow/react";
import { NeonHandle } from "~/components/common/NeonHandle";
import { BoxIcon as Box, DownloadIcon as Download, SquareIcon as Square, TrashIcon as Trash, CopyIcon as Copy, PlayIcon as Play, ZapIcon as Zap } from "../../icons/index";
import type { GenericData } from "./types";
import type { NodeMetadata } from "../../types/api";
import { resolveIconPath } from "~/lib/iconUtils";


type IconComponent = React.ComponentType<{ className?: string; size?: number }>;

interface GenericVisualProps {
  data: GenericData;
  isHovered: boolean;
  onDoubleClick: () => void;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
  onDelete: (e: React.MouseEvent<HTMLButtonElement>) => void;
  isHandleConnected: (handleId: string, isSource?: boolean) => boolean;
  onScrape?: () => void;
  isScraping?: boolean;
  generateCurlCommand?: () => string;
  onCopyToClipboard?: (text: string, label: string) => void;
  isListening?: boolean;
  onStartListening?: () => void;
  onStopListening?: () => void;
  isActive?: boolean;
  startTimer?: () => void;
  stopTimer?: () => void;
  triggerNow?: () => void;
}

function GenericVisual({
  data,
  isHovered,
  onDoubleClick,
  onMouseEnter,
  onMouseLeave,
  onDelete,
  isHandleConnected,
  onScrape,
  isScraping,
  generateCurlCommand,
  onCopyToClipboard,
  isListening,
  onStartListening,
  onStopListening,
  isActive,
  startTimer,
  stopTimer,
  triggerNow,
}: GenericVisualProps) {
  const getNodeColor = () => {
    const colors = data.metadata?.colors;
    if (colors && colors[0] && colors[1]) {
      return `from-${colors[0]} to-${colors[1]}`;
    }
    return "";
    // return "from-blue-500 to-indigo-600";
  };

  const getGlowColor = () => {
    switch (data.validationStatus) {
      case "success":
        return "shadow-emerald-500/30";
      case "error":
        return "shadow-red-500/30";
      default:
        return "shadow-blue-500/30";
    }
  };

  const getIconComponent = (icon: NodeMetadata["icon"]): IconComponent => {
    // Prioritize Icon component if name is available, as it renders inline SVG
    // and supports CSS color classes (text-white, etc.) via currentColor
    if (icon?.name) {
      return (props: any) => <IconComponent name={icon.name} {...props} />;
    }
    if (icon?.path) {
      const iconPath = resolveIconPath(icon.path);
      return (props: any) => (
        <img
          src={iconPath}
          alt={icon.alt}
          {...props}
          className={`${props.className || ""} object-contain`}
        />
      );
    }
    return Box;
  };

  const Icon = useMemo(
    () => getIconComponent(data.metadata?.icon),
    [data.metadata?.icon]
  );

  // Handle configuration for positioning and styling
  const handleConfig = {
    [Position.Left]: {
      vertical: true,
      labelClass: "right-full mr-3",
      transform: "translateY(-50%)",
    },
    [Position.Right]: {
      vertical: true,
      labelClass: "left-full ml-3",
      transform: "translateY(-50%)",
    },
    [Position.Top]: {
      vertical: false,
      labelClass: "bottom-full mb-5",
      transform: "translateX(-30%) rotate(-40deg)",
    },
    [Position.Bottom]: {
      vertical: false,
      labelClass: "top-full mt-5",
      transform: "translateX(-20%) rotate(40deg)",
    },
  };

  const renderHandles = (
    items: any[] = [],
    type: "target" | "source",
    defaultPos: Position
  ) => {
    // Group handles by position
    const groups = items.reduce((acc: Record<string, any[]>, item: any) => {
      if (!item.is_connection) return acc;
      const pos = item.direction || defaultPos;
      if (!acc[pos]) acc[pos] = [];
      acc[pos].push(item);
      return acc;
    }, {});

    return Object.entries(groups).map(([pos, handles]) => {
      const config = handleConfig[pos as Position];
      return handles.map((handle, index) => {
        const percent = `${((index + 1) * 100) / (handles.length + 1)}%`;
        const style = config.vertical ? { top: percent } : { left: percent };

        return (
          <React.Fragment key={`${type}-${handle.name}-${index}`}>
            <NeonHandle
              type={type}
              position={pos as Position}
              id={handle.name}
              isConnectable={true}
              size={16}
              color1="#00FFFF"
              style={style}
              title={handle.name}
            />
            <span
              className={`absolute text-[9px] font-medium text-cyan-100 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap bg-black/60 px-1 rounded backdrop-blur-[1px] z-100 ${config.labelClass}`}
              style={{ ...style, transform: config.transform }}
            >
              {handle.displayName || handle.name}
            </span>
          </React.Fragment>
        );
      });
    });
  };

  return (
    <div
      className={`relative group w-24 h-24 rounded-2xl flex flex-col items-center justify-center 
          cursor-pointer transition-all duration-300 transform
        ${isHovered ? "scale-105" : "scale-100"}
        ${isHovered
          ? `shadow-2xl ${getGlowColor()}`
          : "shadow-lg shadow-black/50"
        }
        bg-gradient-to-br ${getNodeColor()}

        border border-white/20 backdrop-blur-sm
        hover:border-white/40`}
      onDoubleClick={onDoubleClick}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      title="Yapılandırmak için çift tıklayın"
    >
      {/* Arka plan deseni */}
      <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-white/10 to-transparent opacity-50"></div>

      {/* Ana ikon */}
      <div className="relative z-10 mb-2">
        <div className="relative">
          <Icon className="w-8 h-8 text-white drop-shadow-lg" />
        </div>
      </div>

      {/* Node başlığı */}
      <div className="text-white text-xs font-semibold text-center drop-shadow-lg z-10 px-2">
        {data?.display_name ||
          data?.displayName ||
          data?.name ||
          "Generic Node"}
      </div>

      {/* Hover efektleri */}
      {isHovered && (
        <>
          {/* Silme butonu */}
          <button
            className="absolute -top-3 -right-3 w-8 h-8 
              bg-gradient-to-r from-red-500 to-red-600 hover:from-red-400 hover:to-red-500
              text-white rounded-full border border-white/30 shadow-xl 
              transition-all duration-200 hover:scale-110 flex items-center justify-center z-20
              backdrop-blur-sm"
            onClick={onDelete}
            title="Node'u Sil"
          >
            <Trash size={14} />
          </button>
        </>
      )}

      {/* WebScraper Node's Scrape button */}
      {data.name === "WebScraper" && (isHovered || isScraping) && (
        <button
          className={`absolute -bottom-3 -right-3 w-8 h-8 
                ${isScraping
              ? "bg-gradient-to-r from-red-500 to-red-600 hover:from-red-400 hover:to-red-500"
              : "bg-gradient-to-r from-green-500 to-green-600 hover:from-green-400 hover:to-green-500"
            }
                text-white rounded-full border border-white/30 shadow-xl 
                transition-all duration-200 hover:scale-110 flex items-center justify-center z-20
                backdrop-blur-sm`}
          onClick={(e) => {
            e.stopPropagation();
            if (isScraping) {
              // Optional: Add cancel logic here if supported
            } else if (onScrape) {
              onScrape();
            }
          }}
          title={isScraping ? "Scraping..." : "Start Scraping"}
        >
          {isScraping ? <Square size={14} /> : <Download size={14} />}
        </button>
      )}

      {/* HTTPRequest Node's Copy cURL button */}
      {data.name === "HttpRequest" &&
        isHovered &&
        generateCurlCommand &&
        onCopyToClipboard && (
          <button
            className="absolute -bottom-3 -left-3 w-8 h-8 
                bg-gradient-to-r from-purple-500 to-purple-600 hover:from-purple-400 hover:to-purple-500
                text-white rounded-full border border-white/30 shadow-xl 
                transition-all duration-200 hover:scale-110 flex items-center justify-center z-20
                backdrop-blur-sm"
            onClick={(e) => {
              e.stopPropagation();
              onCopyToClipboard(generateCurlCommand(), "cURL");
            }}
            title="Copy cURL"
          >
            <Copy size={14} />
          </button>
        )}

      {/* WebhookTrigger Node's Start Listening button */}
      {data.name === "WebhookTrigger" && isHovered && (
        <button
          className={`absolute -bottom-3 -right-3 w-8 h-8 
                ${isListening
              ? "bg-gradient-to-r from-red-500 to-red-600 hover:from-red-400 hover:to-red-500"
              : "bg-gradient-to-r from-green-500 to-green-600 hover:from-green-400 hover:to-green-500"
            }
                text-white rounded-full border border-white/30 shadow-xl 
                transition-all duration-200 hover:scale-110 flex items-center justify-center z-20
                backdrop-blur-sm`}
          onClick={(e) => {
            e.stopPropagation();
            if (isListening) {
              onStopListening?.();
            } else {
              onStartListening?.();
            }
          }}
          title={isListening ? "Stop Listening" : "Start Listening"}
        >
          {isListening ? <Square size={14} /> : <Play size={14} />}
        </button>
      )}

      {/* TimerStartNode Node's Start Timer button */}
      {data.name === "TimerStart" &&
        isHovered &&
        startTimer &&
        stopTimer &&
        triggerNow && (
          <div className="absolute -bottom-3 -right-3 flex space-x-1">
            {!isActive ? (
              <button
                className="w-8 h-8 bg-gradient-to-r from-green-500 to-green-600 
                    hover:from-green-400 hover:to-green-500 text-white rounded-full 
                    border border-white/30 shadow-xl transition-all duration-200 
                    hover:scale-110 flex items-center justify-center z-20 backdrop-blur-sm"
                onClick={(e) => {
                  e.stopPropagation();
                  startTimer();
                }}
                title="Start Timer"
              >
                <Play size={14} />
              </button>
            ) : (
              <button
                className="w-8 h-8 bg-gradient-to-r from-red-500 to-red-600 
                    hover:from-red-400 hover:to-red-500 text-white rounded-full 
                    border border-white/30 shadow-xl transition-all duration-200 
                    hover:scale-110 flex items-center justify-center z-20 backdrop-blur-sm"
                onClick={(e) => {
                  e.stopPropagation();
                  stopTimer();
                }}
                title="Stop Timer"
              >
                <Square size={14} />
              </button>
            )}

            <button
              className="w-8 h-8 bg-gradient-to-r from-blue-500 to-blue-600 
                  hover:from-blue-400 hover:to-blue-500 text-white rounded-full 
                  border border-white/30 shadow-xl transition-all duration-200 
                  hover:scale-110 flex items-center justify-center z-20 backdrop-blur-sm"
              onClick={(e) => {
                e.stopPropagation();
                triggerNow();
              }}
              title="Trigger Now"
            >
              <Zap size={14} />
            </button>
          </div>
        )}

      {/* Render Handles */}
      {renderHandles(
        data.inputs || data.metadata?.inputs,
        "target",
        Position.Left
      )}
      {renderHandles(
        data.outputs || data.metadata?.outputs,
        "source",
        Position.Right
      )}
    </div>
  );
}

export default GenericVisual;
