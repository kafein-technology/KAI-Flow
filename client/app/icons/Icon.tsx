import React from "react";
import * as Icons from "~/icons/index";

interface IconProps {
  name: string;
  className?: string;
  size?: number;
  [key: string]: any;
}

/**
 * Dynamic Icon component that renders icons by name.
 * Maps icon names to actual icon components from the icons/index export.
 */
const Icon = React.forwardRef<any, IconProps>(
  ({ name, className, size, ...props }, ref) => {
    // Get the icon component from the Icons export
    const IconComponent = (Icons as Record<string, React.ComponentType<any>>)[
      name
    ];

    if (!IconComponent) {
      console.warn(`Icon "${name}" not found`);
      return null;
    }

    return (
      <IconComponent
        ref={ref}
        className={className}
        size={size}
        {...props}
      />
    );
  }
);

Icon.displayName = "Icon";

export default Icon;
