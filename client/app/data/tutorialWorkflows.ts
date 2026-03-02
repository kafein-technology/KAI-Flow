export interface TutorialStep {
  id: string;
  title: string;
  description: string;
  instructions: string[];
  tips: string[];
  expectedOutcome: string;
  completed: boolean;
}

export interface TutorialWorkflow {
  id: string;
  name: string;
  description: string;
  difficulty: 'Beginner' | 'Intermediate' | 'Advanced';
  category: string;
  estimatedTime: string;
  steps: TutorialStep[];
  prerequisites: string[];
  tags: string[];
}

export const TUTORIAL_WORKFLOWS: TutorialWorkflow[] = [
  {
    id: 'simple-chatbot',
    name: 'Simple AI Chatbot',
    description: 'Create a comprehensive AI chatbot with agent coordination, LLM integration, memory, and tools',
    difficulty: 'Beginner',
    category: 'AI & Chatbots',
    estimatedTime: '15-20 minutes',
    tags: ['chatbot', 'openai', 'llm', 'beginner'],
    prerequisites: ['OpenAI API key'],
    steps: [
      {
        id: 'step-1',
        title: 'Set Up Base Workflow',
        description: 'Create the core workflow structure with Start, Agent, and End nodes',
        instructions: [
          'Drag a Start node from the sidebar onto the canvas',
          'Drag an Agent node and place it to the right of Start',
          'Drag an End node and place it to the right of Agent',
          'Connect Start output → Agent input → End input by dragging between handles'
        ],
        tips: [
          'Every workflow needs exactly one Start node as the entry point',
          'The Agent node is the brain of your chatbot — it coordinates LLM, memory, and tools',
          'You can zoom in/out with the scroll wheel and pan by dragging the canvas background'
        ],
        expectedOutcome: 'Three nodes on the canvas connected in a chain: Start → Agent → End',
        completed: false
      },
      {
        id: 'step-2',
        title: 'Add and Configure LLM',
        description: 'Connect a language model to power your agent\'s responses',
        instructions: [
          'Drag an OpenAI GPT node onto the canvas above the Agent node',
          'Click the OpenAI GPT node to open its settings',
          'Enter your OpenAI API key and select a model (e.g. gpt-4o-mini)',
          'Connect the OpenAI GPT output to the Agent node\'s LLM handle'
        ],
        tips: [
          'gpt-4o-mini offers the best balance of speed, quality, and cost for chatbots',
          'Set temperature to 0.7 for natural conversation — lower values give more deterministic outputs',
          'You can also use an OpenAI Compatible node if you prefer a different LLM provider'
        ],
        expectedOutcome: 'OpenAI GPT node configured with your API key and connected to the Agent',
        completed: false
      },
      {
        id: 'step-3',
        title: 'Add Conversation Memory',
        description: 'Enable your chatbot to remember previous messages in the conversation',
        instructions: [
          'Drag a Conversation Memory (Windowed) node below the Agent node',
          'Click the node to configure the window size (default works for most cases)',
          'Connect its output to the Agent node\'s memory handle'
        ],
        tips: [
          'Windowed memory keeps the last N messages, preventing token limits from being exceeded',
          'For simple Q&A chatbots, Buffer Memory (Persistent) is an alternative that stores everything',
          'Memory is what makes your chatbot feel conversational instead of stateless'
        ],
        expectedOutcome: 'Memory node connected — the agent can now reference previous messages',
        completed: false
      },
      {
        id: 'step-4',
        title: 'Add a Tool',
        description: 'Give your agent the ability to search the web or call external APIs',
        instructions: [
          'Drag a Tavily Web Search node (or HTTP Client) to the left of the Agent node',
          'Click the node and configure your API key and search parameters',
          'Connect the tool\'s output to the Agent node\'s tools handle',
          'Optionally write a system prompt in the Agent node to guide when the tool should be used'
        ],
        tips: [
          'Tavily Web Search lets the agent look up real-time information from the internet',
          'HTTP Client is more flexible — use it to call any REST API',
          'You can connect multiple tools to the same Agent; it will decide which one to use based on the query'
        ],
        expectedOutcome: 'Tool node connected — the agent can now access external data when needed',
        completed: false
      },
      {
        id: 'step-5',
        title: 'Test Your Chatbot',
        description: 'Run the workflow and have a conversation with your AI chatbot',
        instructions: [
          'Click the Execute button in the top toolbar to start the workflow',
          'Type a message in the chat panel and send it',
          'Ask a follow-up question to verify memory is working',
          'Ask something that requires web search to verify tool usage'
        ],
        tips: [
          'Check the execution logs panel to see which nodes ran and in what order',
          'If the agent doesn\'t use a tool, try being more specific (e.g. "What is today\'s weather in Istanbul?")',
          'You can re-run the workflow after making changes without rebuilding everything'
        ],
        expectedOutcome: 'Your chatbot responds intelligently, remembers context, and uses tools when needed',
        completed: false
      }
    ]
  },
  {
    id: 'rag-system',
    name: 'RAG Document Q&A System',
    description: 'Build a Retrieval-Augmented Generation system for document analysis',
    difficulty: 'Intermediate',
    category: 'Document Processing',
    estimatedTime: '15-20 minutes',
    tags: ['rag', 'documents', 'vector', 'intermediate'],
    prerequisites: ['OpenAI API key', 'PostgreSQL database'],
    steps: [
      {
        id: 'step-1',
        title: 'Load Your Documents',
        description: 'Set up a Document Loader to ingest files from Google Drive',
        instructions: [
          'Drag a Document Loader node onto the canvas',
          'Click it to open settings and select your authentication method (Service Account or OAuth2)',
          'Paste your Google Drive file or folder links into the Drive Links field',
          'Choose which formats to process (PDF, DOCX, TXT, JSON, CSV) using the checkboxes'
        ],
        tips: [
          'Service Account auth is easier for automated workflows — just paste the JSON credentials',
          'You can load entire Google Drive folders at once, not just individual files',
          'Set Min Content Length to 100+ to filter out empty or boilerplate pages'
        ],
        expectedOutcome: 'Document Loader configured and ready to pull files from Google Drive',
        completed: false
      },
      {
        id: 'step-2',
        title: 'Split Documents into Chunks',
        description: 'Break large documents into smaller pieces optimized for AI retrieval',
        instructions: [
          'Drag a Document Chunk Splitter node to the right of the Document Loader',
          'Connect Document Loader\'s output → Chunk Splitter\'s documents input',
          'Set Chunk Size to 1000 and Overlap to 200 as a good starting point'
        ],
        tips: [
          'Overlap ensures context isn\'t lost at chunk boundaries — 200 chars is a solid default',
          'Smaller chunks (500-800) improve precision, larger chunks (1000-1500) keep more context',
          'The default Recursive Character strategy works well for most document types'
        ],
        expectedOutcome: 'Documents are split into overlapping chunks ready for embedding',
        completed: false
      },
      {
        id: 'step-3',
        title: 'Set Up Embeddings and Vector Store',
        description: 'Create vector embeddings and store them in PostgreSQL with pgvector',
        instructions: [
          'Drag an OpenAI Embeddings Provider node below the canvas area',
          'Select your OpenAI credential and choose text-embedding-3-small as the model',
          'Drag a Vector Store Orchestrator node to the right of the Chunk Splitter',
          'Connect Chunk Splitter output → Vector Store documents input',
          'Connect OpenAI Embeddings Provider output → Vector Store embedder input',
          'Set a Collection Name (e.g. "my_knowledge_base") and select your PostgreSQL credential'
        ],
        tips: [
          'text-embedding-3-small (1536D) is the best cost/quality balance for most use cases',
          'Collection Name keeps your datasets isolated — use different names for different projects',
          'The orchestrator auto-creates HNSW indexes for fast similarity search'
        ],
        expectedOutcome: 'Embeddings provider and vector store connected — documents will be vectorized and stored',
        completed: false
      },
      {
        id: 'step-4',
        title: 'Create the Retriever Tool',
        description: 'Build an agent-ready search tool that queries your vector database',
        instructions: [
          'Drag a Retriever Provider node onto the canvas',
          'Select the same PostgreSQL credential used for the Vector Store',
          'Enter the same Collection Name you used in the Vector Store',
          'Drag an OpenAI Embeddings Provider node and connect it to the Retriever\'s embedder input',
          'Adjust Search K (number of results) and Score Threshold as needed'
        ],
        tips: [
          'Search K = 6 is a good default — increase it for broader searches, decrease for precision',
          'Setting a Score Threshold (e.g. 0.3) filters out low-relevance results automatically',
          'MMR search type reduces redundancy when retrieved chunks are too similar'
        ],
        expectedOutcome: 'Retriever tool configured and ready to search your knowledge base',
        completed: false
      },
      {
        id: 'step-5',
        title: 'Build the Q&A Agent',
        description: 'Connect an AI agent that uses the retriever to answer questions from your documents',
        instructions: [
          'Drag Start, Agent, and End nodes onto the canvas and connect them in order',
          'Connect the Retriever Provider\'s tool output → Agent\'s tools handle',
          'Drag an OpenAI GPT node and connect it to the Agent\'s LLM handle',
          'Write a system prompt in the Agent that instructs it to answer using retrieved documents only'
        ],
        tips: [
          'A good system prompt: "Answer questions based only on the retrieved documents. If the answer isn\'t in the documents, say so."',
          'Adding Conversation Memory (Windowed) lets users ask follow-up questions naturally',
          'The agent automatically decides when to use the retriever tool based on the query'
        ],
        expectedOutcome: 'Complete RAG pipeline: documents → chunks → embeddings → retriever → agent',
        completed: false
      },
      {
        id: 'step-6',
        title: 'Test Your RAG System',
        description: 'Run the full pipeline and validate document-grounded answers',
        instructions: [
          'First, execute the ingestion workflow (Document Loader → Splitter → Vector Store) to store your documents',
          'Then execute the Q&A workflow with a question that requires document knowledge',
          'Ask a follow-up question to test if context is maintained',
          'Try a question whose answer is NOT in your documents to verify the agent admits when it doesn\'t know'
        ],
        tips: [
          'Check the execution logs to see which chunks were retrieved — this helps debug relevance issues',
          'If answers are off, try adjusting chunk size or increasing Search K in the Retriever',
          'You can re-ingest documents without losing previous data by keeping the same Collection Name'
        ],
        expectedOutcome: 'The agent answers questions accurately using information from your documents',
        completed: false
      }
    ]
  },
  {
    id: 'webhook-automation',
    name: 'Webhook Automation Workflow',
    description: 'Create automated workflows triggered by external webhooks',
    difficulty: 'Intermediate',
    category: 'Automation',
    estimatedTime: '10-15 minutes',
    tags: ['webhook', 'automation', 'api', 'intermediate'],
    prerequisites: ['External system that can send webhooks'],
    steps: [
      {
        id: 'step-1',
        title: 'Set Up the Webhook Trigger',
        description: 'Create a REST endpoint that external services can call to trigger your workflow',
        instructions: [
          'Drag a Webhook Trigger node onto the canvas (it replaces the Start node)',
          'Click the node and set a unique Path (e.g. "github-events") — this becomes your webhook URL',
          'Select the HTTP Method your external service will use (POST is most common)',
          'Optionally enable authentication under the Auth tab (Basic Auth or Header Auth)'
        ],
        tips: [
          'Your webhook URL will be: http://your-server/api/v1/webhook-test/{path} for testing',
          'Use Header Auth with a secret token for production webhooks — it is simpler than Basic Auth',
          'The node automatically parses JSON payloads and makes fields available as {{webhook_trigger.fieldname}}'
        ],
        expectedOutcome: 'Webhook endpoint created with a unique path and ready to receive external requests',
        completed: false
      },
      {
        id: 'step-2',
        title: 'Add an Agent for Processing',
        description: 'Use an AI agent to intelligently process incoming webhook data',
        instructions: [
          'Drag an Agent node to the right of the Webhook Trigger',
          'Connect Webhook Trigger output → Agent input',
          'Drag an OpenAI GPT node and connect it to the Agent\'s LLM handle',
          'Write a system prompt that tells the agent what to do with the webhook data (e.g. "Analyze the incoming GitHub event and summarize the changes")'
        ],
        tips: [
          'The agent receives the full webhook payload as input — no extra parsing needed',
          'Use gpt-4o-mini for webhook processing to keep costs low and response times fast',
          'You can reference specific webhook fields in the system prompt to guide the agent\'s behavior'
        ],
        expectedOutcome: 'Agent configured to analyze and process webhook payloads',
        completed: false
      },
      {
        id: 'step-3',
        title: 'Add External API Calls',
        description: 'Give the agent tools to call external services based on webhook data',
        instructions: [
          'Drag an HTTP Client node onto the canvas',
          'Click it and set the URL, HTTP Method, and Content Type for the target API',
          'Configure authentication (Bearer Token, Basic Auth, or API Key) in the Auth tab',
          'Connect the HTTP Client\'s tool output to the Agent\'s tools handle'
        ],
        tips: [
          'Enable Templates in the Advanced tab to use Jinja2 variables in URLs and request bodies',
          'The HTTP Client supports automatic retries (default 3) with configurable delay — great for unreliable APIs',
          'You can add multiple HTTP Client nodes as tools — the agent will decide which one to call'
        ],
        expectedOutcome: 'HTTP Client configured as an agent tool for making external API calls',
        completed: false
      },
      {
        id: 'step-4',
        title: 'Configure the Webhook Response',
        description: 'Send a custom HTTP response back to the service that triggered the webhook',
        instructions: [
          'Drag a Respond to Webhook node onto the canvas (it replaces the End node)',
          'Connect the Agent\'s output → Respond to Webhook input',
          'Set the HTTP Status Code (200 OK for success, 201 Created, etc.)',
          'Choose a Response Config: "All Incoming Items" to forward agent output, or "JSON" to write a custom body'
        ],
        tips: [
          'Use "All Incoming Items" to automatically return whatever the agent produced — no manual formatting needed',
          'The Response Body field supports templating with ${{variable}} for dynamic responses',
          'Set Content-Type to application/json for API integrations, or text/plain for simple acknowledgments'
        ],
        expectedOutcome: 'Webhook response configured to send meaningful data back to the caller',
        completed: false
      },
      {
        id: 'step-5',
        title: 'Add Error Handling',
        description: 'Make your webhook workflow robust with proper error handling',
        instructions: [
          'Review your Agent\'s system prompt and add instructions for handling unexpected or malformed data',
          'In the Respond to Webhook node, configure an appropriate error status code (400 or 500) for failure cases',
          'Add Custom Headers in the Advanced tab if the calling service expects specific response headers',
          'Consider adding Conversation Memory (Windowed) if webhook events need sequential context'
        ],
        tips: [
          'The Webhook Trigger automatically rejects requests with non-matching HTTP methods (405 error)',
          'Max Response Size defaults to 1024 KB — increase it in Advanced tab if you return large payloads',
          'Respond to Webhook supports JSON, plain text, and HTML content types for different use cases'
        ],
        expectedOutcome: 'Webhook workflow handles both success and error scenarios gracefully',
        completed: false
      },
      {
        id: 'step-6',
        title: 'Test Your Webhook',
        description: 'Send test requests and verify the full webhook pipeline',
        instructions: [
          'Copy your webhook URL from the Webhook Trigger node settings',
          'Use curl or Postman to send a POST request to http://localhost:8000/api/v1/webhook-test/your-path with a JSON body',
          'Check the execution logs in the canvas to see which nodes ran and what they produced',
          'Verify the HTTP response you received matches your Respond to Webhook configuration'
        ],
        tips: [
          'Use the webhook-test endpoint for development — it streams execution events to the UI in real-time',
          'Switch to the webhook (production) endpoint when deploying — it runs without UI streaming for better performance',
          'Test with malformed JSON and missing fields to make sure your error handling works'
        ],
        expectedOutcome: 'Webhook receives requests, processes them through the agent, and returns proper HTTP responses',
        completed: false
      }
    ]
  },
  {
    id: 'scheduled-reports',
    name: 'Scheduled Report Generation',
    description: 'Automate report generation and distribution on schedule',
    difficulty: 'Advanced',
    category: 'Automation',
    estimatedTime: '20-25 minutes',
    tags: ['scheduling', 'reports', 'automation', 'advanced'],
    prerequisites: ['Data sources for reports', 'Distribution channels'],
    steps: [
      {
        id: 'step-1',
        title: 'Set Up the Timer Trigger',
        description: 'Create a scheduled trigger that automatically runs your workflow at specified times',
        instructions: [
          'Drag a Timer Start node onto the canvas (it replaces the Start node)',
          'Choose a Schedule Type: Interval for regular runs, or Cron Expression for complex schedules',
          'For Interval, set the slider between 1 minute (60s) and 24 hours (86400s) — default is 1 hour',
          'For Cron, enter an expression like "0 9 * * 1-5" (weekdays at 9 AM) or "0 */6 * * *" (every 6 hours)'
        ],
        tips: [
          'Use Interval for simple "every X hours" schedules, and Cron for specific days/times like "Monday 9 AM"',
          'Set the Timezone dropdown to your team\'s timezone — default is UTC which may cause unexpected run times',
          'Add Trigger Data in the Data tab (JSON) to pass static config like report_type or recipient_list to the workflow'
        ],
        expectedOutcome: 'Timer trigger configured with your desired schedule and timezone',
        completed: false
      },
      {
        id: 'step-2',
        title: 'Fetch Report Data',
        description: 'Use HTTP Client nodes to pull data from your APIs and databases',
        instructions: [
          'Drag an HTTP Client node to the right of the Timer Start',
          'Connect Timer Start output → HTTP Client input',
          'Set the URL to your data source API (e.g. analytics endpoint, database REST API)',
          'Configure authentication in the Auth tab (Bearer Token for most APIs, API Key for services like Stripe)'
        ],
        tips: [
          'Add multiple HTTP Client nodes for different data sources — they can run in sequence through the agent',
          'Enable retry logic (default 3 retries) in the Advanced tab for APIs that occasionally timeout',
          'Use Jinja2 templates in the URL to include dynamic dates: /api/reports?date={{today}}'
        ],
        expectedOutcome: 'Data fetching configured to pull from your external data sources',
        completed: false
      },
      {
        id: 'step-3',
        title: 'Build the Report Agent',
        description: 'Use an AI agent to analyze data and generate formatted report content',
        instructions: [
          'Drag an Agent node onto the canvas',
          'Connect the HTTP Client tool(s) to the Agent\'s tools handle',
          'Drag an OpenAI GPT node and connect it to the Agent\'s LLM handle',
          'Write a system prompt like: "You are a report analyst. Fetch data from the available tools and generate a summary report with key metrics, trends, and actionable insights"'
        ],
        tips: [
          'Use gpt-4o for complex analysis, gpt-4o-mini for simple summary reports to save costs',
          'Include the desired output format in your prompt (markdown table, bullet points, or structured JSON)',
          'The agent can call multiple HTTP Client tools to gather data before generating the report'
        ],
        expectedOutcome: 'Agent configured to analyze fetched data and produce formatted reports',
        completed: false
      },
      {
        id: 'step-4',
        title: 'Set Up Report Distribution',
        description: 'Deliver the generated report via Slack, email, or other channels',
        instructions: [
          'Drag another HTTP Client node for distribution (e.g. Slack webhook, SendGrid API, Teams connector)',
          'Connect it as a second tool on the Agent\'s tools handle',
          'Configure the URL and Content Type for your distribution channel',
          'Update the agent\'s system prompt to include: "After generating the report, send it to the distribution channel"'
        ],
        tips: [
          'For Slack: use an Incoming Webhook URL with Content-Type application/json and a body like {"text": "report content"}',
          'You can add multiple distribution channels as separate HTTP Client tools — the agent will send to all of them',
          'Set different report formats per channel: markdown for Slack, HTML for email, JSON for dashboards'
        ],
        expectedOutcome: 'Distribution channels configured to deliver reports automatically',
        completed: false
      },
      {
        id: 'step-5',
        title: 'Configure Reliability Settings',
        description: 'Make your scheduled reports robust with retry logic and execution limits',
        instructions: [
          'In the Timer Start node, enable Retry on Failure in the Advanced tab for automatic retries',
          'Set Max Executions if you want the timer to stop after a certain number of runs (0 = unlimited)',
          'Set Timeout (default 300 seconds) to prevent hung workflows from running forever',
          'Use the Enable Timer checkbox to quickly pause/resume the schedule without deleting the node'
        ],
        tips: [
          'Retry uses exponential backoff (2s, 4s, 8s...) up to 60s — great for handling temporary API outages',
          'Set max_executions to a specific number for one-off report batches (e.g. 5 runs then stop)',
          'The Timer Start tracks execution_count and last_execution — useful for debugging missed runs'
        ],
        expectedOutcome: 'Report workflow configured with retry logic, timeouts, and execution limits',
        completed: false
      },
      {
        id: 'step-6',
        title: 'Test Your Scheduled Report',
        description: 'Run the workflow manually and verify the full report pipeline',
        instructions: [
          'Set Schedule Type to "Manual Trigger" temporarily for testing',
          'Click Execute to run the workflow and verify data fetching, report generation, and distribution',
          'Check the execution logs to verify each node produced the expected output',
          'Switch back to Interval or Cron once testing is complete'
        ],
        tips: [
          'Use the "One Time" schedule type to test at a specific future time before enabling recurring runs',
          'Monitor timer_stats output to see execution_count, last_execution, and next_execution times',
          'The Timer Start node supports start/stop/trigger_now controls — helpful for on-demand report runs'
        ],
        expectedOutcome: 'Scheduled report workflow tested and running automatically on your defined schedule',
        completed: false
      }
    ]
  }
];
