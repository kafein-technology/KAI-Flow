import type { NodeMetadata } from '../../../../client/app/types/api'

export interface NodeInput {
  name: string;
  type: string;
  default?: any;
  required: boolean;
  ui_config?: {
    widget?: string;
    placeholder?: string;
    rows?: number;
    resize?: string;
    [key: string]: any;
  } | null;
  description?: string;
  is_connection: boolean;
  validation_rules?: {
    pattern?: string | null;
    max_length?: number;
    min_length?: number;
    [key: string]: any;
  } | null;
}

export interface NodeOutput {
  name: string;
  type: string;
  format?: string | null;
  description?: string;
  output_schema?: any;
}

export interface NodeProperty {
  name: string;
  displayName: string;
  type: string;
  placeholder?: string;
  required?: boolean;
  maxLength?: number;
  serviceType?: string;
  rows?: number;
  [key: string]: any;
}

export interface GenericData {
  // Görüntüleme alanları
  display_name?: string;
  displayName?: string;
  name?: string;
  colors?: string[];
  description?: string;

  // Node yapılandırma verileri
  inputs?: NodeInput[];
  outputs?: NodeOutput[];
  metadata?: NodeMetadata;
  properties?: NodeProperty[];

  // Validasyon durumu
  validationStatus?: "success" | "error" | "pending";

  // Diğer dinamik alanlar (text_input, model_name, vs.)
  [key: string]: any;
}

export interface GenericNodeProps {
  data: GenericData;
  id: string;
}