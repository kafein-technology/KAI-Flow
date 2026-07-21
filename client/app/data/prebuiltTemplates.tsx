export type MarketplaceCategory =
  | "automation"
  | "data-processing"
  | "ai-ml"
  | "integration";

type TemplateJson = {
  id: string;
  name: string;
  description: string;
  colorFrom: string;
  colorTo: string;
  icon: { name: string; path: string | null; alt: string | null };
  flow_data: any;
};

export type PrebuiltTemplate = TemplateJson & {
  category: MarketplaceCategory;
  popularity: number;
  created_at: string;
};

/** Marketplace metadata kept here so template JSON files stay untouched in the PR. */
const templateMeta: Record<
  string,
  { category: MarketplaceCategory; popularity: number; created_at: string }
> = {
  "basic-agent": {
    category: "ai-ml",
    popularity: 100,
    created_at: "2025-01-15T00:00:00.000Z",
  },
  "webhook-template": {
    category: "integration",
    popularity: 75,
    created_at: "2025-02-20T00:00:00.000Z",
  },
  "rag-pipeline": {
    category: "data-processing",
    popularity: 80,
    created_at: "2025-03-01T00:00:00.000Z",
  },
  "rag-usage-flow": {
    category: "ai-ml",
    popularity: 90,
    created_at: "2025-03-10T00:00:00.000Z",
  },
  "kafka-template": {
    category: "automation",
    popularity: 70,
    created_at: "2025-04-01T00:00:00.000Z",
  },
};

const templateModules = import.meta.glob<TemplateJson>("./templates/*.json", {
  eager: true,
  import: "default",
});

export const prebuiltTemplates: PrebuiltTemplate[] = Object.values(
  templateModules
).map((tpl) => {
  const meta = templateMeta[tpl.id] ?? {
    category: "automation" as MarketplaceCategory,
    popularity: 0,
    created_at: "2025-01-01T00:00:00.000Z",
  };
  return { ...tpl, ...meta };
});
