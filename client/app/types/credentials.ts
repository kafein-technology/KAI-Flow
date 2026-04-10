export interface ServiceField {
  name: string;
  label: string;
  type: 'text' | 'password' | 'textarea' | 'select';
  required: boolean;
  placeholder?: string;
  default?: string;
  options?: { value: string; label: string }[];
  description?: string;
  dependsOn?: {
    field: string;
    values: string[];
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
        placeholder: 'https://openrouter.ai/api/v1',
        description: 'The endpoint URL for the compatible service'
      },
      {
        name: 'api_key',
        label: 'API Key',
        type: 'password',
        required: true,
        placeholder: '...',
        description: 'The authentication key for the compatible service'
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
    icon: 'kafka_credetial.svg',
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
