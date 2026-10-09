import copy from "copy-to-clipboard";

/**
 * Safe clipboard utility that works in all environments
 * @param text - Text to copy to clipboard
 * @returns Promise that resolves to true if successful
 */
export const copyToClipboard = async (text: string): Promise<boolean> => {
  try {
    const success = await copy(text);
    return success;
  } catch (err) {
    console.error("Clipboard operation failed:", err);
    return false;
  }
};

/**
 * Copy text with feedback (for React components that show copy status)
 * @param text - Text to copy
 * @param onSuccess - Callback when copy succeeds
 * @param onError - Callback when copy fails
 */
export const copyWithFeedback = async (
  text: string,
  onSuccess?: () => void,
  onError?: (error: any) => void
): Promise<void> => {
  try {
    const success = await copy(text);
    if (success) {
      onSuccess?.();
    } else {
      onError?.(new Error("Copy failed"));
    }
  } catch (err) {
    console.error("Clipboard operation failed:", err);
    onError?.(err);
  }
};
