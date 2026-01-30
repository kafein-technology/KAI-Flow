/**
 * Centralized utility functions for resolving icon paths.
 * This module handles the complexity of icon path resolution,
 * ensuring all icons correctly include the BASE_PATH prefix.
 */

/**
 * Resolves an icon path to an absolute URL with BASE_PATH.
 * Handles various path formats: relative, absolute, and full URLs.
 * 
 * @param iconPath - The icon path to resolve (e.g., "icons/openai.svg")
 * @returns The resolved path with BASE_PATH prefix, or undefined if no path
 */
export function resolveIconPath(iconPath: string | undefined | null): string | undefined {
    if (!iconPath) return undefined;

    const basePath = window.VITE_BASE_PATH || "";

    // Already absolute URL (http:// or https://)
    if (iconPath.startsWith("http://") || iconPath.startsWith("https://")) {
        return iconPath;
    }

    // Already has base path prefix
    if (basePath && iconPath.startsWith(basePath + "/")) {
        return iconPath;
    }
    if (basePath && iconPath.startsWith(basePath) && iconPath.charAt(basePath.length) === "/") {
        return iconPath;
    }

    // Relative path without leading slash (most common case: "icons/openai.svg")
    if (!iconPath.startsWith("/")) {
        // If basePath is "/" or ends with "/", don't add another slash
        if (basePath === "/" || basePath.endsWith("/")) {
            return `${basePath}${iconPath}`;
        }
        return `${basePath}/${iconPath}`;
    }

    // Absolute path without base path (e.g., "/icons/openai.svg")
    // If basePath is present (and not just "/"), prepend it
    if (basePath && basePath !== "/") {
        // If basePath ends with / and iconPath starts with /, remove one
        if (basePath.endsWith("/")) {
            return `${basePath.slice(0, -1)}${iconPath}`;
        }
        return `${basePath}${iconPath}`;
    }
    return iconPath;
}

/**
 * Gets the full icon path for a known node type.
 * Uses lazy evaluation to ensure BASE_PATH is read at call time, not module load time.
 * 
 * @param nodeType - The node type identifier (e.g., "OpenAIChat", "StartNode")
 * @returns The full resolved icon path
 */
export function getNodeTypeIconPath(nodeType: string): string {
    const relativePaths: Record<string, string> = {
        // Flow Control
        StartNode: "icons/actions/rocket.svg",
        start: "icons/actions/rocket.svg",
        TimerStart: "icons/time/clock.svg",
        EndNode: "icons/navigation/flag.svg",
        ConditionalChain: "icons/misc/git-compare.svg",
        RouterChain: "icons/misc/git-branch.svg",

        // AI & Embedding
        Agent: "icons/communication/bot.svg",
        CohereEmbeddings: "icons/providers/cohere.svg",
        OpenAIEmbedder: "icons/providers/openai.svg",

        // Memory
        BufferMemory: "icons/file/database.svg",
        ConversationMemory: "icons/communication/message-circle.svg",

        // Documents & Data
        TextDataLoader: "icons/file/file-text.svg",
        DocumentLoader: "icons/file/file-input.svg",
        ChunkSplitter: "icons/file/scissors.svg",
        StringInputNode: "icons/file/type.svg",
        PGVectorStore: "icons/providers/postgresql_vectorstore.svg",
        VectorStoreOrchestrator: "icons/providers/postgresql_vectorstore.svg",
        IntelligentVectorStore: "icons/providers/postgresql_vectorstore.svg",

        // Web & APIs
        TavilySearch: "icons/providers/tavily-nonbrand.svg",
        WebScraper: "icons/misc/pickaxe.svg",
        HttpRequest: "icons/misc/globe.svg",
        WebhookTrigger: "icons/providers/webhook.svg",
        RespondToWebhook: "icons/providers/webhook.svg",

        // RAG & QA
        RetrievalQA: "icons/misc/book-open.svg",
        Reranker: "icons/providers/cohere.svg",
        CohereRerankerProvider: "icons/providers/cohere.svg",
        RetrieverProvider: "icons/file/file-stack.svg",
        RetrieverNode: "icons/ui_elements/search.svg",
        OpenAIEmbeddingsProvider: "icons/providers/openai.svg",

        // LLM Providers
        OpenAICompatibleNode: "icons/providers/openai.svg",
        OpenAIChat: "icons/providers/openai.svg",
        OpenAIEmbeddings: "icons/providers/openai.svg",

        // Processing Nodes
        CodeNode: "icons/file/code.svg",
        ConditionNode: "icons/misc/condition.svg",
    };

    const relativePath = relativePaths[nodeType];
    if (!relativePath) {
        return ""; // Return empty for unknown types, let caller decide fallback
    }

    return resolveIconPath(relativePath)!;
}

/**
 * Checks if a node type has a registered icon.
 */
export function hasNodeTypeIcon(nodeType: string): boolean {
    return !!getNodeTypeIconPath(nodeType);
}
