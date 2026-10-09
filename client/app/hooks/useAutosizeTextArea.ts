import { useEffect } from "react";

/**
 * Custom hook to automatically adjust the height of a textarea element
 * based on its content scrollHeight up to a specified maximum height.
 */
export const useAutosizeTextArea = (
  textAreaRef: HTMLTextAreaElement | null,
  value: string,
  maxHeight: number = 160
) => {
  useEffect(() => {
    if (textAreaRef) {
      textAreaRef.style.height = "auto";
      const scrollHeight = textAreaRef.scrollHeight;
      textAreaRef.style.height = `${Math.min(scrollHeight, maxHeight)}px`;
    }
  }, [textAreaRef, value, maxHeight]);
};
