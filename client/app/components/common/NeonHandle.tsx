import React, { useState } from "react";
import { Handle, Position } from "@xyflow/react";

export const NeonHandle = ({
  type = "source",
  position = Position.Right,
  id,
  isConnectable = true,
  className = "",
  size = 16,
  color1 = "#a855f7",
  glow = false,
  ...props
}: {
  type?: "source" | "target";
  position?: Position;
  id?: string;
  isConnectable?: boolean;
  className?: string;
  size?: number;
  color1?: string;
  glow?: boolean;
  [key: string]: any;
}) => {
  // CSS variable style for dynamic color and size
  const styleVars = {
    "--neon-size": `${size}px`,
    "--neon-color": color1,
  } as React.CSSProperties;

  return (
    <Handle
      type={type}
      position={position}
      id={id}
      isConnectable={isConnectable}
      className={`
        !rounded-full !border-1 !border-white
        bg-[var(--neon-color)]
        ${
          glow
            ? "shadow-[0_0_8px_2px_var(--neon-color),0_0_16px_4px_var(--neon-color)]"
            : ""
        }
         z-30
        ${
          glow
            ? "before:content-[''] before:absolute before:inset-0 before:rounded-full before:bg-[radial-gradient(circle,var(--neon-color)_0%,transparent_80%)] before:opacity-40 before:blur-[3px] after:content-[''] after:absolute after:inset-0 after:rounded-full after:bg-[radial-gradient(circle,var(--neon-color)_0%,transparent_80%)] after:opacity-30 after:blur-[5px]"
            : ""
        }
        transition-all duration-300
        ${className}
      `}
      style={{
        width: `var(--neon-size)`,
        height: `var(--neon-size)`,
        ...styleVars,
      }}
      {...props}
    />
  );
};

export default NeonHandle;
