import { CircleAlert, KeyRound, ServerOff, Timer } from "lucide-react";
import { Link } from "react-router-dom";
import { useI18n } from "@/app/preferencesContext";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";

/** Explains a failed request in plain language, with the next step (never a stack trace). */
export function ErrorNotice({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useI18n();
  const e = error instanceof ApiError ? error : new ApiError(0, "unknown", String(error));

  let Icon = CircleAlert;
  let title = t.errors.genericTitle;
  let body: string = e.message;
  let settingsLink = false;

  if (e.isEndpointDisabled) {
    Icon = KeyRound; title = t.errors.endpointDisabledTitle; body = t.errors.endpointDisabledBody; settingsLink = true;
  } else if (e.isUnauthorized) {
    Icon = KeyRound; title = t.errors.unauthorizedTitle; body = t.errors.unauthorizedBody; settingsLink = true;
  } else if (e.code === "llm_unavailable" || e.code === "llm_bad_output") {
    Icon = ServerOff; title = t.errors.llmUnavailableTitle; body = t.errors.llmUnavailableBody;
  } else if (e.code === "network_error") {
    Icon = ServerOff; title = t.errors.networkTitle; body = t.errors.networkBody;
  } else if (e.status === 429) {
    Icon = Timer; title = t.errors.rateLimitedTitle; body = t.errors.rateLimitedBody;
  } else if (e.status === 413) {
    title = t.errors.tooLargeTitle;
  } else if (e.status === 422) {
    title = t.errors.validationTitle;
  }

  return (
    <div role="alert" className="flex gap-3 rounded-lg border border-critical-line bg-critical-bg px-4 py-3 text-critical">
      <Icon className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="font-semibold">{title}</p>
        <p className="mt-0.5 text-small">{body}</p>
        {(onRetry || settingsLink) && (
          <div className="mt-3 flex flex-wrap gap-2">
            {onRetry && (
              <Button size="sm" variant="secondary" onClick={onRetry}>
                {t.errors.retry}
              </Button>
            )}
            {settingsLink && (
              <Button size="sm" variant="secondary" asChild>
                <Link to="/settings">{t.errors.goToSettings}</Link>
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
