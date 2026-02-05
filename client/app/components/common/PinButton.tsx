import React from "react";
import { Heart, HeartOff } from "~/icons/index";
import { usePinnedItems } from "~/stores/pinnedItems";
import { useSnackbar } from "notistack";

interface PinButtonProps {
  id: string;
  type: "workflow" | "chat";
  title: string;
  description?: string;
  metadata?: {
    status?: string;
    lastActivity?: string;
    messageCount?: number;
  };
  size?: "sm" | "md" | "lg";
  variant?: "default" | "minimal";
  className?: string;
}

export default function PinButton({
  id,
  type,
  title,
  description,
  metadata,
  size = "md",
  variant = "default",
  className = "",
}: PinButtonProps) {
  const { isPinned, addPinnedItem, removePinnedItem } = usePinnedItems();
  const { enqueueSnackbar } = useSnackbar();

  const pinned = isPinned(id, type);

  const handleTogglePin = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (pinned) {
      removePinnedItem(id, type);
      enqueueSnackbar(`${type === "workflow" ? "Workflow" : "Chat"} unpinned`, {
        variant: "info",
      });
    } else {
      addPinnedItem({
        id,
        type,
        title,
        description,
        metadata,
      });
      enqueueSnackbar(
        `${type === "workflow" ? "Workflow" : "Chat"} pinned to top`,
        {
          variant: "success",
        }
      );
    }
  };

  const getSizeClasses = () => {
    switch (size) {
      case "sm":
        return "w-4 h-4";
      case "lg":
        return "w-6 h-6";
      default:
        return "w-5 h-5";
    }
  };

  const getVariantClasses = () => {
    if (variant === "minimal") {
      return pinned
        ? "text-red-500 hover:text-red-600"
        : "text-gray-400 hover:text-red-500";
    }

    return pinned
      ? "text-red-500 hover:text-red-600 bg-red-50 hover:bg-red-100"
      : "text-gray-400 hover:text-red-500 bg-gray-50 hover:bg-red-50";
  };

  return (
    <button
      onClick={handleTogglePin}
      className={`
        flex items-center justify-center rounded-full transition-all duration-200
        ${getVariantClasses()}
        ${getSizeClasses()}
        ${className}
      `}
      title={pinned ? `Unpin ${type}` : `Pin ${type} to top`}
    >
      {pinned ? (
        <Heart className={`${getSizeClasses()} fill-current`} />
      ) : (
        <Heart className={getSizeClasses()} />
      )}
    </button>
  );
}
