export interface ServiceField {
  name: string;
  label: string;
  type: 'text' | 'password' | 'textarea' | 'select' | 'checkbox' | 'model-combobox';
  helpText?: string;
  required: boolean;
  placeholder?: string;
  default?: any;
  options?: { value: string; label: string }[];
  description?: string;
  dependsOn?: {
    field: string;
    values: Array<string | boolean>;
  };
  validation?: {
    minLength?: number;
    maxLength?: number;
    pattern?: string;
    custom?: (value: any) => string | undefined;
  };
}

export interface ServiceDefinition {
  id: string;
  name: string;
  description: string;
  icon: string;
  category: 'ai' | 'database' | 'api' | 'storage' | 'cache' | 'webhook_auth' | 'other';
  fields: ServiceField[];
  color: string;
}

export const SERVICE_DEFINITIONS: ServiceDefinition[] = [
  {
    id: 'openai',
    name: 'OpenAI',
    description: 'OpenAI API credentials for GPT models, embeddings, and more',
    icon: 'openai.svg',
    category: 'ai',
    color: 'from-green-500 to-emerald-600',
    fields: [
      {
        name: 'api_key',
        label: 'API Key',
        type: 'password',
        required: true,
        placeholder: 'sk-...',
        description: 'Your OpenAI API key from https://platform.openai.com/api-keys',
        validation: {
          minLength: 20,
          custom: (value: string) => {
            if (value.length < 20) {
              return 'API key must be at least 20 characters long';
            }
            return undefined;
          }
        }
      },
      {
        name: 'model_name',
        label: 'Model',
        type: 'model-combobox',
        required: true,
        placeholder: 'Select or type a model',
        description: 'Models are loaded from OpenAI after you enter your API key. Use the arrow keys to move through the list.'
      }
    ]
  },
  {
    id: 'openai_compatible',
    name: 'OpenAI Compatible',
    description: 'Connect to any OpenAI-API compatible service like OpenRouter, vLLM, DeepSeek, or LM Studio.',
    icon: 'openai.svg',
    category: 'ai',
    color: 'from-gray-500 to-slate-600',
    fields: [
      {
        name: 'base_url',
        label: 'Base URL',
        type: 'text',
        required: true,
        placeholder: 'e.g. https://openrouter.ai/api/v1',
        description: 'The endpoint URL for the compatible service'
      },
      {
        name: 'api_key',
        label: 'API Key',
        type: 'password',
        required: false,
        placeholder: 'Optional for local endpoints (Ollama, LM Studio, etc.)',
        description: 'The authentication key for the compatible service (leave empty if not required)'
      },
      {
        name: 'model_name',
        label: 'Model',
        type: 'model-combobox',
        required: true,
        placeholder: 'Select or type a model',
        description: 'Models are loaded from your provider when Base URL is set. Use the arrow keys to move through the list.'
      },
      {
        name: 'skip_ssl_verify',
        label: 'Skip SSL Certificate Verification',
        type: 'checkbox',
        required: false,
        default: '',
        description: 'Enable this when connecting to servers with self-signed certificates (e.g. internal/local deployments)'
      }
    ]
  },
  {
    id: 'cohere',
    name: 'Cohere',
    description: 'Cohere AI API credentials for embeddings and reranking',
    icon: 'cohere.svg',
    category: 'ai',
    color: 'from-blue-500 to-cyan-600',
    fields: [
      {
        name: 'api_key',
        label: 'API Key',
        type: 'password',
        required: true,
        placeholder: '...',
        description: 'Your Cohere API key from https://dashboard.cohere.ai/',
        validation: {
          minLength: 20
        }
      }
    ]
  },
  {
    id: 'postgresql_vectorstore',
    name: 'Postgres',
    description: 'PostgreSQL database with vector extension for storing embeddings and retrieving',
    icon: 'postgresql_vectorstore.svg',
    category: 'database',
    color: 'from-indigo-500 to-purple-600',
    fields: [
      {
        name: 'host',
        label: 'Host',
        type: 'text',
        required: true,
        placeholder: 'localhost',
        description: 'PostgreSQL server hostname or IP address'
      },
      {
        name: 'port',
        label: 'Port',
        type: 'text',
        required: true,
        placeholder: '5432',
        description: 'PostgreSQL server port'
      },
      {
        name: 'database',
        label: 'Database Name',
        type: 'text',
        required: true,
        placeholder: 'vectorstore',
        description: 'Name of the database to connect to'
      },
      {
        name: 'username',
        label: 'Username',
        type: 'text',
        required: true,
        placeholder: 'postgres',
        description: 'Database username'
      },
      {
        name: 'password',
        label: 'Password',
        type: 'password',
        required: true,
        placeholder: '••••••••',
        description: 'Database password'
      }
    ]
  },

  {
    id: 'mongodb',
    name: 'MongoDB',
    description: 'Connect to MongoDB for bounded document read and write operations',
    icon: 'mongodb.svg',
    category: 'database',
    color: 'from-green-500 to-emerald-600',
    fields: [
      {
        name: 'configuration_type',
        label: 'Configuration Type',
        type: 'select',
        required: true,
        default: 'values',
        options: [
          { value: 'values', label: 'Separate Fields' },
          { value: 'connection_string', label: 'Connection String' }
        ],
        description: 'Enter the connection details field by field, or paste a connection string'
      },
      {
        name: 'connection_string',
        label: 'Connection String',
        type: 'password',
        required: false,
        placeholder: 'mongodb+srv://user:password@cluster.mongodb.net',
        description: 'Paste the string your provider gave you. Atlas uses the mongodb+srv scheme.',
        dependsOn: {
          field: 'configuration_type',
          values: ['connection_string']
        }
      },
      {
        name: 'host',
        label: 'Host',
        type: 'text',
        required: false,
        default: 'localhost',
        placeholder: 'localhost',
        description: 'MongoDB server hostname or IP address',
        dependsOn: {
          field: 'configuration_type',
          values: ['values']
        }
      },
      {
        name: 'port',
        label: 'Port',
        type: 'text',
        required: false,
        default: '27017',
        placeholder: '27017',
        description: 'MongoDB server port',
        dependsOn: {
          field: 'configuration_type',
          values: ['values']
        }
      },
      {
        name: 'username',
        label: 'Username',
        type: 'text',
        required: false,
        placeholder: 'mongo',
        description: 'Username for authentication',
        dependsOn: {
          field: 'configuration_type',
          values: ['values']
        }
      },
      {
        name: 'password',
        label: 'Password',
        type: 'password',
        required: false,
        placeholder: '••••••••',
        description: 'Password for authentication',
        dependsOn: {
          field: 'configuration_type',
          values: ['values']
        }
      },
      {
        name: 'auth_source',
        label: 'Authentication Database',
        type: 'text',
        required: false,
        placeholder: 'admin',
        description: 'Database that holds the user account. Usually admin.',
        dependsOn: {
          field: 'configuration_type',
          values: ['values']
        }
      },
      {
        name: 'database',
        label: 'Database Name',
        type: 'text',
        required: true,
        placeholder: 'mydatabase',
        description: 'Name of the database to work in'
      }
    ]
  },
  {
    id: 'tavily_search',
    name: 'Tavily Search',
    description: 'Tavily AI search API for web search capabilities',
    icon: 'tavily-nonbrand.svg',
    category: 'api',
    color: 'from-yellow-500 to-orange-600',
    fields: [
      {
        name: 'api_key',
        label: 'API Key',
        type: 'password',
        required: true,
        placeholder: 'tvly-...',
        description: 'Your Tavily API key from https://tavily.com/',
        validation: {
          minLength: 20
        }
      }
    ]
  },
  {
    id: 'sqlite',
    name: 'SQLite',
    description: 'Connect to a SQLite database file for workflow query and row operations',
    icon: 'sqlite.svg',
    category: 'database',
    color: 'from-sky-600 to-cyan-800',
    fields: [
      {
        name: 'database_path',
        label: 'Database Path',
        type: 'text',
        required: true,
        placeholder: '/data/app.sqlite',
        description: 'Absolute path to the SQLite database file on the backend host'
      },
      {
        name: 'timeout_ms',
        label: 'Connection Timeout (ms)',
        type: 'text',
        required: false,
        default: '30000',
        description: 'Maximum time SQLite waits for a locked database'
      },
      {
        name: 'read_only',
        label: 'Read Only',
        type: 'checkbox',
        required: false,
        default: false,
        description: 'Open the database in read-only mode as an additional safety guard'
      },
      {
        name: 'create_if_missing',
        label: 'Create if Missing',
        type: 'checkbox',
        required: false,
        default: false,
        description: 'Create the database file when it does not exist; the parent directory must already exist'
      }
    ]
  },
  {
    id: 'basic_auth',
    name: 'Basic Auth',
    description: 'Basic authentication credentials for webhook endpoints (username and password)',
    icon: 'globe.svg',
    category: 'webhook_auth',
    color: 'from-blue-500 to-indigo-600',
    fields: [
      {
        name: 'username',
        label: 'Username',
        type: 'text',
        required: true,
        placeholder: 'your_username',
        description: 'Username for Basic Authentication'
      },
      {
        name: 'password',
        label: 'Password',
        type: 'password',
        required: true,
        placeholder: '••••••••',
        description: 'Password for Basic Authentication'
      }
    ]
  },
  {
    id: 'header_auth',
    name: 'Header Auth',
    description: 'Header-based authentication credentials for webhook endpoints',
    icon: 'globe.svg',
    category: 'webhook_auth',
    color: 'from-purple-500 to-pink-600',
    fields: [
      {
        name: 'header_name',
        label: 'Header Name',
        type: 'text',
        required: true,
        placeholder: 'Authorization',
        default: 'Authorization',
        description: 'Name of the HTTP header to validate on incoming webhook requests'
      },
      {
        name: 'header_value',
        label: 'Header Value',
        type: 'password',
        required: true,
        placeholder: 'your-secret-header-value',
        description: 'The secret value that must match the custom header in webhook requests'
      }
    ]
  },
  {
    id: 'kafka',
    name: 'Kafka',
    description: 'Apache Kafka connection credentials for producing and consuming messages',
    icon: 'kafka-credentials.svg',
    category: 'api',
    color: 'from-green-500 to-emerald-600',
    fields: [
      {
        name: 'client_id',
        label: 'Client ID',
        type: 'text',
        required: true,
        placeholder: 'my-kafka-client',
        description: 'A unique identifier for this Kafka client'
      },
      {
        name: 'brokers',
        label: 'Brokers',
        type: 'text',
        required: true,
        placeholder: 'localhost:9092',
        description: 'Comma-separated list of Kafka broker addresses (e.g. host1:9092,host2:9092)'
      },
      {
        name: 'security_protocol',
        label: 'Security Protocol',
        type: 'select',
        required: false,
        default: 'PLAINTEXT',
        options: [
          { value: 'PLAINTEXT', label: 'PLAINTEXT' },
          { value: 'SASL_PLAINTEXT', label: 'SASL_PLAINTEXT' },
          { value: 'SASL_SSL', label: 'SASL_SSL' },
          { value: 'SSL', label: 'SSL' }
        ],
        description: 'Protocol used to communicate with brokers'
      },
      {
        name: 'sasl_mechanism',
        label: 'SASL Mechanism',
        type: 'select',
        required: false,
        default: 'PLAIN',
        options: [
          { value: 'PLAIN', label: 'PLAIN' },
          { value: 'SCRAM-SHA-256', label: 'SCRAM-SHA-256' },
          { value: 'SCRAM-SHA-512', label: 'SCRAM-SHA-512' }
        ],
        description: 'SASL mechanism to use for authentication',
        dependsOn: {
          field: 'security_protocol',
          values: ['SASL_PLAINTEXT', 'SASL_SSL']
        }
      },
      {
        name: 'sasl_username',
        label: 'SASL Username',
        type: 'text',
        required: false,
        placeholder: 'your-username',
        description: 'Username for SASL authentication',
        dependsOn: {
          field: 'security_protocol',
          values: ['SASL_PLAINTEXT', 'SASL_SSL']
        }
      },
      {
        name: 'sasl_password',
        label: 'SASL Password',
        type: 'password',
        required: false,
        placeholder: '••••••••',
        description: 'Password for SASL authentication',
        dependsOn: {
          field: 'security_protocol',
          values: ['SASL_PLAINTEXT', 'SASL_SSL']
        }
      },
      {
        name: 'ssl_cafile',
        label: 'SSL CA Certificate Path',
        type: 'text',
        required: false,
        placeholder: '/path/to/ca-cert.pem',
        description: 'File path to the CA certificate for SSL verification',
        dependsOn: {
          field: 'security_protocol',
          values: ['SSL', 'SASL_SSL']
        }
      }
    ]
  },
  {
    id: 'minio',
    name: 'MinIO / S3 Storage',
    description: 'S3-compatible object storage credentials for MinIO or AWS S3',
    icon: 'minio-credentials.svg',
    category: 'storage',
    color: 'from-blue-600 to-indigo-700',
    fields: [
      {
        name: 'endpoint',
        label: 'Endpoint URL',
        type: 'text',
        required: true,
        placeholder: 'e.g. localhost:9000 or s3.amazonaws.com',
        helpText: 'The host and port for your MinIO/S3 instance (without http/https)'
      },
      {
        name: 'access_key',
        label: 'Access Key',
        type: 'text',
        required: true,
        placeholder: 'e.g. minioadmin',
        helpText: 'The access key ID for your MinIO/S3 storage'
      },
      {
        name: 'secret_key',
        label: 'Secret Key',
        type: 'password',
        required: true,
        placeholder: 'e.g. minioadmin',
        helpText: 'The secret access key for your MinIO/S3 storage'
      },
      {
        name: 'use_ssl',
        label: 'Use SSL (HTTPS)',
        type: 'checkbox',
        required: false,
        default: false,
        helpText: 'Toggle on if your endpoint requires HTTPS'
      }
    ]
  },
  {
    id: 'mysql',
    name: 'MySQL',
    description: 'Connect to a MySQL database for workflow query and row operations',
    icon: 'mysql-credentials.svg',
    category: 'database',
    color: 'from-cyan-600 to-blue-700',
    fields: [
      {
        name: 'host',
        label: 'Host',
        type: 'text',
        required: true,
        default: 'localhost',
        placeholder: 'localhost',
        description: 'MySQL server hostname or IP address'
      },
      {
        name: 'port',
        label: 'Port',
        type: 'text',
        required: true,
        default: '3306',
        placeholder: '3306',
        description: 'MySQL TCP port'
      },
      {
        name: 'database',
        label: 'Database',
        type: 'text',
        required: true,
        placeholder: 'kai',
        description: 'Default database used by the connection'
      },
      {
        name: 'username',
        label: 'User',
        type: 'text',
        required: true,
        placeholder: 'kai',
        description: 'MySQL account username'
      },
      {
        name: 'password',
        label: 'Password',
        type: 'password',
        required: false,
        placeholder: '••••••••',
        description: 'MySQL account password'
      },
      {
        name: 'connect_timeout',
        label: 'Connect Timeout (ms)',
        type: 'text',
        required: false,
        default: '10000',
        description: 'Maximum time allowed for the initial connection'
      },
      {
        name: 'ssl',
        label: 'SSL',
        type: 'checkbox',
        required: false,
        default: false,
        description: 'Encrypt the MySQL connection with TLS'
      },
      {
        name: 'ca_certificate',
        label: 'CA Certificate',
        type: 'textarea',
        required: false,
        dependsOn: { field: 'ssl', values: [true] },
        description: 'Optional PEM certificate authority'
      },
      {
        name: 'client_certificate',
        label: 'Client Certificate',
        type: 'textarea',
        required: false,
        dependsOn: { field: 'ssl', values: [true] },
        description: 'Optional PEM client certificate'
      },
      {
        name: 'client_private_key',
        label: 'Client Private Key',
        type: 'textarea',
        required: false,
        dependsOn: { field: 'ssl', values: [true] },
        description: 'Optional PEM client private key'
      }
    ]
  }
];

export const getServiceDefinition = (serviceId: string): ServiceDefinition | undefined => {
  return SERVICE_DEFINITIONS.find(service => service.id === serviceId);
};

export const getServicesByCategory = () => {
  const grouped = SERVICE_DEFINITIONS.reduce((acc, service) => {
    if (!acc[service.category]) {
      acc[service.category] = [];
    }
    acc[service.category].push(service);
    return acc;
  }, {} as Record<string, ServiceDefinition[]>);

  return grouped;
};

export const getCategoryLabel = (category: string): string => {
  const labels: Record<string, string> = {
    ai: 'AI Services',
    database: 'Databases',
    api: 'APIs',
    storage: 'Storage',
    cache: 'Cache',
    webhook_auth: 'Webhook Auths',
    other: 'Other'
  };
  return labels[category] || category;
};
