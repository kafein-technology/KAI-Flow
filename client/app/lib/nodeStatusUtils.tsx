import React, { type CSSProperties } from "react";

export type ExecutionStatus = "success" | "failed" | "pending" | string;
export {
  getEdgeExecutionStatus,
  getEffectiveNodeStatus,
} from "./executionStatus";
export type { CanvasExecutionStatus } from "./executionStatus";

export function getExecutionStatusStyle(
  status?: ExecutionStatus
): CSSProperties | undefined {
  if (status === "success") {
    return {
      boxShadow: "0 0 0 3px #22c55e, 0 0 16px rgba(34, 197, 94, 0.6)",
    };
  }
  if (status === "failed") {
    return {
      boxShadow: "0 0 0 3px #ef4444, 0 0 16px rgba(239, 68, 68, 0.6)",
    };
  }
  return undefined;
}

interface PendingWormRingProps {
  borderRadius?: string;
  rx?: number;
}

/**
 * Finalized Production Pending Execution Ring Component
 * Uses the user's exact chosen values:
 * - Amber gold photon particle (#f59e0b) with soft yellow core (#fef08a)
 * - 3.0px border track (#f59e0b) matching success (3px) and failed (3px) width
 * - Outward-only SVG mask to keep node face 100% clean
 * - 4.5s smooth clockwise rotation
 */
export const PendingWormRing: React.FC<PendingWormRingProps> = ({
  borderRadius = "1rem",
  rx = 16,
}) => {
  const orbLength = 12;
  const dashLength = orbLength;
  const dashGap = Math.max(1, 100 - orbLength);
  const strokeDash = `${dashLength} ${dashGap}`;
  const speed = 4.5;

  const glowBlur = 3.0;
  const outwardGlowWidth = 3.0;
  const outwardGlowOpacity = 1.0;

  const mainColor = "#f59e0b";
  const coreColor = "#fef08a";
  const trackColor = "#f59e0b";
  const trackOpacity = 1.0;
  const trackWidth = 3.0;

  const uniqueId = React.useId().replace(/:/g, "");
  const filterId = `outward-amber-glow-${uniqueId}`;
  const maskId = `outward-only-mask-${uniqueId}`;

  return (
    <div
      className="pointer-events-none absolute inset-0 z-0 overflow-visible"
      style={{ borderRadius }}
    >
      <svg className="w-full h-full overflow-visible">
        <defs>
          {/* Outward-Only Mask: Blackout 100% of light inside node face so glow ONLY radiates outward */}
          <mask id={maskId}>
            <rect x="-200%" y="-200%" width="500%" height="500%" fill="white" />
            <rect
              x="2"
              y="2"
              width="calc(100% - 4px)"
              height="calc(100% - 4px)"
              rx={rx}
              fill="black"
            />
          </mask>

          {/* Deep Volumetric Outward Gaussian Blur Filter */}
          <filter id={filterId} x="-200%" y="-200%" width="500%" height="500%">
            <feGaussianBlur stdDeviation={glowBlur} result="wideOutwardGlow" />
            <feMerge>
              <feMergeNode in="wideOutwardGlow" />
              <feMergeNode in="wideOutwardGlow" />
            </feMerge>
          </filter>
        </defs>

        {/* Base ambient track rail (Exact 3px thickness) */}
        <rect
          x="0"
          y="0"
          width="100%"
          height="100%"
          rx={rx}
          fill="none"
          stroke={trackColor}
          strokeWidth={trackWidth}
          strokeOpacity={trackOpacity}
        />

        {/* Outward-Only Volumetric Glowing Atmosphere */}
        <g mask={`url(#${maskId})`}>
          <rect
            x="0"
            y="0"
            width="100%"
            height="100%"
            rx={rx}
            pathLength={100}
            fill="none"
            stroke={mainColor}
            strokeWidth={outwardGlowWidth}
            strokeLinecap="round"
            strokeDasharray={strokeDash}
            style={{
              animation: `clean-border-flow ${speed}s linear infinite`,
              filter: `url(#${filterId})`,
              opacity: outwardGlowOpacity,
            }}
          />
        </g>

        {/* Crisp photon particle track */}
        <rect
          x="0"
          y="0"
          width="100%"
          height="100%"
          rx={rx}
          pathLength={100}
          fill="none"
          stroke={mainColor}
          strokeWidth={trackWidth}
          strokeLinecap="round"
          strokeDasharray={strokeDash}
          style={{
            animation: `clean-border-flow ${speed}s linear infinite`,
          }}
        />

        {/* Crisp bright yellow-white core spark center */}
        <rect
          x="0"
          y="0"
          width="100%"
          height="100%"
          rx={rx}
          pathLength={100}
          fill="none"
          stroke={coreColor}
          strokeWidth={trackWidth - 1}
          strokeLinecap="round"
          strokeDasharray={strokeDash}
          style={{
            animation: `clean-border-flow ${speed}s linear infinite`,
          }}
        />
      </svg>

      <style>{`
        @keyframes clean-border-flow {
          0% { stroke-dashoffset: 0; }
          100% { stroke-dashoffset: -100; }
        }
      `}</style>
    </div>
  );
};
