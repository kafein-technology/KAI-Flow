/**
 * KAI-Fusion Widget - Pure JavaScript Chat Widget
 * Makes direct requests to target API without backend dependency
 */

(function () {
    'use strict';

    // Configuration
    const config = {
        targetUrl: '',
        apiKey: '',
        workflowId: '',
        title: 'KAI-Fusion AI',
        position: 'right',
        color: '#2563eb',
        width: '',
        height: '',
        icon: {
            data: '💬',
            format: 'emoji'
        }
    };

    // Widget state
    let isOpen = false;
    let elements = {};
    let sessionId = null;

    // Initialize widget
    function init() {
        // Load Marked.js for Markdown parsing
        if (!window.marked) {
            const script = document.createElement('script');
            script.src = "https://cdn.jsdelivr.net/npm/marked/marked.min.js";

            script.onload = () => console.log('[KAI Widget] Marked.js loaded');
            document.head.appendChild(script);
        }

        // Get configuration from script attributes
        // Token precedence:
        // 1) data-api-key (explicit embed config)
        // 2) localStorage auth_access_token (KAI-Fusion frontend session)
        const authToken = localStorage.getItem("auth_access_token");

        const script = document.currentScript || getCurrentScript();
        if (script) {
            const dataset = script.dataset || {};
            config.targetUrl = dataset.targetUrl || 'http://localhost:23056';
            config.apiKey = dataset.apiKey || authToken || '';
            config.workflowId = dataset.workflowId || '';
            config.position = dataset.position || 'right';
            config.color = dataset.color || '#2563eb';
            config.width = dataset.width || '500px';
            config.height = dataset.height || '600px';
            config.title = dataset.title || 'KAI-Fusion AI';
            config.icon = dataset.emoji ? { data: dataset.emoji, format: "emoji" } : dataset.iconUrl ? { data: dataset.iconUrl, format: 'url' } : { data: '💬', format: 'emoji' };

            // Log the dynamic src configuration for debugging
            console.log('[KAI Widget] Configuration loaded:', {
                targetUrl: config.targetUrl,
                workflowId: config.workflowId,
                scriptSrc: script.src,
                position: config.position
            });
        }

        // Generate session ID
        sessionId = crypto.randomUUID();

        // Create widget elements
        createWidget();

        // Expose global API
        window.KAIWidget = {
            show: showWidget,
            hide: hideWidget,
            toggle: toggleWidget,
            toggleFullscreen: toggleFullscreen,
            updateConfig: updateConfig,
            getConfig: () => ({ ...config }),
            copyToClipboard: copyToClipboard
        };

        console.log('[KAI Widget] Initialized successfully');
    }

    function getCurrentScript() {
        const scripts = document.getElementsByTagName('script');
        return scripts[scripts.length - 1];
    }

    function createWidget() {
        // Create widget button
        elements.button = createElement('button', {
            id: 'kai-widget-button',
            className: 'kai-widget-button',
            innerHTML: config.icon.format === 'emoji' ? config.icon.data : `<img src="${config.icon.data}" alt="KAI Widget Icon" />`,
            onclick: toggleWidget
        });

        // Create overlay
        elements.overlay = createElement('div', {
            id: 'kai-widget-overlay',
            className: 'kai-widget-overlay',
            onclick: hideWidget
        });

        // Create widget container
        elements.container = createElement('div', {
            id: 'kai-widget-container',
            className: 'kai-widget-container'
        });

        // Create chat interface
        elements.chat = createChatInterface();
        elements.container.appendChild(elements.chat);

        // Apply styles
        applyStyles();

        // Add to DOM
        document.body.appendChild(elements.button);
        document.body.appendChild(elements.overlay);
        document.body.appendChild(elements.container);
    }

    function createElement(tag, props) {
        const element = document.createElement(tag);
        Object.keys(props).forEach(key => {
            if (key === 'onclick') {
                element.addEventListener('click', props[key]);
            } else {
                element[key] = props[key];
            }
        });
        return element;
    }

    function createChatInterface() {
        const chat = createElement('div', {
            className: 'kai-chat-interface',
            innerHTML: `
                <div class="kai-chat-header">
                    <div class="kai-chat-title">
                        <span class="kai-chat-icon">🤖</span>
                        ${config.title || 'KAI-Fusion AI'}
                    </div>
                    <div class="kai-chat-controls">
                        <button class="kai-chat-fullscreen" onclick="window.KAIWidget.toggleFullscreen()" title="Tam Ekran">⛶</button>
                        <button class="kai-chat-close" onclick="window.KAIWidget.hide()" title="Kapat">×</button>
                    </div>
                </div>
                <div class="kai-chat-messages" id="kai-chat-messages">
                    <div class="kai-welcome-message">
                        <div class="kai-message kai-message-bot">
                            <div class="kai-message-content">
                                Hello! I'm your AI assistant. How can I help you today?
                            </div>
                        </div>
                    </div>
                </div>
                <div class="kai-chat-input">
                    <input type="text" id="kai-message-input" placeholder="Type your message..." />
                    <button id="kai-send-button">
                        <span class="kai-send-icon">➤</span>
                    </button>
                </div>
                <div class="kai-chat-status">
                    <div class="kai-status-indicator" id="kai-status-indicator">
                        <span class="kai-status-dot"></span>
                        <span class="kai-status-text">Ready</span>
                    </div>
                </div>
            `
        });

        // Add event listeners
        setTimeout(() => {
            const messageInput = document.getElementById('kai-message-input');
            const sendButton = document.getElementById('kai-send-button');

            if (messageInput && sendButton) {
                messageInput.addEventListener('keypress', (e) => {
                    if (e.key === 'Enter') sendMessage();
                });
                sendButton.addEventListener('click', sendMessage);
            }
        }, 0);

        return chat;
    }

    function copyToClipboard(btn) {
        if (!btn) return;
        const wrapper = btn.closest('.kai-code-block');
        if (!wrapper) return;

        const codeTextarea = wrapper.querySelector('.kai-hidden-code');
        if (!codeTextarea) return;

        const code = codeTextarea.value;

        navigator.clipboard.writeText(code).then(() => {
            const originalHTML = btn.innerHTML;
            btn.innerHTML = `<span class="kai-copy-icon">✓</span><span class="kai-copy-text">Copied!</span>`;
            setTimeout(() => {
                btn.innerHTML = originalHTML;
            }, 2000);
        }).catch(err => {
            console.error('Failed to copy:', err);
        });
    }

    function processMessageContent(container) {
        if (!container) return;

        // Wrap tables
        const tables = container.querySelectorAll('table');
        tables.forEach(table => {
            if (!table.parentElement.classList.contains('kai-table-wrapper')) {
                const wrapper = document.createElement('div');
                wrapper.className = 'kai-table-wrapper';
                table.parentNode.insertBefore(wrapper, table);
                wrapper.appendChild(table);
            }
        });

        // Process code blocks
        const pres = container.querySelectorAll('pre');
        pres.forEach(pre => {
            if (pre.closest('.kai-code-block')) return; // Already processed

            const code = pre.querySelector('code');
            if (!code) return;

            const langClass = Array.from(code.classList).find(c => c.startsWith('language-'));
            const language = langClass ? langClass.replace('language-', '') : 'plaintext';
            const codeContent = code.textContent;

            const wrapper = document.createElement('div');
            wrapper.className = 'kai-code-block';

            // Header
            const header = document.createElement('div');
            header.className = 'kai-code-header';
            header.innerHTML = `
                <div class="kai-code-lang">
                    <span class="kai-code-icon">💻</span>
                    <span>${language}</span>
                </div>
                <button class="kai-copy-btn" onclick="window.KAIWidget.copyToClipboard(this)">
                    <span class="kai-copy-icon"></span>
                    <span class="kai-copy-text">Copy</span>
                </button>
                <textarea class="kai-hidden-code" style="display:none">${codeContent}</textarea>
            `;

            // Content
            const content = document.createElement('div');
            content.className = 'kai-code-content';

            const newPre = pre.cloneNode(true);
            newPre.style.margin = '0';
            newPre.style.borderRadius = '0';
            content.appendChild(newPre);

            wrapper.appendChild(header);
            wrapper.appendChild(content);

            pre.parentNode.replaceChild(wrapper, pre);
        });

        // Links target _blank
        const links = container.querySelectorAll('a');
        links.forEach(link => {
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
        });
    }

    function applyStyles() {
        const styles = `
            .kai-widget-button {
                display: flex;
                justify-content: center;
                align-items: center;
                position: fixed;
                bottom: 20px;
                ${config.position}: 20px;
                width: 60px;
                height: 60px;
                border-radius: 50%;
                background: ${config.color};
                color: white;
                border: none;
                font-size: 24px;
                cursor: pointer;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                z-index: 9999;
                transition: all 0.3s ease;
            }
            
            .kai-widget-button:hover {
                transform: scale(1.1);
                box-shadow: 0 6px 16px rgba(0,0,0,0.2);
            }

            .kai-widget-button img {
            background-color: white;
                width: 34px;
                height: 34px;
                object-fit: contain;
            }
            
            .kai-widget-overlay {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.5);
                backdrop-filter: blur(2px);
                z-index: 9997;
                display: none;
                transition: opacity 0.3s ease;
            }
            
            .kai-widget-container {
                position: fixed;
                bottom: 100px;
                ${config.position}: 20px;
                width: ${config.width};
                height: ${config.height};
                background: white;
                border-radius: 16px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.12);
                z-index: 9998;
                display: none;
                overflow: hidden;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
                transition: all 0.3s ease;
            }
            
            .kai-chat-interface {
                height: 100%;
                display: flex;
                flex-direction: column;
            }
            
            .kai-chat-header {
                background: ${config.color};
                color: white;
                padding: 16px 20px;
                font-size: 16px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            
            .kai-chat-title {
                display: flex;
                align-items: center;
                gap: 8px;
                font-weight: 600;
            }

            .kai-chat-controls {
                display: flex;
                align-items: center;
                gap: 8px;
            }

            .kai-chat-fullscreen {
                background: none;
                border: none;
                color: white;
                font-size: 18px;
                cursor: pointer;
                width: 32px;
                height: 32px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: background 0.2s;
            }

            .kai-chat-fullscreen:hover {
                background: rgba(255,255,255,0.1);
            }
            
            .kai-widget-container.kai-fullscreen {
                width: 800px !important;
                max-width: 90vw !important;
                height: 600px !important;
                max-height: 85vh !important;
                top: 50% !important;
                left: 50% !important;
                right: auto !important;
                bottom: auto !important;
                transform: translate(-50%, -50%) !important;
                border-radius: 16px !important;
                z-index: 9999 !important;
                box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04) !important;
            }
            
            .kai-chat-close {
                background: none;
                border: none;
                color: white;
                font-size: 24px;
                cursor: pointer;
                width: 32px;
                height: 32px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            
            .kai-chat-close:hover {
                background: rgba(255,255,255,0.1);
            }
            
            .kai-chat-messages {
                flex: 1;
                overflow-y: auto;
                padding: 20px;
                display: flex;
                flex-direction: column;
                gap: 16px;
            }
            
            .kai-message {
                display: flex;
                max-width: 85%;
            }
            
            .kai-message-bot {
                align-self: flex-start;
            }
            
            .kai-message-user {
                align-self: flex-end;
            }
            
            .kai-message-content {
                padding: 12px 16px;
                border-radius: 18px;
                font-size: 14px;
                width: 100%;
                line-height: 1.6;
            }
            
            .kai-message-bot .kai-message-content {
                background: #f1f3f5;
                color: #333;
            }
            
            .kai-message-user .kai-message-content {
                background: ${config.color};
                color: white;
            }

            /* Markdown Styles from ChatBubble */
            .kai-message-content p {
                margin: 0;
            }
            
            .kai-message-content h1 {
                font-size: 1.25rem;
                font-weight: 700;
                margin-bottom: 1rem;
                padding-bottom: 0.75rem;
                border-bottom: 2px solid;
                border-image: linear-gradient(to right, #3b82f6, #9333ea) 1;
                color: #111827;
                background: linear-gradient(to right, #2563eb, #9333ea);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }

            .kai-message-content h2 {
                font-size: 1.125rem;
                font-weight: 700;
                margin-top: 1.5rem;
                margin-bottom: 0.75rem;
                color: #111827;
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }
            
            .kai-message-content h2::before {
                content: '';
                display: block;
                width: 0.25rem;
                height: 1.5rem;
                background: linear-gradient(to bottom, #3b82f6, #9333ea);
                border-radius: 9999px;
            }

            .kai-message-content h3 {
                font-size: 1rem;
                font-weight: 600;
                margin-top: 1.25rem;
                margin-bottom: 0.75rem;
                color: #1f2937;
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }

            .kai-message-content h3::before {
                content: '';
                display: block;
                width: 0.25rem;
                height: 1.25rem;
                background: linear-gradient(to bottom, #60a5fa, #a855f7);
                border-radius: 9999px;
            }

            .kai-message-content ul, .kai-message-content ol {
                margin-bottom: 1rem;
                padding-left: 0;
                list-style: none;
            }

            .kai-message-content li {
                position: relative;
                padding-left: 1.5rem;
                margin-bottom: 0.5rem;
            }

            .kai-message-content ul li::before {
                content: '';
                position: absolute;
                left: 0.5rem;
                top: 0.6em;
                width: 0.375rem;
                height: 0.375rem;
                background: linear-gradient(to right, #3b82f6, #9333ea);
                border-radius: 50%;
            }

            .kai-message-content ol {
                counter-reset: kai-counter;
            }

            .kai-message-content ol li {
                padding-left: 2rem;
            }


            .kai-message-content blockquote {
                position: relative;
                margin: 1rem 0;
                padding: 1rem 1.5rem;
                background: linear-gradient(to right, #eff6ff, #eef2ff);
                border-left: 4px solid #bfdbfe;
                border-radius: 0.75rem;
                color: #374151;
                font-style: italic;
            }

            .kai-code-block {
                margin: 1rem 0;
                border-radius: 0.75rem;
                overflow: hidden;
                border: 1px solid #e5e7eb;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            }

            .kai-code-block code {
                display: flex;
                width: 100%;
                font-size: x-small;
            }

            .kai-code-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 0.5rem 1rem;
                background: linear-gradient(to right, #1f2937, #111827);
                color: #f3f4f6;
                border-bottom: 1px solid #374151;
                font-size: 14px !important;
            }

            .kai-code-lang {
                display: flex;
                align-items: center;
                gap: 0.5rem;
                text-transform: capitalize;
                font-weight: 500;
            }

            .kai-copy-btn {
                display: flex;
                align-items: center;
                gap: 0.25rem;
                padding: 0.25rem 0.75rem;
                background: #374151;
                border: none;
                border-radius: 0.375rem;
                color: #e5e7eb;
                cursor: pointer;
                font-size: 12px !important;
                transition: all 0.2s;
            }

            .kai-copy-btn:hover {
                background: #4b5563;
            }

            .kai-code-content {
                background: #030712;
                padding: 1rem;
                overflow-x: auto;
                font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
                font-size: 0.875rem !important;
                line-height: 1.5;
                color: #e5e7eb;
            }

            .kai-code-content pre {
                margin: 0;
            }

            .kai-message-content :not(pre) > code {
                background-color: #eff6ff;
                color: #1d4ed8;
                padding: 0.2em 0.4em;
                border-radius: 0.375rem;
                font-size: 0.875em;
                border: 1px solid #bfdbfe;
                font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            }

            .kai-table-wrapper {
                overflow-x: auto;
                margin: 1rem 0;
                border-radius: 0.75rem;
                border: 1px solid #e5e7eb;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            }

            .kai-message-content table {
                width: 100%;
                border-collapse: collapse;
                font-size: 0.875rem;
            }

            .kai-message-content th {
                background: #f9fafb;
                padding: 0.75rem 1rem;
                text-align: left;
                font-weight: 600;
                color: #111827;
                border-bottom: 1px solid #e5e7eb;
            }

            .kai-message-content td {
                padding: 0.75rem 1rem;
                color: #374151;
                border-bottom: 1px solid #f3f4f6;
            }

            .kai-message-content tr:last-child td {
                border-bottom: none;
            }

            .kai-message-content tr:hover td {
                background-color: #f9fafb;
            }

            .kai-message-content a {
                color: #2563eb;
                text-decoration: underline;
                text-underline-offset: 2px;
            }
            
            .kai-message-content a:hover {
                color: #1d4ed8;
            }
            
            .kai-chat-input {
                border-top: 1px solid #e9ecef;
                padding: 16px 20px;
                display: flex;
                gap: 12px;
                align-items: center;
            }
            
            #kai-message-input {
                flex: 1;
                border: 1px solid #e9ecef;
                border-radius: 24px;
                padding: 10px 16px;
                font-size: 14px;
                outline: none;
                transition: border-color 0.2s;
            }
            
            #kai-message-input:focus {
                border-color: ${config.color};
            }
            
            #kai-send-button {
                width: 40px;
                height: 40px;
                border-radius: 50%;
                background: ${config.color};
                color: white;
                border: none;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 24px;
                transition: transform 0.2s;
            }
            
            #kai-send-button:hover {
                transform: scale(1.1);
            }
            
            #kai-send-button:disabled {
                opacity: 0.5;
                cursor: not-allowed;
                transform: none;
            }
            
            .kai-chat-status {
                border-top: 1px solid #e9ecef;
                padding: 8px 20px;
                background: #f8f9fa;
            }
            
            .kai-status-indicator {
                display: flex;
                align-items: center;
                gap: 6px;
                font-size: 12px;
                color: #6c757d;
            }
            
            .kai-status-dot {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background: #28a745;
            }
            
            .kai-status-dot.connecting {
                background: #ffc107;
                animation: kai-pulse 2s infinite;
            }
            
            .kai-status-dot.error {
                background: #dc3545;
            }
            
            @keyframes kai-pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }
            
            .kai-typing-indicator {
                display: flex;
                align-items: center;
                gap: 4px;
                padding: 8px 16px;
                background: #f1f3f5;
                border-radius: 18px;
                font-size: 14px;
                color: #6c757d;
            }
            
            .kai-typing-dots {
                display: flex;
                gap: 2px;
            }
            
            .kai-typing-dots span {
                width: 4px;
                height: 4px;
                border-radius: 50%;
                background: #6c757d;
                animation: kai-typing 1.4s infinite;
            }
            
            .kai-typing-dots span:nth-child(2) {
                animation-delay: 0.2s;
            }
            
            .kai-typing-dots span:nth-child(3) {
                animation-delay: 0.4s;
            }
            
            @keyframes kai-typing {
                0%, 60%, 100% { transform: translateY(0); }
                30% { transform: translateY(-8px); }
            }
        `;

        // Add styles to page
        const styleSheet = document.createElement('style');
        styleSheet.textContent = styles;
        document.head.appendChild(styleSheet);
    }

    function showWidget() {
        elements.container.style.display = 'block';
        isOpen = true;
    }

    function hideWidget() {
        elements.container.style.display = 'none';
        if (elements.overlay) elements.overlay.style.display = 'none';

        // Reset fullscreen state when closing
        if (elements.container.classList.contains('kai-fullscreen')) {
            toggleFullscreen();
        }

        isOpen = false;
    }

    function toggleWidget() {
        if (isOpen) {
            hideWidget();
        } else {
            showWidget();
        }
    }

    function toggleFullscreen() {
        elements.container.classList.toggle('kai-fullscreen');
        const isFullscreen = elements.container.classList.contains('kai-fullscreen');
        const btn = elements.container.querySelector('.kai-chat-fullscreen');

        if (isFullscreen) {
            btn.innerHTML = '↙';
            btn.title = 'Küçült';
            if (elements.overlay) elements.overlay.style.display = 'block';
        } else {
            btn.innerHTML = '⛶';
            btn.title = 'Tam Ekran';
            if (elements.overlay) elements.overlay.style.display = 'none';
        }
    }

    function updateConfig(newConfig) {
        Object.assign(config, newConfig);
        console.log('[KAI Widget] Configuration updated:', config);
    }

    function setStatus(message, type = 'ready') {
        const statusIndicator = document.getElementById('kai-status-indicator');
        if (statusIndicator) {
            const dot = statusIndicator.querySelector('.kai-status-dot');
            const text = statusIndicator.querySelector('.kai-status-text');

            if (dot && text) {
                dot.className = `kai-status-dot ${type}`;
                text.textContent = message;
            }
        }
    }

    function addMessage(content, isUser = false) {
        const messagesContainer = document.getElementById('kai-chat-messages');
        if (!messagesContainer) return;

        // Use marked to parse content if available, otherwise fallback to raw text
        const parsedContent = (window.marked && typeof content === 'string')
            ? window.marked.parse(content)
            : content;

        const messageDiv = createElement('div', {
            className: `kai-message ${isUser ? 'kai-message-user' : 'kai-message-bot'}`,
            innerHTML: `<div class="kai-message-content">${parsedContent}</div>`
        });

        if (!isUser) {
            processMessageContent(messageDiv.querySelector('.kai-message-content'));
        }

        messagesContainer.appendChild(messageDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        return messageDiv;
    }

    function showTypingIndicator() {
        const messagesContainer = document.getElementById('kai-chat-messages');
        if (!messagesContainer) return;

        const typingDiv = createElement('div', {
            id: 'kai-typing-indicator',
            className: 'kai-message kai-message-bot',
            innerHTML: `
                <div class="kai-typing-indicator">
                    Typing
                    <div class="kai-typing-dots">
                        <span></span>
                        <span></span>
                        <span></span>
                    </div>
                </div>
            `
        });

        messagesContainer.appendChild(typingDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    function removeTypingIndicator() {
        const typingIndicator = document.getElementById('kai-typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    }

    async function sendMessage() {
        const messageInput = document.getElementById('kai-message-input');
        const sendButton = document.getElementById('kai-send-button');

        if (!messageInput || !messageInput.value.trim()) return;

        const message = messageInput.value.trim();
        messageInput.value = '';
        sendButton.disabled = true;

        // Add user message
        addMessage(message, true);

        // Show typing indicator
        showTypingIndicator();
        setStatus('Thinking...', 'connecting');

        let botMessageContentDiv = null;

        try {
            const response = await sendToAPI(message, (text) => {
                // Callback for streaming updates
                if (!botMessageContentDiv) {
                    removeTypingIndicator();
                    const msgDiv = addMessage(text, false);
                    if (msgDiv) {
                        botMessageContentDiv = msgDiv.querySelector('.kai-message-content');
                    }
                } else if (botMessageContentDiv) {
                    // Update existing message content with markdown parsing
                    botMessageContentDiv.innerHTML = window.marked ? window.marked.parse(text) : text;
                    processMessageContent(botMessageContentDiv);
                    const messagesContainer = document.getElementById('kai-chat-messages');
                    if (messagesContainer) {
                        messagesContainer.scrollTop = messagesContainer.scrollHeight;
                    }
                }
            });

            // If callback was never called (e.g. non-streaming fallback or fast response), ensure message is added
            if (!botMessageContentDiv) {
                removeTypingIndicator();
                addMessage(response);
            }

            setStatus('Ready', 'ready');
        } catch (error) {
            console.error('[KAI Widget] API Error:', error);
            removeTypingIndicator();

            if (error.name === 'AbortError') {
                addMessage('Response timed out. Please try again.', false);
            } else {
                addMessage('Sorry, I encountered an error. Please try again.', false);
            }

            setStatus('Error', 'error');
        } finally {
            removeTypingIndicator();
            sendButton.disabled = false;
        }
    }

    async function sendToAPI(message, onProgress) {
        const headers = {
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream'
        };

        if (config.apiKey) {
            headers['Authorization'] = `Bearer ${config.apiKey}`;
            headers['X-API-Key'] = config.apiKey;
        }

        // Use only the working endpoint
        const apiStart = window.VITE_API_START || 'api';
        const apiVersionOnly = window.VITE_API_VERSION_ONLY || 'v1';
        const url = config.targetUrl + '/' + apiStart + '/' + apiVersionOnly + '/workflows/execute';
        const payload = {
            input_text: message,
            session_id: sessionId,
            chatflow_id: sessionId,
            workflow_id: config.workflowId
        };

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 60000); // 60s timeout

        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify(payload),
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let fullText = '';

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6).trim();
                        if (data === '[DONE]' || !data) continue;

                        try {
                            const parsed = JSON.parse(data);
                            let newContent = '';

                            // Handle different event types from backend
                            if (parsed.type === 'token' && parsed.content) {
                                newContent = parsed.content;
                            } else if (parsed.type === 'output' && parsed.output) {
                                newContent = parsed.output;
                            } else if (parsed.type === 'complete' && parsed.result) {
                                if (typeof parsed.result === 'string' && !fullText) {
                                    newContent = parsed.result;
                                }
                            }

                            if (newContent) {
                                fullText += newContent;
                                if (onProgress) {
                                    onProgress(fullText);
                                }
                            }
                        } catch (e) {
                            console.warn('Error parsing stream data:', e);
                        }
                    }
                }
            }

            return fullText || 'Yanıt alınamadı.';

        } catch (error) {
            console.error('Stream error:', error);
            throw error;
        }
    }

    function extractResponse(data) {
        // Try different response formats
        if (data.response) return data.response;
        if (data.result && data.result.response) return data.result.response;
        if (data.message) return data.message;
        if (data.text) return data.text;
        if (data.content) return data.content;

        // Fallback
        return typeof data === 'string' ? data : 'I received your message but couldn\'t parse the response.';
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();