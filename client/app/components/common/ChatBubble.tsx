import React, { useState } from "react";
import {
  Bot,
  Copy,
  Check,
  ExternalLink,
  Edit,
  Trash2,
  Terminal,
  FileText,
  Quote,
  CheckCircle,
} from "./Icon";
import { useAuth } from "~/stores/auth";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeRaw from "rehype-raw";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/cjs/styles/prism";
import { copyWithFeedback } from "~/lib/clipboard";
interface ChatBubbleProps {
  message: string;
  from: "user" | "assistant";
  loading?: boolean;
  userAvatarUrl?: string;
  userInitial?: string;
  timestamp?: Date;
  messageId?: string;
  onEdit?: (messageId: string, newContent: string) => void;
  onDelete?: (messageId: string) => void;
  isEditing?: boolean;
  onSaveEdit?: (messageId: string, newContent: string) => void;
  onCancelEdit?: () => void;
}

const ChatBubble: React.FC<ChatBubbleProps> = ({
  message,
  from,
  loading,
  userAvatarUrl,
  userInitial,
  timestamp,
  messageId,
  onEdit,
  onDelete,
  isEditing,
  onSaveEdit,
  onCancelEdit,
}) => {
  const { user } = useAuth();
  const [copiedCode, setCopiedCode] = useState<string | null>(null);
  const [editContent, setEditContent] = useState(message);
  const isUser = from === "user";

  const copyToClipboard = async (text: string) => {
    await copyWithFeedback(
      text,
      () => {
        setCopiedCode(text);
        setTimeout(() => {
          setCopiedCode(null);
        }, 2000);
      },
      (err) => {
        console.error("Kopyalama başarısız:", err);
      }
    );
  };

  const formatTimestamp = (date: Date) => {
    return date.toLocaleTimeString("tr-TR", {
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const handleEdit = () => {
    if (messageId && onEdit) {
      onEdit(messageId, message);
    }
  };

  const handleDelete = () => {
    if (messageId && onDelete) {
      onDelete(messageId);
    }
  };

  const handleSaveEdit = () => {
    if (messageId && onSaveEdit) {
      onSaveEdit(messageId, editContent);
    }
  };

  const handleCancelEdit = () => {
    setEditContent(message);
    if (onCancelEdit) {
      onCancelEdit();
    }
  };

  return (
    <div
      className={`flex w-full my-3 px-2 sm:px-4 ${
        isUser ? "justify-end" : "justify-start"
      }`}
    >
      {/* Assistant Avatar */}
      {!isUser && (
        <div className="flex flex-col items-center mr-2 sm:mr-3 flex-shrink-0">
          <div className="w-8 h-8 sm:w-9 sm:h-9 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center shadow-lg border-2 border-white">
            <Bot className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
          </div>
          {timestamp && (
            <span className="text-xs text-gray-400 mt-1 hidden sm:block">
              {formatTimestamp(timestamp)}
            </span>
          )}
        </div>
      )}

      <div
        className={`max-w-[calc(100%-3rem)] sm:max-w-[85%] px-3 sm:px-4 py-2 sm:py-3 rounded-2xl shadow-lg text-sm
        ${
          isUser
            ? "bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-br-md border border-blue-400"
            : "bg-white text-gray-800 rounded-bl-md border border-gray-200"
        }
        relative transition-all duration-200 hover:shadow-xl group`}
      >
        {/* Action buttons for user messages */}
        {isUser && messageId && !isEditing && (
          <div className="absolute -top-2 -right-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex gap-1">
            <button
              onClick={handleEdit}
              className="w-6 h-6 bg-blue-500 hover:bg-blue-600 text-white rounded-full flex items-center justify-center text-xs shadow-lg"
              title="Düzenle"
            >
              <Edit className="w-3 h-3" />
            </button>
            <button
              onClick={handleDelete}
              className="w-6 h-6 bg-red-500 hover:bg-red-600 text-white rounded-full flex items-center justify-center text-xs shadow-lg"
              title="Sil"
            >
              <Trash2 className="w-3 h-3" />
            </button>
          </div>
        )}

        {loading && !isUser ? (
          <div className="flex items-center gap-3">
            <div className="flex space-x-1">
              <div className="w-2 h-2 bg-gradient-to-r from-blue-500 to-purple-600 rounded-full animate-pulse"></div>
              <div
                className="w-2 h-2 bg-gradient-to-r from-blue-500 to-purple-600 rounded-full animate-pulse"
                style={{ animationDelay: "0.2s" }}
              ></div>
              <div
                className="w-2 h-2 bg-gradient-to-r from-blue-500 to-purple-600 rounded-full animate-pulse"
                style={{ animationDelay: "0.4s" }}
              ></div>
            </div>
            <span className="italic text-gray-600 font-medium">
              Thinking...
            </span>
          </div>
        ) : (
          <div className="w-full">
            {isUser && isEditing ? (
              <div className="space-y-2">
                <textarea
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  className="w-full p-2 border border-gray-300 rounded-lg text-sm text-gray-800 bg-white resize-none"
                  rows={Math.max(2, editContent.split("\n").length)}
                  autoFocus
                />
                <div className="flex gap-2">
                  <button
                    onClick={handleSaveEdit}
                    className="px-3 py-1 bg-green-500 hover:bg-green-600 text-white rounded text-xs"
                  >
                    Save
                  </button>
                  <button
                    onClick={handleCancelEdit}
                    className="px-3 py-1 bg-gray-500 hover:bg-gray-600 text-white rounded text-xs"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : isUser ? (
              <div className="whitespace-pre-wrap break-words leading-relaxed">
                {message}
              </div>
            ) : (
              <div className="prose prose-sm max-w-none prose-slate break-words">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkMath]}
                  rehypePlugins={[rehypeKatex, rehypeRaw]}
                  components={{
                    // Kod blokları - modern tasarım ile
                    code: ({ className, children, ...props }: any) => {
                      const match = /language-(\w+)/.exec(className || "");
                      const language = match ? match[1] : "";
                      const isInline = !match;
                      const codeContent = String(children).replace(/\n$/, "");

                      return !isInline ? (
                        <div className="relative group my-4 sm:my-6 rounded-xl shadow-lg border border-gray-200 w-full overflow-hidden">
                          {/* Header with language and copy button */}
                          <div className="flex items-center justify-between bg-gradient-to-r from-gray-800 to-gray-900 text-gray-100 px-3 sm:px-4 py-2 sm:py-3 border-b border-gray-700">
                            <div className="flex items-center gap-2 min-w-0 flex-1">
                              <Terminal className="w-4 h-4 text-blue-400 flex-shrink-0" />
                              <span className="text-sm font-medium capitalize text-gray-200 truncate">
                                {language || "plaintext"}
                              </span>
                              {language && (
                                <span className="hidden sm:inline text-xs px-2 py-1 bg-gray-700 text-gray-300 rounded-full">
                                  {language}
                                </span>
                              )}
                            </div>
                            <button
                              onClick={() => copyToClipboard(codeContent)}
                              className="flex items-center gap-1 sm:gap-2 px-2 sm:px-3 py-1 sm:py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg transition-all duration-200 text-xs sm:text-sm font-medium group-hover:shadow-md flex-shrink-0"
                            >
                              {copiedCode === codeContent ? (
                                <>
                                  <CheckCircle className="w-3 h-3 sm:w-4 sm:h-4 text-green-400" />
                                  <span className="hidden sm:inline">
                                    Kopyalandı!
                                  </span>
                                  <span className="sm:hidden">✓</span>
                                </>
                              ) : (
                                <>
                                  <Copy className="w-3 h-3 sm:w-4 sm:h-4" />
                                  <span className="hidden sm:inline">
                                    Kopyala
                                  </span>
                                </>
                              )}

                              <span className="text-xs">
                                {copiedCode === codeContent
                                  ? "Copied!"
                                  : "Copy"}
                              </span>

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
                      <pre className="bg-white max-w-full overflow-x-auto p-3 rounded-lg text-sm ">
                        {children}
                      </pre>
                    ),

                    // Başlıklar - modern hiyerarşi
                    h1: ({ children }: any) => (
                      <h1 className="text-xl font-bold mb-4 text-gray-900 pb-3 border-b-2 border-gradient-to-r from-blue-500 to-purple-600 relative">
                        <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                          {children}
                        </span>
                      </h1>
                    ),
                    h2: ({ children }: any) => (
                      <h2 className="text-lg font-bold mb-3 text-gray-900 mt-6 flex items-center gap-2">
                        <span className="w-1 h-6 bg-gradient-to-b from-blue-500 to-purple-600 rounded-full"></span>
                        {children}
                      </h2>
                    ),
                    h3: ({ children }: any) => (
                      <h3 className="text-md font-semibold mb-3 text-gray-800 mt-5 flex items-center gap-2">
                        <span className="w-1 h-5 bg-gradient-to-b from-blue-400 to-purple-500 rounded-full"></span>
                        {children}
                      </h3>
                    ),
                    h4: ({ children }: any) => (
                      <h4 className="text-md font-semibold mb-2 text-gray-700 mt-4 flex items-center gap-2">
                        <span className="w-0.5 h-4 bg-gradient-to-b from-blue-400 to-purple-500 rounded-full"></span>
                        {children}
                      </h4>
                    ),

                    // Listeler - modern tasarım ile
                    ul: ({ children }: any) => (
                      <ul className="mb-4 space-y-1">{children}</ul>
                    ),
                    ol: ({ children }: any) => (
                      <ol className="mb-4 space-y-1 counter-reset-list">
                        {children}
                      </ol>
                    ),
                    li: ({ children, ...props }: any) => {
                      const isOrderedList =
                        props.className?.includes("ordered") ||
                        (typeof children === "object" &&
                          children?.props?.ordered);

                      return isOrderedList ? (
                        <li className="flex items-start gap-3 pl-2 leading-relaxed text-gray-700">
                          <span className="flex-shrink-0 w-6 h-6 bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-full flex items-center justify-center text-xs font-bold mt-0.5 shadow-sm counter-increment">
                            •
                          </span>
                          <div className="flex-1 pt-0.5 text-left">{children}</div>
                        </li>
                      ) : (
                        <li className="flex items-start gap-3 pl-2 leading-relaxed text-gray-700">
                          <span className="flex-shrink-0 w-2 h-2 bg-gradient-to-r from-blue-500 to-purple-600 rounded-full mt-2.5 shadow-sm"></span>
                          <div className="flex-1 text-left">{children}</div>
                        </li>
                      );
                    },

                    // Linkler - dış bağlantı ikonu ile
                    a: ({ href, children }: any) => (
                      <a
                        href={href}
                        className="text-blue-600 hover:text-blue-800 underline inline-flex items-center gap-1 transition-colors duration-200 break-all max-w-full"
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        <span className="break-all">{children}</span>
                        <ExternalLink className="w-3 h-3 flex-shrink-0" />
                      </a>
                    ),

                    // Alıntılar - modern tasarım
                    blockquote: ({ children }: any) => (
                      <blockquote className="relative my-4 sm:my-6 p-4 sm:p-6 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-xl shadow-sm -mx-2 sm:mx-0">
                        <div className="absolute top-3 sm:top-4 left-3 sm:left-4">
                          <Quote className="w-4 h-4 sm:w-6 sm:h-6 text-blue-400 opacity-60" />
                        </div>
                        <div className="pl-6 sm:pl-8">
                          <div className="text-blue-600 text-xs sm:text-sm font-semibold mb-2 uppercase tracking-wide">
                            Alıntı
                          </div>
                          <div className="text-gray-700 italic leading-relaxed text-sm sm:text-base">
                            {children}
                          </div>
                        </div>
                        <div className="absolute bottom-3 sm:bottom-4 right-3 sm:right-4">
                          <Quote className="w-3 h-3 sm:w-4 sm:h-4 text-blue-300 opacity-40 rotate-180" />
                        </div>
                      </blockquote>
                    ),

                    // Tablolar - modern responsive tasarım
                    table: ({ children }: any) => (
                      <div className="overflow-x-auto my-4 sm:my-6 rounded-xl border border-gray-200 shadow-lg bg-white -mx-2 sm:mx-0">
                        <table className="min-w-full text-xs sm:text-sm">
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
                      <th className="px-3 sm:px-6 py-2 sm:py-4 text-left font-semibold text-gray-900 border-b border-gray-200 first:rounded-tl-xl last:rounded-tr-xl">
                        <div className="flex items-center gap-1 sm:gap-2">
                          <FileText className="w-3 h-3 sm:w-4 sm:h-4 text-gray-500 hidden sm:block" />
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
                      <td className="px-3 sm:px-6 py-2 sm:py-4 text-gray-700 leading-relaxed text-xs sm:text-sm">
                        <div
                          className="truncate max-w-[200px] sm:max-w-none"
                          title={typeof children === "string" ? children : ""}
                        >
                          {children}
                        </div>
                      </td>
                    ),

                    // Paragraflar - daha iyi spacing
                    p: ({ children }: any) => (
                      <p className="mb-3 last:mb-0 text-gray-700 leading-relaxed break-words overflow-wrap-anywhere">
                        {children}
                      </p>
                    ),

                    // Vurgu metinleri
                    strong: ({ children }: any) => (
                      <strong className="font-bold text-gray-900 inline">
                        {children}
                      </strong>
                    ),
                    em: ({ children }: any) => (
                      <em className="italic text-gray-600">{children}</em>
                    ),

                    // Çizgi
                    hr: () => <hr className="border-gray-300 my-6" />,

                    // Resimler - responsive
                    img: ({ src, alt }: any) => (
                      <img
                        src={src}
                        alt={alt}
                        className="max-w-full h-auto rounded-lg shadow-md my-3"
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
                  {message}
                </ReactMarkdown>
              </div>
            )}
          </div>
        )}
      </div>

      {/* User Avatar */}
      {isUser && (
        <div className="flex flex-col items-center ml-2 sm:ml-3 flex-shrink-0">
          {userAvatarUrl ? (
            <img
              src={userAvatarUrl}
              alt="User"
              className="w-8 h-8 sm:w-9 sm:h-9 rounded-full object-cover shadow-lg border-2 border-white"
            />
          ) : (
            <div className="w-8 h-8 sm:w-9 sm:h-9 bg-gradient-to-br from-blue-500 to-blue-600 rounded-full flex items-center justify-center text-white font-bold shadow-lg border-2 border-white text-xs sm:text-sm">
              {user?.full_name?.[0]?.toUpperCase() ||
                userInitial?.toUpperCase() ||
                "U"}
            </div>
          )}
          {timestamp && (
            <span className="text-xs text-gray-400 mt-1 hidden sm:block">
              {formatTimestamp(timestamp)}
            </span>
          )}
        </div>
      )}
    </div>
  );
};

export default ChatBubble;
