import React from "react";
import { Heart, Play, MessageSquare, Clock, ChevronRight } from "~/icons/index";
import { Link } from "react-router";
import { usePinnedItems } from "~/stores/pinnedItems";
import { timeAgo } from "~/lib/dateFormatter";
import PinButton from "./PinButton";

interface PinnedItemsSectionProps {
  type?: "workflow" | "chat";
  onItemClick?: (item: any) => void;
  className?: string;
}

export default function PinnedItemsSection({
  type,
  onItemClick,
  className = "",
}: PinnedItemsSectionProps) {
  const { getPinnedItems } = usePinnedItems();

  const pinnedItems = getPinnedItems(type);

  if (pinnedItems.length === 0) {
    return null;
  }

  const getItemIcon = (itemType: "workflow" | "chat") => {
    switch (itemType) {
      case "workflow":
        return <Play className="w-4 h-4" />;
      case "chat":
        return <MessageSquare className="w-4 h-4" />;
      default:
        return null;
    }
  };

  const getItemPath = (item: any) => {
    switch (item.type) {
      case "workflow":
        return `/canvas?workflow=${item.id}`;
      case "chat":
        return `/canvas?chat=${item.id}`;
      default:
        return "#";
    }
  };

  const handleItemClick = (item: any) => {
    if (onItemClick) {
      onItemClick(item);
    }
  };

  return (
    <div className={`mb-6 ${className}`}>
      {/* Pinned Section Header */}
      <div className="flex items-center gap-2 mb-4">
        <Heart className="w-5 h-5 text-red-500 fill-current" />
        <h3 className="text-lg font-semibold text-gray-900">
          Pinned{" "}
          {type ? (type === "workflow" ? "Workflows" : "Chats") : "Items"}
        </h3>
        <span className="px-2 py-1 text-xs font-medium bg-red-100 text-red-700 rounded-full">
          {pinnedItems.length}
        </span>
      </div>

      {/* Pinned Items Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {pinnedItems.map((item) => (
          <div
            key={`${item.type}-${item.id}`}
            className="relative bg-gradient-to-br from-red-50 to-pink-50 border-2 border-red-200 rounded-xl p-4 hover:shadow-lg transition-all duration-300 group"
          >
            {/* Pin Indicator */}
            <div className="absolute top-3 right-3">
              <Heart className="w-4 h-4 text-red-500 fill-current" />
            </div>

            {/* Item Content */}
            <div className="pr-8">
              <div className="flex items-start gap-3 mb-3">
                <div className="flex items-center justify-center w-8 h-8 bg-red-100 rounded-lg group-hover:bg-red-200 transition-colors">
                  {getItemIcon(item.type)}
                </div>
                <div className="flex-1 min-w-0">
                  <h4 className="font-semibold text-gray-900 truncate group-hover:text-red-600 transition-colors">
                    {item.title}
                  </h4>
                  {item.description && (
                    <p className="text-sm text-gray-600 mt-1 line-clamp-2">
                      {item.description}
                    </p>
                  )}
                </div>
              </div>

              {/* Metadata */}
              <div className="space-y-2 mb-3">
                {item.metadata?.status && (
                  <div className="flex items-center text-xs text-gray-500">
                    <span className="font-medium">Status:</span>
                    <span className="ml-2 px-2 py-0.5 bg-gray-100 rounded-full">
                      {item.metadata.status}
                    </span>
                  </div>
                )}
                {item.metadata?.messageCount && (
                  <div className="flex items-center text-xs text-gray-500">
                    <MessageSquare className="w-3 h-3 mr-1" />
                    <span>{item.metadata.messageCount} messages</span>
                  </div>
                )}
                <div className="flex items-center text-xs text-gray-500">
                  <Clock className="w-3 h-3 mr-1" />
                  <span>Pinned {timeAgo(item.pinnedAt)}</span>
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center justify-between pt-3 border-t border-red-100">
                <Link
                  to={getItemPath(item)}
                  onClick={() => handleItemClick(item)}
                  className="flex items-center gap-2 text-sm text-red-600 hover:text-red-700 font-medium"
                >
                  Open {item.type === "workflow" ? "Workflow" : "Chat"}
                  <ChevronRight className="w-4 h-4" />
                </Link>

                <PinButton
                  id={item.id}
                  type={item.type}
                  title={item.title}
                  description={item.description}
                  metadata={item.metadata}
                  size="sm"
                  variant="minimal"
                />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
