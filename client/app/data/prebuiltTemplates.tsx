export type MarketplaceCategory = string;

export type PrebuiltTemplate = {
  id: string;
  name: string;
  description: string;
  category: MarketplaceCategory;
  created_at: string;
  colorFrom: string;
  colorTo: string;
  icon: { name: string; path: string | null; alt: string | null };
  flow_data: any;
};

const templateModules = import.meta.glob<PrebuiltTemplate>("./templates/*.json", {
  eager: true,
  import: "default",
});

export const prebuiltTemplates: PrebuiltTemplate[] = Object.values(templateModules);
