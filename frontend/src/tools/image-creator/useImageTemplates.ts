import { useDomainConfig } from "../../lib/useDomainConfig";
import type { ImageTemplate } from "../../types";

export function useImageTemplates(): ImageTemplate[] {
  const { config } = useDomainConfig();
  return config?.image_templates ?? [];
}
