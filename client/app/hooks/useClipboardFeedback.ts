import { useCallback } from "react";
import { useSnackbar } from "notistack";

import { copyToClipboard } from "~/lib/clipboard";

const DEFAULT_SUCCESS_MESSAGE = "Copied to clipboard.";
const DEFAULT_ERROR_MESSAGE = "Could not copy to clipboard.";
const DEFAULT_AUTO_HIDE_DURATION = 2000;

export function useClipboardFeedback() {
  const { enqueueSnackbar } = useSnackbar();

  const copy = useCallback(
    async (value: string): Promise<boolean> => {
      if (!value) return false;

      const copied = await copyToClipboard(value);
      enqueueSnackbar(
        copied ? DEFAULT_SUCCESS_MESSAGE : DEFAULT_ERROR_MESSAGE,
        {
          variant: copied ? "success" : "error",
          autoHideDuration: DEFAULT_AUTO_HIDE_DURATION,
          preventDuplicate: true,
        },
      );
      return copied;
    },
    [enqueueSnackbar],
  );

  return { copy };
}
