import { useI18n } from "@/app/preferencesContext";
import { PageHeader } from "@/components/layout/PageHeader";
import type { Messages } from "@/i18n/es";

/** Shell-only page used until the screen is implemented in its phase. */
export function makePlaceholder(key: keyof Messages["pages"]) {
  return function PlaceholderPage() {
    const { t } = useI18n();
    return <PageHeader title={t.pages[key].title} subtitle={t.pages[key].subtitle} />;
  };
}
