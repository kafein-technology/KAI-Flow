import React, { useState } from "react";
import { SearchIcon as Search, PlusIcon as Plus, ArrowRightIcon as ArrowRight } from "../../icons/index";
import {
  SERVICE_DEFINITIONS,
  getServicesByCategory,
  getCategoryLabel,
} from "~/types/credentials";
import { resolveIconPath } from "~/lib/iconUtils";
import type { ServiceDefinition } from "~/types/credentials";

interface ServiceSelectionModalProps {
  onSelectService: (service: ServiceDefinition) => void;
  onClose: () => void;
}

const ServiceSelectionModal: React.FC<ServiceSelectionModalProps> = ({
  onSelectService,
  onClose,
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("all");

  const servicesByCategory = getServicesByCategory();
  const categories = Object.keys(servicesByCategory);

  const filteredServices = SERVICE_DEFINITIONS.filter((service) => {
    const matchesSearch =
      service.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      service.description.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory =
      selectedCategory === "all" || service.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  const handleServiceSelect = (service: ServiceDefinition) => {
    onSelectService(service);
  };

  // Track which icons failed to load so we can fallback to emoji
  const [iconErrorMap, setIconErrorMap] = useState<Record<string, boolean>>({});

  const renderServiceIcon = (service: ServiceDefinition) => {
    return (
      <div className="w-10 h-10 flex items-center justify-center">
        <Icon name={service.id} className="w-10 h-10 object-contain" />
      </div>
    );
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold text-gray-900">
                Connect to a Service
              </h2>
              <p className="text-gray-600 mt-1">
                Choose a service to connect and configure your credentials
              </p>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg
                className="w-6 h-6"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>

          {/* Search and Filter */}
          <div className="mt-6 flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                type="search"
                placeholder="Search services..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="all">All Categories</option>
              {categories.map((category) => (
                <option key={category} value={category}>
                  {getCategoryLabel(category)}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Services Grid */}
        <div className="p-6 overflow-y-auto max-h-[60vh]">
          {filteredServices.length === 0 ? (
            <div className="text-center py-12">
              <div className="text-6xl mb-4">🔍</div>
              <h3 className="text-xl font-semibold text-gray-900 mb-2">
                No services found
              </h3>
              <p className="text-gray-600">
                Try adjusting your search or category filter
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredServices.map((service) => (
                <div
                  key={service.id}
                  onClick={() => handleServiceSelect(service)}
                  className="group cursor-pointer bg-white border border-gray-200 rounded-xl p-6 hover:border-blue-300 hover:shadow-lg transition-all duration-200 hover:scale-105"
                >
                  <div className="flex items-start justify-between mb-4">
                    {renderServiceIcon(service)}
                    <ArrowRight className="w-5 h-5 text-gray-400 group-hover:text-blue-500 group-hover:translate-x-1 transition-all duration-200" />
                  </div>

                  <h3 className="text-lg font-semibold text-gray-900 mb-2 group-hover:text-blue-600 transition-colors">
                    {service.name}
                  </h3>

                  <p className="text-sm text-gray-600 mb-4 line-clamp-2">
                    {service.description}
                  </p>

                  <div className="flex items-center justify-between">
                    <span className="inline-flex px-2 py-1 text-xs font-medium rounded-full bg-gray-100 text-gray-800">
                      {getCategoryLabel(service.category)}
                    </span>

                    <div className="flex items-center gap-1 text-xs text-gray-500">
                      <Plus className="w-3 h-3" />
                      Connect
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-200 bg-gray-50">
          <div className="text-center">
            <p className="text-sm text-gray-600">
              Can't find the service you're looking for?{" "}
              <button className="text-blue-600 hover:text-blue-700 font-medium">
                Request a new integration
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ServiceSelectionModal;
