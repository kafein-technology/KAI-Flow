import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeRaw from "rehype-raw";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/cjs/styles/prism";
import {
  MessageSquare,
  X,
  Send,
  Maximize2,
  Minimize2,
  Loader2,
  Bot,
  Copy,
  CheckCircle,
  Terminal,
  FileText,
  ExternalLink,
  RefreshCcw,
  Quote,
} from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { v4 as uuidv4 } from "uuid";
import { config } from "../lib/config";

interface Message {
  id: string;
  content: string;
  isBot: boolean;
  timestamp: Date;
  isError?: boolean;
}

export interface KaiChatWidgetProps {
  authToken: string;
  workflowId: string;
  title?: string;
  targetUrl: string;
  position?: "left" | "right";
  color?: string;
  icon?: React.ReactNode;
}

export default function KaiChatWidget({
  authToken,
  workflowId,
  title = "ChatBot",
  targetUrl,
  position = "right",
  color = "#526cfe",
  icon,
}: KaiChatWidgetProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isMaximized, setIsMaximized] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      content: "Merhaba! Size nasıl yardımcı olabilirim?",
      isBot: true,
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [copiedCode, setCopiedCode] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const sessionIdRef = useRef(uuidv4());

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedCode(text);
      setTimeout(() => {
        setCopiedCode(null);
      }, 2000);
    } catch (err) {
      console.error("Kopyalama başarısız:", err);
    }
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isOpen]);

  // Focus input when chat opens or loading finishes
  useEffect(() => {
    if (isOpen && !isLoading) {
      inputRef.current?.focus();
    }
  }, [isOpen, isLoading]);

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: uuidv4(),
      content: input,
      isBot: false,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    // Bot mesajı için placeholder oluştur
    const botMessageId = uuidv4();
    setMessages((prev) => [
      ...prev,
      {
        id: botMessageId,
        content: "",
        isBot: true,
        timestamp: new Date(),
      },
    ]);

    try {
      const token = authToken || localStorage.getItem("auth_access_token");
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      };

      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
        headers["X-API-Key"] = token;
      }

      const response = await fetch(`${targetUrl}/${config.API_START}/${config.API_VERSION_ONLY}/workflows/execute`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          input_text: userMessage.content,
          session_id: sessionIdRef.current,
          chatflow_id: sessionIdRef.current,
          workflow_id: workflowId,
        }),
      });

      const contentType = response.headers.get("content-type");
      if (contentType && contentType.includes("application/json")) {
        const data = await response.json();
        if (data.error) {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === botMessageId
                ? { ...msg, content: data.message, isError: true }
                : msg
            )
          );
          return;
        }
      }

      if (!response.body) throw new Error("ReadableStream not supported");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let fullText = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6).trim();
            if (data === "[DONE]" || !data) continue;

            try {
              const parsed = JSON.parse(data);
              let newContent = "";

              if (parsed.type === "token" && parsed.content) {
                newContent = parsed.content;
              } else if (parsed.type === "output" && parsed.output) {
                newContent = parsed.output;
              } else if (parsed.type === "complete" && parsed.result) {
                if (typeof parsed.result === "string" && !fullText) {
                  newContent = parsed.result;
                }
              }

              if (newContent) {
                fullText += newContent;
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === botMessageId
                      ? { ...msg, content: fullText }
                      : msg
                  )
                );
              }
            } catch (e) {
              console.warn("Stream parse error:", e);
            }
          }
        }
      }
    } catch (error) {
      console.error("API Error:", error);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === botMessageId
            ? { ...msg, content: "Üzgünüm, bir hata oluştu.", isError: true }
            : msg
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  const clearHistory = () => {
    setMessages([]);
    sessionIdRef.current = uuidv4();
  };

  return (
    <div
      className={`fixed bottom-5 z-50 flex flex-col items-end gap-4 font-sans ${position === "left" ? "left-5" : "right-5"
        }`}
      style={{ fontFamily: "system-ui, -apple-system, sans-serif" }}
    >
      {/* Overlay - Tam Ekran Modu İçin */}
      <AnimatePresence>
        {isOpen && isMaximized && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
            onClick={() => setIsMaximized(false)}
          />
        )}
      </AnimatePresence>

      {/* Chat Penceresi */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{
              opacity: 1,
              y: 0,
              scale: 1,
              width: isMaximized ? "900px" : "400px",
              height: isMaximized ? "85vh" : "600px",
            }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            className={`rounded-2xl shadow-2xl flex flex-col overflow-hidden z-50 transition-all duration-300 ${isMaximized
              ? "fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 m-0"
              : "relative"
              }`}
          >
            {/* Header */}
            <div
              className="px-4 py-3 text-white flex justify-between items-center shadow-md"
              style={{ background: color }}
            >
              <div className="flex items-center gap-2 font-semibold">
                <Bot className="w-5 h-5" />
                {title}
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={clearHistory}
                  className="p-1.5 hover:bg-white/20 rounded-full transition-colors"
                  title="Sohbeti Temizle"
                >
                  <RefreshCcw className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setIsMaximized(!isMaximized)}
                  className="p-1.5 hover:bg-white/20 rounded-full transition-colors"
                >
                  {isMaximized ? (
                    <Minimize2 className="w-4 h-4" />
                  ) : (
                    <Maximize2 className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>

            {/* Mesajlar */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.isBot ? "justify-start" : "justify-end"
                    } ${msg.isBot && !msg.content && !msg.isError ? "hidden" : ""
                    }`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-3 shadow-sm ${msg.isBot
                      ? msg.isError
                        ? "bg-red-50 text-red-600 border border-red-100"
                        : "bg-white text-gray-800 border border-gray-100"
                      : "text-white"
                      }`}
                    style={!msg.isBot ? { backgroundColor: color } : {}}
                  >
                    <div className="max-w-none break-words">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm, remarkMath]}
                        rehypePlugins={[rehypeKatex, rehypeRaw]}
                        components={{
                          // Kod blokları - modern tasarım ile
                          code: ({ className, children, ...props }: any) => {
                            const match = /language-(\w+)/.exec(
                              className || ""
                            );
                            const language = match ? match[1] : "";
                            const isInline = !match;
                            const codeContent = String(children).replace(
                              /\n$/,
                              ""
                            );

                            return !isInline ? (
                              <div className="relative group my-2 sm:my-4 rounded-xl shadow-lg border border-gray-200 w-full overflow-hidden">
                                {/* Header with language and copy button */}
                                <div
                                  className="flex items-center justify-between px-4 py-2 text-[#f3f4f6] border-b border-[#374151]"
                                  style={{
                                    background:
                                      "linear-gradient(to right, #1f2937, #111827)",
                                    fontSize: "14px",
                                  }}
                                >
                                  <div className="flex items-center gap-2 min-w-0 flex-1">
                                    <Terminal className="w-4 h-4 text-blue-400 flex-shrink-0" />
                                    <span className="font-medium capitalize truncate">
                                      {language || "plaintext"}
                                    </span>
                                  </div>
                                  <button
                                    onClick={() => copyToClipboard(codeContent)}
                                    className="flex items-center gap-1 px-3 py-1 bg-[#374151] hover:bg-[#4b5563] text-[#e5e7eb] rounded-md transition-all duration-200 text-xs font-medium cursor-pointer"
                                    style={{ fontSize: "12px" }}
                                  >
                                    {copiedCode === codeContent ? (
                                      <>
                                        <CheckCircle className="w-3 h-3 text-green-400" />
                                        <span>Kopyalandı!</span>
                                      </>
                                    ) : (
                                      <>
                                        <Copy className="w-3 h-3" />
                                        <span>Kopyala</span>
                                      </>
                                    )}
                                  </button>
                                </div>

                                {/* Syntax highlighted code */}
                                <div className="bg-gray-950 overflow-x-auto">
                                  <SyntaxHighlighter
                                    style={vscDarkPlus}
                                    language={language || "text"}
                                    customStyle={{
                                      margin: 0,
                                      padding: "1rem",
                                      fontSize: "0.75rem",
                                      lineHeight: "1.4",
                                      background: "transparent",
                                      borderRadius: 0,
                                    }}
                                    showLineNumbers={
                                      codeContent.split("\n").length > 5
                                    }
                                    lineNumberStyle={{
                                      color: "#6b7280",
                                      fontSize: "0.7rem",
                                      marginRight: "0.5rem",
                                      userSelect: "none",
                                    }}
                                    wrapLongLines={false}
                                  >
                                    {codeContent}
                                  </SyntaxHighlighter>
                                </div>
                              </div>
                            ) : (
                              <code
                                className="bg-blue-50 text-blue-700 px-2 py-1 rounded-md text-sm font-mono border border-blue-200 font-medium"
                                {...props}
                              >
                                {children}
                              </code>
                            );
                          },

                          // Pre etiketleri için beyaz arka plan
                          pre: ({ children }: any) => (
                            <pre className="bg-white max-w-full rounded-lg text-sm ">
                              {children}
                            </pre>
                          ),

                          // Başlıklar - modern hiyerarşi (Daha kompakt)
                          h1: ({ children }: any) => (
                            <h1 className="text-lg font-bold mb-2 text-gray-900 pb-2 border-b-2 border-gradient-to-r from-blue-500 to-purple-600 relative">
                              <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                                {children}
                              </span>
                            </h1>
                          ),
                          h2: ({ children }: any) => (
                            <h2 className="text-base font-bold mb-2 text-gray-900 mt-4 flex items-center gap-2">
                              <span className="w-1 h-5 bg-gradient-to-b from-blue-500 to-purple-600 rounded-full"></span>
                              {children}
                            </h2>
                          ),
                          h3: ({ children }: any) => (
                            <h3 className="text-sm font-semibold mb-2 text-gray-800 mt-3 flex items-center gap-2">
                              <span className="w-1 h-4 bg-gradient-to-b from-blue-400 to-purple-500 rounded-full"></span>
                              {children}
                            </h3>
                          ),
                          h4: ({ children }: any) => (
                            <h4 className="text-xs font-semibold mb-1 text-gray-700 mt-2 flex items-center gap-2">
                              <span className="w-0.5 h-3 bg-gradient-to-b from-blue-400 to-purple-500 rounded-full"></span>
                              {children}
                            </h4>
                          ),

                          // Listeler - modern tasarım ile
                          ul: ({ children }: any) => (
                            <ul className="mb-2 space-y-0.5 text-sm">
                              {children}
                            </ul>
                          ),
                          ol: ({ children }: any) => (
                            <ol className="mt-3 mb-2 space-y-0.5 counter-reset-list text-sm">
                              {children}
                            </ol>
                          ),
                          li: ({ children, ...props }: any) => {
                            const isOrderedList =
                              props.className?.includes("ordered") ||
                              (typeof children === "object" &&
                                children?.props?.ordered);

                            return isOrderedList ? (
                              <li
                                className={`flex items-start gap-2 pl-1 leading-relaxed ${!msg.isBot ? "text-white" : "text-gray-700"
                                  }`}
                              >
                                <span className="flex-shrink-0 w-5 h-5 bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-full flex items-center justify-center text-[10px] font-bold mt-0.5 shadow-sm counter-increment">
                                  •
                                </span>
                                <div className="flex-1 pt-0.5 text-left">
                                  {children}
                                </div>
                              </li>
                            ) : (
                              <li
                                className={`flex items-start gap-2 pl-1 leading-relaxed ${!msg.isBot ? "text-white" : "text-gray-700"
                                  }`}
                              >
                                <span className="flex-shrink-0 w-1.5 h-1.5 bg-gradient-to-r from-blue-500 to-purple-600 rounded-full mt-2 shadow-sm"></span>
                                <div className="flex-1 text-left">
                                  {children}
                                </div>
                              </li>
                            );
                          },

                          // Linkler
                          a: ({ href, children }: any) => (
                            <a
                              href={href}
                              className="text-blue-600 hover:text-blue-800 underline inline-flex items-center gap-0.5 transition-colors duration-200 break-all max-w-full text-sm"
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              <span className="break-all">{children}</span>
                              <ExternalLink className="w-3 h-3 flex-shrink-0" />
                            </a>
                          ),

                          // Alıntılar - modern tasarım
                          blockquote: ({ children }: any) => (
                            <blockquote className="relative my-2 sm:my-4 p-3 sm:p-4 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg shadow-sm -mx-1 sm:mx-0">
                              <div className="absolute top-2 sm:top-3 left-2 sm:left-3">
                                <Quote className="w-3 h-3 sm:w-4 sm:h-4 text-blue-400 opacity-60" />
                              </div>
                              <div className="pl-4 sm:pl-6">
                                <div className="text-blue-600 text-[10px] sm:text-xs font-semibold mb-1 uppercase tracking-wide">
                                  Alıntı
                                </div>
                                <div className="text-gray-700 italic leading-relaxed text-xs sm:text-sm">
                                  {children}
                                </div>
                              </div>
                              <div className="absolute bottom-2 sm:bottom-3 right-2 sm:right-3">
                                <Quote className="w-2 h-2 sm:w-3 sm:h-3 text-blue-300 opacity-40 rotate-180" />
                              </div>
                            </blockquote>
                          ),

                          // Tablolar - modern responsive tasarım
                          table: ({ children }: any) => (
                            <div className="overflow-x-auto my-2 sm:my-4 rounded-lg border border-gray-200 shadow-sm bg-white -mx-1 sm:mx-0">
                              <table className="min-w-full text-xs">
                                {children}
                              </table>
                            </div>
                          ),
                          thead: ({ children }: any) => (
                            <thead className="bg-gradient-to-r from-gray-50 to-gray-100">
                              {children}
                            </thead>
                          ),
                          th: ({ children }: any) => (
                            <th className="px-2 sm:px-4 py-1.5 sm:py-2 text-left font-semibold text-gray-900 border-b border-gray-200 first:rounded-tl-lg last:rounded-tr-lg">
                              <div className="flex items-center gap-1">
                                <FileText className="w-3 h-3 text-gray-500 hidden sm:block" />
                                <span className="truncate">{children}</span>
                              </div>
                            </th>
                          ),
                          tbody: ({ children }: any) => (
                            <tbody className="divide-y divide-gray-100">
                              {children}
                            </tbody>
                          ),
                          tr: ({ children }: any) => (
                            <tr className="hover:bg-gray-50 transition-colors duration-150">
                              {children}
                            </tr>
                          ),
                          td: ({ children }: any) => (
                            <td className="px-2 sm:px-4 py-1.5 sm:py-2 text-gray-700 leading-relaxed text-xs">
                              <div
                                className="truncate max-w-[150px] sm:max-w-none"
                                title={
                                  typeof children === "string" ? children : ""
                                }
                              >
                                {children}
                              </div>
                            </td>
                          ),

                          // Paragraflar - daha iyi spacing
                          p: ({ children }: any) => (
                            <p
                              className={`m-0! last:mb-0 leading-relaxed break-words overflow-wrap-anywhere text-sm ${!msg.isBot ? "text-white" : "text-gray-700"
                                }`}
                            >
                              {children}
                            </p>
                          ),

                          // Vurgu metinleri
                          strong: ({ children }: any) => (
                            <strong
                              className={`font-bold inline ${!msg.isBot ? "text-white" : "text-gray-900"
                                }`}
                            >
                              {children}
                            </strong>
                          ),
                          em: ({ children }: any) => (
                            <em
                              className={`italic ${!msg.isBot ? "text-white/90" : "text-gray-600"
                                }`}
                            >
                              {children}
                            </em>
                          ),

                          // Çizgi
                          hr: () => <hr className="border-gray-300 my-4" />,

                          // Resimler - responsive
                          img: ({ src, alt }: any) => (
                            <img
                              src={src}
                              alt={alt}
                              className="max-w-full h-auto rounded-lg shadow-sm my-2"
                              loading="lazy"
                            />
                          ),

                          // Matematik formülleri için
                          div: ({ className, children, ...props }: any) => {
                            if (className === "math math-display") {
                              return (
                                <div className="my-4 text-center bg-gray-50 p-3 rounded-lg border">
                                  <div className={className} {...props}>
                                    {children}
                                  </div>
                                </div>
                              );
                            }
                            return (
                              <div className={className} {...props}>
                                {children}
                              </div>
                            );
                          },

                          // Inline matematik
                          span: ({ className, children, ...props }: any) => {
                            if (className === "math math-inline") {
                              return (
                                <span className="bg-gray-100 px-1 py-0.5 rounded text-sm font-mono">
                                  <span className={className} {...props}>
                                    {children}
                                  </span>
                                </span>
                              );
                            }
                            return (
                              <span className={className} {...props}>
                                {children}
                              </span>
                            );
                          },
                        }}
                      >
                        {msg.content}
                      </ReactMarkdown>
                    </div>
                  </div>
                </div>
              ))}
              {isLoading && (
                <div className="flex justify-start">
                  <div className="bg-white border border-gray-100 rounded-2xl px-4 py-3 shadow-sm flex items-center gap-2">
                    <span className="text-xs text-gray-500">Yazıyor</span>
                    <div className="flex space-x-1">
                      <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                      <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                      <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"></div>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input Alanı */}
            <div className="p-4 bg-white border-t border-gray-100">
              <div className="flex gap-2 items-center bg-gray-50 rounded-full px-4 py-2 border border-gray-200 focus-within:border-blue-500 focus-within:ring-1 focus-within:ring-blue-500 transition-all">
                <input
                  ref={inputRef}
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      sendMessage();
                      // Immediate focus attempt after sending
                      setTimeout(() => inputRef.current?.focus(), 0);
                    }
                  }}
                  placeholder="Write your message..."
                  className="flex-1 bg-transparent border-none focus:ring-0 outline-none text-sm py-1"
                  disabled={isLoading}
                />
                <button
                  onClick={sendMessage}
                  disabled={isLoading || !input.trim()}
                  className={`p-2 rounded-full transition-all ${input.trim() && !isLoading
                    ? "text-blue-600 hover:bg-blue-50"
                    : "text-gray-400"
                    }`}
                >
                  {isLoading ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <Send className="w-5 h-5" />
                  )}
                </button>
              </div>
              <div className="text-center mt-2">
                <span className="text-[10px] text-gray-400">
                  Powered by Agenticgro
                </span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <motion.button
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
        onClick={() => setIsOpen(!isOpen)}
        className="w-14 h-14 rounded-full shadow-xl flex items-center justify-center text-white transition-shadow hover:shadow-2xl"
        style={{ backgroundColor: color }}
      >
        {isOpen ? (
          <X className="w-7 h-7" />
        ) : (
          icon || <MessageSquare className="w-7 h-7" />
        )}
      </motion.button>
    </div>
  );
}
