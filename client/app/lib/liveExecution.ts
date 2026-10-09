export type LiveNodeOutputMap = Record<string, any>;

type LiveNodeEvent = Record<string, any>;

const isRecord = (value: unknown): value is Record<string, any> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

const recordDetailScore = (record: Record<string, any>): number => {
  let score = 0;
  if (record.output !== undefined && record.output !== null) score += 4;
  if (record.outputs !== undefined && record.outputs !== null) score += 2;
  if (isRecord(record.inputs) && Object.keys(record.inputs).length > 0) score += 2;
  if (isRecord(record.inputs_meta) && Object.keys(record.inputs_meta).length > 0) score += 1;
  if (Number(record.executionTimeMs) > 0) score += 1;
  return score;
};

const mergeNodeOutputRecord = (current: unknown, reported: unknown): unknown => {
  if (!isRecord(current) || !isRecord(reported)) return reported;

  const preferCurrent = recordDetailScore(current) > recordDetailScore(reported);
  const merged = preferCurrent
    ? { ...reported, ...current }
    : { ...current, ...reported };

  const reportedFailed =
    reported.success === false ||
    reported.status === "failed" ||
    reported.status === "error";
  if (reportedFailed) {
    merged.success = false;
    merged.status = "failed";
    merged.statusCode = reported.statusCode ?? 500;
    merged.error = reported.error || merged.error;
  }

  return merged;
};

export const mergeLiveNodeOutputMaps = (
  current: LiveNodeOutputMap,
  reported: unknown
): LiveNodeOutputMap => {
  if (!isRecord(reported)) return { ...current };

  const merged = { ...current };
  Object.entries(reported).forEach(([nodeId, output]) => {
    merged[nodeId] = mergeNodeOutputRecord(current[nodeId], output);
  });
  return merged;
};

/**
 * Reduce one streaming lifecycle event into the node-output shape consumed by
 * the canvas detail panel. The same reducer is shared by Start and Chat runs so
 * node details no longer depend on which trigger opened the execution stream.
 */
export const reduceLiveNodeEvent = (
  current: LiveNodeOutputMap,
  nodeId: string,
  event: LiveNodeEvent
): LiveNodeOutputMap => {
  if (!nodeId) return current;

  const eventType = event.event || event.type;
  const runtimeStatus = event.status;
  const previous = isRecord(current[nodeId]) ? current[nodeId] : {};
  const metadata = isRecord(event.metadata) ? event.metadata : {};
  const inputs = event.inputs ?? metadata.inputs;
  const inputsMeta = event.inputs_meta ?? metadata.inputs_meta;

  if (
    eventType === "node_start" ||
    (eventType === "node_status" && runtimeStatus === "pending")
  ) {
    return {
      ...current,
      [nodeId]: {
        ...previous,
        ...(inputs !== undefined ? { inputs } : {}),
        ...(inputsMeta !== undefined ? { inputs_meta: inputsMeta } : {}),
        status: "running",
      },
    };
  }

  const isTerminal =
    eventType === "node_end" ||
    (eventType === "node_status" &&
      (runtimeStatus === "success" || runtimeStatus === "failed"));
  if (!isTerminal) return current;

  const rawOutput = event.output ?? event.node_output;
  const failed =
    runtimeStatus === "failed" ||
    event.status === "error" ||
    Boolean(event.error);

  let next: Record<string, any> = { ...previous };
  if (isRecord(rawOutput)) {
    const isStandardOutput =
      "success" in rawOutput ||
      "nodeId" in rawOutput ||
      "statusCode" in rawOutput;
    next = isStandardOutput
      ? { ...next, ...rawOutput }
      : { ...next, output: rawOutput, outputs: rawOutput };
  } else if (rawOutput !== undefined) {
    next = { ...next, output: rawOutput, outputs: rawOutput };
  }

  if (inputs !== undefined && next.inputs === undefined) next.inputs = inputs;
  if (inputsMeta !== undefined && next.inputs_meta === undefined) {
    next.inputs_meta = inputsMeta;
  }

  next.status = failed ? "failed" : "completed";
  next.success = failed ? false : next.success ?? true;

  if (failed && !next.error) {
    next.error = {
      error_type: event.error_type || "execution",
      error_message: String(event.error || "Node execution failed"),
    };
  }

  return { ...current, [nodeId]: next };
};

export const ensureLiveNodeFailure = (
  current: LiveNodeOutputMap,
  nodeId: string,
  event: LiveNodeEvent
): LiveNodeOutputMap => {
  if (!nodeId) return current;

  const previous = isRecord(current[nodeId]) ? current[nodeId] : {};
  const errorMessage = String(event.error || event.message || "Node execution failed");
  const errorDetails = isRecord(previous.error)
    ? previous.error
    : {
        error_type: event.error_type || "execution",
        error_message: errorMessage,
      };

  return {
    ...current,
    [nodeId]: {
      ...previous,
      success: false,
      status: "failed",
      statusCode: previous.statusCode ?? 500,
      nodeId: previous.nodeId ?? nodeId,
      output: previous.output ?? null,
      error: errorDetails,
    },
  };
};
