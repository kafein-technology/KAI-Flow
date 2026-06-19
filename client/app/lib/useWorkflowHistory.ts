import { useCallback, useEffect, useRef, useState } from "react";
import type { Node, Edge } from "@xyflow/react";

interface WorkflowSnapshot {
  nodes: Node[];
  edges: Edge[];
}

const MAX_HISTORY = 50;

const stableStringify = (obj: unknown): string => {
  if (obj === null || obj === undefined) return JSON.stringify(obj);
  if (typeof obj !== "object") return JSON.stringify(obj);
  if (Array.isArray(obj)) {
    return "[" + obj.map((item) => stableStringify(item)).join(",") + "]";
  }
  const sortedKeys = Object.keys(obj as Record<string, unknown>).sort();
  const parts = sortedKeys.map((key) => {
    const value = (obj as Record<string, unknown>)[key];
    return JSON.stringify(key) + ":" + stableStringify(value);
  });
  return "{" + parts.join(",") + "}";
};

const normalizeSnapshot = (nodes: Node[], edges: Edge[]): string => {
  const normalizedNodes = nodes.map((node) => ({
    id: node.id,
    type: node.type,
    position: {
      x: Math.round((node.position?.x || 0) * 1000) / 1000,
      y: Math.round((node.position?.y || 0) * 1000) / 1000,
    },
    data: node.data,
    width: node.width,
    height: node.height,
  }));

  const normalizedEdges = edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    sourceHandle: edge.sourceHandle || null,
    targetHandle: edge.targetHandle || null,
    type: edge.type || "custom",
  }));

  normalizedNodes.sort((a, b) => a.id.localeCompare(b.id));
  normalizedEdges.sort((a, b) => a.id.localeCompare(b.id));

  return stableStringify({ nodes: normalizedNodes, edges: normalizedEdges });
};

const cloneSnapshot = (nodes: Node[], edges: Edge[]): WorkflowSnapshot => ({
  nodes: JSON.parse(JSON.stringify(nodes)),
  edges: JSON.parse(JSON.stringify(edges)),
});

export function useWorkflowHistory(
  nodes: Node[],
  edges: Edge[],
  setNodes: React.Dispatch<React.SetStateAction<Node[]>>,
  setEdges: React.Dispatch<React.SetStateAction<Edge[]>>
) {
  const pastRef = useRef<WorkflowSnapshot[]>([]);
  const futureRef = useRef<WorkflowSnapshot[]>([]);
  const previousSnapshotRef = useRef<WorkflowSnapshot | null>(null);
  const isApplyingHistoryRef = useRef(false);
  const skipRecordingRef = useRef(false);
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);

  const updateAvailability = useCallback(() => {
    setCanUndo(pastRef.current.length > 0);
    setCanRedo(futureRef.current.length > 0);
  }, []);

  const resetHistory = useCallback(
    (snapshotNodes: Node[], snapshotEdges: Edge[]) => {
      pastRef.current = [];
      futureRef.current = [];
      previousSnapshotRef.current = cloneSnapshot(snapshotNodes, snapshotEdges);
      skipRecordingRef.current = true;
      updateAvailability();
    },
    [updateAvailability]
  );

  useEffect(() => {
    if (isApplyingHistoryRef.current) {
      isApplyingHistoryRef.current = false;
      return;
    }

    if (skipRecordingRef.current) {
      skipRecordingRef.current = false;
      previousSnapshotRef.current = cloneSnapshot(nodes, edges);
      return;
    }

    const timer = setTimeout(() => {
      const currentKey = normalizeSnapshot(nodes, edges);
      const previous = previousSnapshotRef.current;

      if (previous) {
        const previousKey = normalizeSnapshot(previous.nodes, previous.edges);
        if (previousKey !== currentKey) {
          pastRef.current.push(previous);
          if (pastRef.current.length > MAX_HISTORY) {
            pastRef.current.shift();
          }
          futureRef.current = [];
          updateAvailability();
        }
      }

      previousSnapshotRef.current = cloneSnapshot(nodes, edges);
    }, 300);

    return () => clearTimeout(timer);
  }, [nodes, edges, updateAvailability]);

  const undo = useCallback(() => {
    if (pastRef.current.length === 0) return;

    const current = cloneSnapshot(nodes, edges);
    futureRef.current.push(current);

    const previous = pastRef.current.pop()!;
    isApplyingHistoryRef.current = true;
    previousSnapshotRef.current = previous;
    setNodes(previous.nodes);
    setEdges(previous.edges);
    updateAvailability();
  }, [nodes, edges, setNodes, setEdges, updateAvailability]);

  const redo = useCallback(() => {
    if (futureRef.current.length === 0) return;

    const current = cloneSnapshot(nodes, edges);
    pastRef.current.push(current);

    const next = futureRef.current.pop()!;
    isApplyingHistoryRef.current = true;
    previousSnapshotRef.current = next;
    setNodes(next.nodes);
    setEdges(next.edges);
    updateAvailability();
  }, [nodes, edges, setNodes, setEdges, updateAvailability]);

  return { undo, redo, canUndo, canRedo, resetHistory };
}

/** True when focus is in a text-editing surface — workflow undo must not steal Ctrl+Z/Ctrl+Y. */
export const isEditableKeyboardTarget = (target: EventTarget | null): boolean => {
  if (!(target instanceof HTMLElement)) return false;

  if (target.closest(".monaco-editor")) return true;

  const tag = target.tagName;
  if (tag === "INPUT") {
    const type = (target as HTMLInputElement).type;
    if (type === "checkbox" || type === "radio" || type === "button" || type === "submit" || type === "file") {
      return false;
    }
    return true;
  }

  return tag === "TEXTAREA" || target.isContentEditable;
};
