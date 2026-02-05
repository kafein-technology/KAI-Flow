import React from "react";
import { Loader2 } from "~/icons/index";

type LoadingProps = {
  fullscreen?: boolean; // Tam ekran mı
  message?: string; // Yazı gösterilsin mi
  size?: "sm" | "md" | "lg"; // Spinner boyutu
  className?: string; // Ekstra class
};

const sizeMap = {
  sm: "h-4 w-4",
  md: "h-6 w-6",
  lg: "h-10 w-10",
};

export default function Loading({
  fullscreen = false,
  message = "Loading...",
  size = "md",
  className = "",
}: LoadingProps) {
  const spinnerSize = sizeMap[size];

  const content = (
    <div
      className={`flex flex-col items-center justify-center gap-2 ${className}`}
    >
      <Loader2 className={`${spinnerSize} animate-spin text-purple-600`} />
      {message && <p className="text-gray-500 text-sm">{message}</p>}
    </div>
  );

  if (fullscreen) {
    return (
      <div className="fixed inset-0 z-50 bg-white/80 backdrop-blur-sm flex items-center justify-center">
        {content}
      </div>
    );
  }

  return content;
}
