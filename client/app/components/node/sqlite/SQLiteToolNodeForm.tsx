import GenericNodeForm from "../GenericNodeForm";
import type { GenericNodeProps } from "../types";

export interface SQLiteToolNodeFormProps {
  configData?: GenericNodeProps["data"];
  onSave?: (values: any) => void;
  onCancel: () => void;
  onChange?: (values: GenericNodeProps["data"]) => void;
}

/** SQLite Tool configuration is rendered from SQLiteToolNode metadata only. */
export default function SQLiteToolNodeForm(props: SQLiteToolNodeFormProps) {
  return <GenericNodeForm {...props} />;
}
