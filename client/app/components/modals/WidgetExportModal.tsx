import { forwardRef, useImperativeHandle, useRef, useState, useEffect } from "react";
import { MessageSquare, Copy, Check, Code, Globe, Type, Key, Eye, Bot } from "lucide-react";
import { config as appConfig } from "../../lib/config";
import { KaiChatWidget } from "@kaifusion/widget";
import "@kaifusion/widget/dist/index.css";

interface WidgetExportModalProps {
  workflowId: string;
}

interface WidgetConfig {
  title: string;
  position: "left" | "right";
  color: string;
  baseUrl: string;
  workflowId: string;
  apiKey: string;
  showCustomIcon: boolean;
}

const WidgetExportModal = forwardRef<HTMLDialogElement, WidgetExportModalProps>(
  ({ workflowId }, ref) => {
    const dialogRef = useRef<HTMLDialogElement>(null);
    useImperativeHandle(ref, () => dialogRef.current!);

    const [copied, setCopied] = useState(false);
    const [integrationType, setIntegrationType] = useState<"html" | "react">("html");
    const [latestVersion, setLatestVersion] = useState("latest");
    const [showPreview, setShowPreview] = useState(false);

    useEffect(() => {
      const fetchLatestVersion = async () => {
        try {
          const response = await fetch("https://registry.npmjs.org/@kaifusion/widget/latest");
          if (response.ok) {
            const data = await response.json();
            setLatestVersion(data.version);
          }
        } catch (error) {
          console.warn("Failed to fetch latest widget version:", error);
        }
      };

      fetchLatestVersion();
    }, []);

    const [config, setConfig] = useState<WidgetConfig>({
      title: "KAI Assistant",
      position: "right",
      color: "#526cfe",
      baseUrl: appConfig.API_BASE_URL || "",
      workflowId: workflowId,
      apiKey: "",
      showCustomIcon: false
    });

    useEffect(() => {
      if (workflowId) {
        setConfig(prev => ({ ...prev, workflowId }));
      }
    }, [workflowId]);

    const getReactCode = () => {
      const authLine = config.apiKey ? `\n      authToken="${config.apiKey}"` : "";
      const iconLine = config.showCustomIcon ? `\n      icon={<Bot className="w-7 h-7" />}` : "";
      const iconImport = config.showCustomIcon ? `\nimport { Bot } from "lucide-react";` : "";

      return `import { KaiChatWidget } from "@kaifusion/widget";
import "@kaifusion/widget/dist/index.css";${iconImport}

function App() {
  return (
    <KaiChatWidget
      targetUrl="${config.baseUrl}"
      workflowId="${config.workflowId}"${authLine}
      title="${config.title}"
      position="${config.position}"
      color="${config.color}"${iconLine}
    />
  );
}`;
    };

    const getHtmlCode = () => {
      const authLine = config.apiKey ? `\n  data-auth-token="${config.apiKey}"` : "";
      return `<script
  src="https://cdn.jsdelivr.net/npm/@kaifusion/widget@${latestVersion}/dist/widget.iife.js"
  data-title="${config.title}"${authLine}
  data-workflow-id="${config.workflowId}"
  data-target-url="${config.baseUrl}"
  data-position="${config.position}"
  data-color="${config.color}"
  defer
></script>`;
    };

    const currentCode = integrationType === "react" ? getReactCode() : getHtmlCode();

    const copyToClipboard = () => {
      navigator.clipboard.writeText(currentCode);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    };

    return (
      <dialog
        ref={dialogRef}
        className="modal modal-bottom sm:modal-middle backdrop-blur-sm"
      >
        <div className="modal-box bg-gray-900 border border-gray-700 max-w-[80rem]! h-[80vh] flex flex-col">
          <div className="flex items-center gap-3 mb-6 flex-shrink-0">
            <div className="w-10 h-10 bg-blue-500/20 rounded-full flex items-center justify-center">
              <MessageSquare className="w-5 h-5 text-blue-500" />
            </div>
            <div>
              <h3 className="font-bold text-lg text-white">Export Widget</h3>
              <p className="text-sm text-gray-400">
                Integrate KAI Fusion widget into your application
              </p>
            </div>
          </div>

          <div className="flex-1 overflow-hidden grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left Column - Configuration */}
            <div className="lg:col-span-4 space-y-6 overflow-y-auto pr-2">
              {/* Integration Type */}
              <div className="bg-gray-800/50 p-4 rounded-lg space-y-3">
                <h4 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
                  <Code className="w-4 h-4" /> Integration Type
                </h4>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => setIntegrationType("html")}
                    className={`flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${integrationType === "html"
                      ? "bg-blue-600 text-white"
                      : "bg-gray-700 text-gray-400 hover:bg-gray-600"
                      }`}
                  >
                    <Globe className="w-4 h-4" /> HTML
                  </button>
                  <button
                    onClick={() => setIntegrationType("react")}
                    className={`flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${integrationType === "react"
                      ? "bg-blue-600 text-white"
                      : "bg-gray-700 text-gray-400 hover:bg-gray-600"
                      }`}
                  >
                    <Code className="w-4 h-4" /> React
                  </button>
                </div>
              </div>

              {/* Widget Configuration */}
              <div className="bg-gray-800/50 p-4 rounded-lg space-y-4">
                <h4 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
                  <Type className="w-4 h-4" /> Appearance
                </h4>

                {/* Title */}
                <div className="space-y-1">
                  <label className="text-xs text-gray-400">Widget Title</label>
                  <input
                    type="text"
                    value={config.title}
                    onChange={(e) => setConfig({ ...config, title: e.target.value })}
                    className="w-full bg-gray-700 text-white border border-gray-600 rounded-md px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
                  />
                </div>

                {/* API Key */}
                <div className="space-y-1">
                  <label className="text-xs text-gray-400 flex items-center gap-1">
                    API Key <span className="text-gray-500">(Optional)</span>
                  </label>
                  <div className="relative">
                    <Key className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
                    <input
                      type="text"
                      value={config.apiKey}
                      onChange={(e) => setConfig({ ...config, apiKey: e.target.value })}
                      placeholder="Paste your API Key here"
                      className="w-full bg-gray-700 text-white border border-gray-600 rounded-md pl-9 pr-3 py-2 text-sm focus:outline-none focus:border-blue-500"
                    />
                  </div>
                  <p className="text-[10px] text-gray-500">
                    Leave empty if you don't want to include it in the code snippet.
                  </p>
                </div>

                {/* Position */}
                <div className="space-y-1">
                  <label className="text-xs text-gray-400">Position</label>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      onClick={() => setConfig({ ...config, position: "left" })}
                      className={`px-3 py-2 rounded-md text-sm transition-colors border ${config.position === "left"
                        ? "bg-blue-500/20 border-blue-500 text-blue-400"
                        : "bg-gray-700 border-gray-600 text-gray-400 hover:bg-gray-600"
                        }`}
                    >
                      Bottom Left
                    </button>
                    <button
                      onClick={() => setConfig({ ...config, position: "right" })}
                      className={`px-3 py-2 rounded-md text-sm transition-colors border ${config.position === "right"
                        ? "bg-blue-500/20 border-blue-500 text-blue-400"
                        : "bg-gray-700 border-gray-600 text-gray-400 hover:bg-gray-600"
                        }`}
                    >
                      Bottom Right
                    </button>
                  </div>
                </div>

                {/* Color */}
                <div className="space-y-1">
                  <label className="text-xs text-gray-400">Theme Color</label>
                  <div className="flex items-center gap-2">
                    <input
                      type="color"
                      value={config.color}
                      onChange={(e) => setConfig({ ...config, color: e.target.value })}
                      className="h-9 w-9 p-1 bg-gray-700 border border-gray-600 rounded cursor-pointer"
                    />
                    <input
                      type="text"
                      value={config.color}
                      onChange={(e) => setConfig({ ...config, color: e.target.value })}
                      className="flex-1 bg-gray-700 text-white border border-gray-600 rounded-md px-3 py-2 text-sm font-mono focus:outline-none focus:border-blue-500 uppercase"
                    />
                  </div>
                </div>

                {/* Custom Icon Toggle */}
                {integrationType === "react" && (
                  <div className="space-y-1 pt-2 border-t border-gray-700">
                    <label className="flex items-center gap-2 cursor-pointer group">
                      <input
                        type="checkbox"
                        checked={config.showCustomIcon}
                        onChange={(e) => setConfig({ ...config, showCustomIcon: e.target.checked })}
                        className="checkbox checkbox-xs checkbox-primary rounded-sm"
                      />
                      <span className="text-sm text-gray-300 group-hover:text-white transition-colors">Show Custom Icon Example</span>
                    </label>
                    <p className="text-[10px] text-gray-500 pl-6">
                      Includes an example of how to pass a custom React component as an icon.
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Right Column - Code Preview */}
            <div className="lg:col-span-8 bg-gray-950 rounded-xl border border-gray-800 flex flex-col overflow-hidden">
              <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800 bg-gray-900/50">
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${integrationType === 'html' ? 'bg-orange-500' : 'bg-blue-500'}`}></div>
                  <span className="text-sm font-medium text-gray-300">
                    {integrationType === 'html' ? 'index.html' : 'App.tsx'}
                  </span>
                </div>
                <button
                  onClick={copyToClipboard}
                  className="flex items-center gap-2 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-xs font-medium transition-colors"
                >
                  {copied ? (
                    <>
                      <Check className="w-3.5 h-3.5" /> Copied
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" /> Copy Code
                    </>
                  )}
                </button>
              </div>

              <div className="flex-1 overflow-auto p-4 custom-scrollbar">
                <pre className="text-sm font-mono leading-relaxed text-gray-300">
                  {currentCode}
                </pre>
              </div>

              <div className="p-3 bg-gray-900/50 border-t border-gray-800 text-xs text-gray-500">
                {integrationType === 'html'
                  ? "Place this snippet in your <head> or just before the closing </body> tag."
                  : "Make sure to install the package: npm install @kaifusion/widget"
                }
              </div>
            </div>
          </div>

          <div className="modal-action mt-6 flex-shrink-0 flex items-center justify-end w-full gap-3">
            <button
              className={`flex items-center gap-2 px-3 py-1.5 text-white rounded-md text-xs font-medium transition-colors ${showPreview
                ? "bg-red-500 hover:bg-red-600"
                : "bg-blue-600 hover:bg-blue-700"
                }`}
              onClick={() => setShowPreview(!showPreview)}
            >
              {showPreview ? (
                <>Stop Testing</>
              ) : (
                <>
                  <Eye className="w-4 h-4" /> Test Widget
                </>
              )}
            </button>
            <form method="dialog">
              <button
                className="flex items-center gap-2 px-3 py-1.5 text-gray-400 border border-gray-600 rounded-md text-xs font-medium transition-colors hover:bg-gray-800 hover:text-white"
                onClick={() => setShowPreview(false)}
              >
                Close
              </button>
            </form>
          </div>
        </div>
        {showPreview && (
          <div className="fixed inset-0 z-[100] pointer-events-none">
            <div className="pointer-events-auto">
              <KaiChatWidget
                workflowId={config.workflowId}
                targetUrl={config.baseUrl}
                title={config.title}
                position={config.position}
                color={config.color}
                authToken={config.apiKey}
                icon={config.showCustomIcon ? <Bot className="w-7 h-7" /> : undefined}
              />
            </div>
          </div>
        )}
      </dialog>
    );
  }
);

WidgetExportModal.displayName = "WidgetExportModal";

export default WidgetExportModal;
