import type { WorkflowData } from "~/types/api";

type JsonObject = Record<string, unknown>;

export interface ImportedWorkflowJson extends JsonObject {
  name?: string;
  description?: string;
  is_public?: boolean;
  flow_data: WorkflowData;
}

export class WorkflowJsonError extends Error {
  constructor(message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "WorkflowJsonError";
  }
}

const isJsonObject = (value: unknown): value is JsonObject =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const requireArray = (
  value: unknown,
  fieldName: string,
): unknown[] => {
  if (!Array.isArray(value)) {
    throw new WorkflowJsonError(
      `Invalid workflow JSON: ${fieldName} must be an array.`,
    );
  }
  return value;
};

/**
 * Parse the simple, single-workflow JSON used by the canvas Export JSON action.
 * This intentionally does not handle the separate ZIP/package export format.
 */
export const parseWorkflowJson = (text: string): ImportedWorkflowJson => {
  const source = text.replace(/^\uFEFF/, "").trim();
  if (!source) {
    throw new WorkflowJsonError("The selected workflow JSON file is empty.");
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(source);
  } catch (error) {
    throw new WorkflowJsonError(
      "The selected file does not contain valid JSON.",
      { cause: error },
    );
  }

  if (!isJsonObject(parsed)) {
    throw new WorkflowJsonError(
      "Invalid workflow JSON: the root value must be an object.",
    );
  }

  // Current exports wrap the graph in flow_data. Direct nodes/edges support is
  // retained for older single-workflow canvas exports.
  const rawFlowData = isJsonObject(parsed.flow_data)
    ? parsed.flow_data
    : Array.isArray(parsed.nodes) && Array.isArray(parsed.edges)
      ? parsed
      : null;

  if (!rawFlowData) {
    throw new WorkflowJsonError(
      "Invalid workflow JSON: flow_data with nodes and edges is required.",
    );
  }

  const nodes = requireArray(rawFlowData.nodes, "flow_data.nodes");
  const edges = requireArray(rawFlowData.edges, "flow_data.edges");

  if (!nodes.every(isJsonObject)) {
    throw new WorkflowJsonError(
      "Invalid workflow JSON: every node must be an object.",
    );
  }
  if (!edges.every(isJsonObject)) {
    throw new WorkflowJsonError(
      "Invalid workflow JSON: every edge must be an object.",
    );
  }

  return {
    ...parsed,
    flow_data: {
      ...rawFlowData,
      nodes: nodes as unknown as WorkflowData["nodes"],
      edges: edges as unknown as WorkflowData["edges"],
    },
  } as ImportedWorkflowJson;
};

export const getWorkflowJsonErrorMessage = (error: unknown): string =>
  error instanceof WorkflowJsonError
    ? error.message
    : "The workflow JSON is valid, but it could not be loaded into the canvas.";
