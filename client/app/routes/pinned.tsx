import React from "react";
import { Heart, Play, MessageSquare, Clock, ChevronRight } from "~/components/common/Icon";
import { Link } from "react-router";
import DashboardSidebar from "~/components/dashboard/DashboardSidebar";
import { usePinnedItems } from "~/stores/pinnedItems";
import { timeAgo } from "~/lib/dateFormatter";
import AuthGuard from "~/components/AuthGuard";
import PinButton from "~/components/common/PinButton";

function PinnedItemsLayout() {
  const { getPinnedItems } = usePinnedItems();

  const pinnedItems = getPinnedItems();
  const pinnedWorkflows = getPinnedItems("workflow");
  const pinnedChats = getPinnedItems("chat");

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

  if (pinnedItems.length === 0) {
    return (
      <div className="flex h-screen bg-gray-50">
        <DashboardSidebar />
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <Heart className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <h2 className="text-2xl font-semibold text-gray-900 mb-2">
              No Pinned Items
            </h2>
            <p className="text-gray-600 mb-6">
              Pin workflows and chats to see them here for quick access.
            </p>
            <div className="space-x-4">
              <Link
                to="/workflows"
                className="inline-flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
              >
                <Play className="w-4 h-4" />
                Browse Workflows
              </Link>
              <Link
                to="/canvas"
                className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                <MessageSquare className="w-4 h-4" />
                Start Chat
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-gray-50">
      <DashboardSidebar />
      <div className="flex-1 overflow-auto">
        <div className="p-8">
          {/* Header */}
          <div className="mb-8">
            <div className="flex items-center gap-3 mb-2">
              <Heart className="w-8 h-8 text-red-500 fill-current" />
              <h1 className="text-3xl font-bold text-gray-900">Pinned Items</h1>
              <span className="px-3 py-1 text-sm font-medium bg-red-100 text-red-700 rounded-full">
                {pinnedItems.length} items
              </span>
            </div>
            <p className="text-gray-600">
              Your favorite workflows and chats for quick access
            </p>
          </div>

          {/* Pinned Workflows Section */}
          {pinnedWorkflows.length > 0 && (
            <div className="mb-8">
              <div className="flex items-center gap-2 mb-4">
                <Play className="w-5 h-5 text-purple-600" />
                <h2 className="text-xl font-semibold text-gray-900">
                  Pinned Workflows
                </h2>
                <span className="px-2 py-1 text-xs font-medium bg-purple-100 text-purple-700 rounded-full">
                  {pinnedWorkflows.length}
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {pinnedWorkflows.map((item) => (
                  <div
                    key={`${item.type}-${item.id}`}
                    className="bg-white border border-gray-200 rounded-xl p-4 hover:shadow-lg transition-all duration-300 group"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className="flex items-center justify-center w-8 h-8 bg-purple-100 rounded-lg group-hover:bg-purple-200 transition-colors">
                          {getItemIcon(item.type)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <h3 className="font-semibold text-gray-900 truncate group-hover:text-purple-600 transition-colors">
                            {item.title}
                          </h3>
                          {item.description && (
                            <p className="text-sm text-gray-600 mt-1 line-clamp-2">
                              {item.description}
                            </p>
                          )}
                        </div>
                      </div>
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
                      <div className="flex items-center text-xs text-gray-500">
                        <Clock className="w-3 h-3 mr-1" />
                        <span>Pinned {timeAgo(item.pinnedAt)}</span>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center justify-between pt-3 border-t border-gray-100">
                      <Link
                        to={getItemPath(item)}
                        className="flex items-center gap-2 text-sm text-purple-600 hover:text-purple-700 font-medium"
                      >
                        Open Workflow
                        <ChevronRight className="w-4 h-4" />
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Pinned Chats Section */}
          {pinnedChats.length > 0 && (
            <div className="mb-8">
              <div className="flex items-center gap-2 mb-4">
                <MessageSquare className="w-5 h-5 text-blue-600" />
                <h2 className="text-xl font-semibold text-gray-900">
                  Pinned Chats
                </h2>
                <span className="px-2 py-1 text-xs font-medium bg-blue-100 text-blue-700 rounded-full">
                  {pinnedChats.length}
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {pinnedChats.map((item) => (
                  <div
                    key={`${item.type}-${item.id}`}
                    className="bg-white border border-gray-200 rounded-xl p-4 hover:shadow-lg transition-all duration-300 group"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className="flex items-center justify-center w-8 h-8 bg-blue-100 rounded-lg group-hover:bg-blue-200 transition-colors">
                          {getItemIcon(item.type)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <h3 className="font-semibold text-gray-900 truncate group-hover:text-blue-600 transition-colors">
                            {item.title}
                          </h3>
                          {item.description && (
                            <p className="text-sm text-gray-600 mt-1 line-clamp-2">
                              {item.description}
                            </p>
                          )}
                        </div>
                      </div>
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

                    {/* Metadata */}
                    <div className="space-y-2 mb-3">
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
                    <div className="flex items-center justify-between pt-3 border-t border-gray-100">
                      <Link
                        to={getItemPath(item)}
                        className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-700 font-medium"
                      >
                        Open Chat
                        <ChevronRight className="w-4 h-4" />
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ProtectedPinnedItemsLayout() {
  return (
    <AuthGuard>
      <PinnedItemsLayout />
    </AuthGuard>
  );
}
