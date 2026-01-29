import React, { useEffect } from "react";
import { Calendar, TrendingUp, Activity, Zap } from "lucide-react";
import AuthGuard from "~/components/AuthGuard";
import DashboardSidebar from "~/components/dashboard/DashboardSidebar";
import DashboardChart from "../components/DashboardChart";
import Loading from "../components/Loading";
import { useWorkflows } from "~/stores/workflows";

function DashboardLayout() {
  const [selectedPeriod, setSelectedPeriod] = React.useState("7days");
  const { dashboardStats, fetchDashboardStats, isLoading, error } =
    useWorkflows();

  useEffect(() => {
    fetchDashboardStats();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Helper function to format runtime with ms precision
  const formatRuntime = (ms: number): string => {
    if (ms === 0) return "0s";

    if (ms < 60000) {
      return `${(ms / 1000).toFixed(2)} s`;
    }

    const minutes = Math.floor(ms / 60000);
    const remainingMs = ms % 60000;
    const seconds = (remainingMs / 1000).toFixed(2);
    return `${minutes}m ${seconds} s`;
  };

  // Prepare chart data for DashboardChart
  const periodData =
    dashboardStats?.[selectedPeriod as keyof typeof dashboardStats];
  const chartData = Array.isArray(periodData)
    ? periodData.map((d: any) => ({
      name: d.date,
      prodexec: d.prodexec,
      failedprod: d.failedprod,
      avg_runtime_ms: d.avg_runtime_ms,
    }))
    : [];

  const chartConfig = {
    prodexec: {
      label: "Prod. executions",
      color: "#2563eb",
    },
    failedprod: {
      label: "Failed Prod. executions",
      color: "#ef4444",
    },
    avg_runtime_ms: {
      label: "Avg runtime (ms)",
      color: "#10b981",
    },
  };

  return (
    <div className="flex h-screen bg-background text-foreground">
      <DashboardSidebar />

      <main className="flex-1 overflow-hidden">
        <div className="h-full overflow-y-auto p-6">
          <div className="max-w-7xl mx-auto">
            {/* Header */}
            <div className="mb-8">
              <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
                <div>
                  <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-600 to-blue-600 bg-clip-text text-transparent">
                    Dashboard
                  </h1>
                  <p className="text-gray-600 text-lg">
                    Get an overview of your activity, recent executions, and
                    system health at a glance.
                  </p>
                </div>
                <div className="flex items-center gap-4">
                  <div className="relative">
                    <Calendar className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                    <select
                      className="pl-10 pr-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all duration-200 bg-white text-gray-900"
                      value={selectedPeriod}
                      onChange={(e) => setSelectedPeriod(e.target.value)}
                    >
                      <option value="7days">Last 7 days</option>
                      <option value="30days">Last 30 days</option>
                      <option value="90days">Last 90 days</option>
                    </select>
                  </div>
                </div>
              </div>
            </div>
            {/* Content */}
            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loading size="sm" />
              </div>
            ) : error ? (
              <div className="p-6 bg-red-50 border border-red-200 rounded-xl text-red-600">
                {error}
              </div>
            ) : (
              <div className="space-y-8">
                {/* Stats Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                  <div className="bg-white border border-gray-200 rounded-2xl p-6 hover:shadow-lg transition-all duration-300">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-gray-600">
                          Total Executions
                        </p>
                        <p className="text-2xl font-bold text-gray-900">
                          {chartData.reduce(
                            (sum, item) => sum + (item.prodexec || 0),
                            0
                          )}
                        </p>
                      </div>
                      <div className="p-3 bg-blue-100 rounded-xl">
                        <Activity className="w-6 h-6 text-blue-600" />
                      </div>
                    </div>
                  </div>

                  <div className="bg-white border border-gray-200 rounded-2xl p-6 hover:shadow-lg transition-all duration-300">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-gray-600">
                          Failed Executions
                        </p>
                        <p className="text-2xl font-bold text-gray-900">
                          {chartData.reduce(
                            (sum, item) => sum + (item.failedprod || 0),
                            0
                          )}
                        </p>
                      </div>
                      <div className="p-3 bg-red-100 rounded-xl">
                        <Zap className="w-6 h-6 text-red-600" />
                      </div>
                    </div>
                  </div>

                  <div className="bg-white border border-gray-200 rounded-2xl p-6 hover:shadow-lg transition-all duration-300">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-gray-600">
                          Success Rate
                        </p>
                        <p className="text-2xl font-bold text-gray-900">
                          {(() => {
                            const total = chartData.reduce(
                              (sum, item) => sum + (item.prodexec || 0),
                              0
                            );
                            const failed = chartData.reduce(
                              (sum, item) => sum + (item.failedprod || 0),
                              0
                            );
                            return total > 0
                              ? Math.round(((total - failed) / total) * 100)
                              : 0;
                          })()}
                          %
                        </p>
                      </div>
                      <div className="p-3 bg-green-100 rounded-xl">
                        <TrendingUp className="w-6 h-6 text-green-600" />
                      </div>
                    </div>
                  </div>

                  <div className="bg-white border border-gray-200 rounded-2xl p-6 hover:shadow-lg transition-all duration-300">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-gray-600">
                          Avg Runtime
                        </p>
                        <p className="text-2xl font-bold text-gray-900">
                          {(() => {
                            const completedDays = chartData.filter(
                              (d) => (d as any).avg_runtime_ms > 0
                            );
                            if (completedDays.length === 0) return "0ms";
                            const avg =
                              completedDays.reduce(
                                (sum, d: any) => sum + (d.avg_runtime_ms || 0),
                                0
                              ) / completedDays.length;
                            return formatRuntime(avg);
                          })()}
                        </p>
                      </div>
                      <div className="p-3 bg-purple-100 rounded-xl">
                        <Calendar className="w-6 h-6 text-purple-600" />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Chart */}
                <div className="bg-white border border-gray-200 rounded-2xl ">
                  <DashboardChart
                    title="Production Executions & Avg Runtime"
                    description={
                      selectedPeriod === "7days"
                        ? "Last 7 days"
                        : selectedPeriod === "30days"
                          ? "Last 30 days"
                          : "Last 90 days"
                    }
                    data={chartData}
                    dataKeys={["prodexec", "failedprod", "avg_runtime_ms"]}
                    config={chartConfig}
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

export default function ProtectedDashboardLayout() {
  return (
    <AuthGuard>
      <DashboardLayout />
    </AuthGuard>
  );
}
