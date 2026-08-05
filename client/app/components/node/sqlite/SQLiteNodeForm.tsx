import GenericNodeForm from "../GenericNodeForm";
import type { GenericNodeProps } from "../types";

export interface SQLiteNodeFormProps {
  configData?: GenericNodeProps["data"];
  onSave?: (values: any) => void;
  onCancel: () => void;
  onChange?: (values: GenericNodeProps["data"]) => void;
}

/** SQLite uses the metadata-driven form directly and has no MySQL form dependency. */
export default function SQLiteNodeForm(props: SQLiteNodeFormProps) {
  return <GenericNodeForm {...props} />;
}
