const CREDENTIAL_META_FIELDS = new Set([
  "id",
  "name",
  "service_type",
  "created_at",
  "updated_at",
  "data",
  "secret",
]);

export const getCredentialData = (values: Record<string, any>) =>
  Object.fromEntries(
    Object.entries(values).filter(([key]) => !CREDENTIAL_META_FIELDS.has(key))
  );
