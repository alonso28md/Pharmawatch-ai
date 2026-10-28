import { Eye, EyeOff } from "lucide-react";
import { type FormEvent, type ReactNode, useState, useSyncExternalStore } from "react";
import { type Language, type MotionPreference, type ThemePreference, useI18n, usePreferences } from "@/app/preferencesContext";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/form";
import { Panel, Skeleton } from "@/components/ui/primitives";
import { api, ApiError, call } from "@/lib/api/client";
import { getApiKey, isKeyInSession, setApiKey, subscribeApiKey } from "@/lib/api/keyStore";
import { useConfig } from "@/lib/api/queries";
import { cn } from "@/lib/utils";

/** Segmented single choice built on native radios (arrow keys, labels and form semantics for free). */
function Choice<T extends string>({ legend, name, value, options, onChange, help }: {
  legend: string;
  name: string;
  value: T;
  options: { value: T; label: ReactNode }[];
  onChange: (value: T) => void;
  help?: string;
}) {
  return (
    <fieldset>
      <legend className="mb-2 text-body font-medium text-ink">{legend}</legend>
      <div className="inline-flex flex-wrap rounded-md border border-line-strong bg-surface p-0.5">
        {options.map((option) => (
          <label
            key={option.value}
            className={cn(
              "relative flex min-h-10 cursor-pointer items-center rounded-[5px] px-3.5 text-body transition-colors duration-[140ms]",
              "has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-1 has-[:focus-visible]:outline-focus",
              value === option.value ? "bg-accent text-accent-contrast" : "text-ink-muted hover:bg-surface-sunken hover:text-ink",
            )}
          >
            <input
              type="radio"
              name={name}
              value={option.value}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
              className="sr-only"
            />
            {option.label}
          </label>
        ))}
      </div>
      {help && <p className="mt-1.5 text-small text-ink-muted">{help}</p>}
    </fieldset>
  );
}

type CheckState = "idle" | "checking" | "ok" | "unauthorized" | "disabled" | "failed";

function ApiKeyPanel() {
  const { t } = useI18n();
  const stored = useSyncExternalStore(subscribeApiKey, getApiKey, () => null);
  const [draft, setDraft] = useState("");
  const [remember, setRemember] = useState(isKeyInSession);
  const [visible, setVisible] = useState(false);
  const [notice, setNotice] = useState("");
  const [check, setCheck] = useState<CheckState>("idle");

  function save(event: FormEvent) {
    event.preventDefault();
    setApiKey(draft, { rememberForSession: remember });
    setDraft("");
    setCheck("idle");
    setNotice(draft.trim() ? t.settingsPage.saved : t.settingsPage.cleared);
  }

  function clear() {
    setApiKey(null);
    setDraft("");
    setCheck("idle");
    setNotice(t.settingsPage.cleared);
  }

  async function runCheck() {
    setCheck("checking");
    try {
      await call(() => api.GET("/reports", { params: { query: { limit: 1 } } }));
      setCheck("ok");
    } catch (error) {
      const status = error instanceof ApiError ? error.status : 0;
      setCheck(status === 401 ? "unauthorized" : status === 403 ? "disabled" : "failed");
    }
  }

  const status = !stored ? t.settingsPage.statusNone : isKeyInSession() ? t.settingsPage.statusSession : t.settingsPage.statusMemory;
  const checkText: Partial<Record<CheckState, string>> = {
    ok: t.settingsPage.checkOk,
    unauthorized: t.settingsPage.checkUnauthorized,
    disabled: t.settingsPage.checkDisabled,
    failed: t.settingsPage.checkFailed,
  };

  return (
    <Panel title={t.settingsPage.keyTitle} description={t.settingsPage.keyIntro}>
      <form onSubmit={save} className="space-y-4">
        <Field label={t.settingsPage.keyLabel} help={t.settingsPage.keyHelp}>
          {({ id, describedBy }) => (
            <div className="flex gap-2">
              <Input
                id={id}
                aria-describedby={describedBy}
                type={visible ? "text" : "password"}
                autoComplete="off"
                spellCheck={false}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder={stored ? "••••••••" : undefined}
                className="font-mono"
              />
              <Button
                type="button"
                variant="secondary"
                size="icon"
                aria-label={visible ? t.settingsPage.hide : t.settingsPage.show}
                aria-pressed={visible}
                onClick={() => setVisible((v) => !v)}
              >
                {visible ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
              </Button>
            </div>
          )}
        </Field>
        <label className="flex min-h-10 cursor-pointer items-center gap-2 text-body text-ink">
          <input type="checkbox" className="size-4 accent-[var(--pw-accent)]" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
          {t.settingsPage.remember}
        </label>
        <div className="flex flex-wrap gap-2">
          <Button type="submit">{t.settingsPage.save}</Button>
          <Button type="button" variant="secondary" onClick={clear} disabled={!stored}>
            {t.settingsPage.clear}
          </Button>
          <Button type="button" variant="ghost" onClick={runCheck} loading={check === "checking"} loadingLabel={t.common.loading}>
            {t.settingsPage.check}
          </Button>
        </div>
      </form>
      <div className="mt-4 space-y-1 border-t border-line pt-3 text-small" aria-live="polite">
        <p className="text-ink">{status}</p>
        {notice && <p className="text-ink-muted">{notice}</p>}
        {checkText[check] && (
          <p className={cn("font-medium", check === "ok" ? "text-ok" : "text-critical")}>{checkText[check]}</p>
        )}
        <p className="text-ink-subtle">{t.settingsPage.checkNote}</p>
      </div>
    </Panel>
  );
}

function ServerPanel() {
  const { t, number } = useI18n();
  const config = useConfig();
  return (
    <Panel title={t.settingsPage.serverTitle}>
      {config.data ? (
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-body">
          <dt className="text-ink-muted">{t.health.model}</dt>
          <dd className="font-mono text-small" translate="no">{config.data.model}</dd>
          <dt className="text-ink-muted">{t.settingsPage.rateLimit}</dt>
          <dd className="tabular">{number(config.data.rate_limit_per_minute)}</dd>
          <dt className="text-ink-muted">{t.settingsPage.topK}</dt>
          <dd className="tabular">{number(config.data.retrieval_top_k)}</dd>
          <dt className="text-ink-muted">{t.settingsPage.languages}</dt>
          <dd>{config.data.supported_languages.join(", ")}</dd>
        </dl>
      ) : config.isError ? (
        <p className="text-body text-critical">{t.health.unreachable}</p>
      ) : (
        <Skeleton className="h-20 w-full" />
      )}
    </Panel>
  );
}

export function SettingsPage() {
  const { t } = useI18n();
  const prefs = usePreferences();
  return (
    <>
      <PageHeader title={t.pages.settings.title} subtitle={t.pages.settings.subtitle} />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <div className="space-y-6">
          <ApiKeyPanel />
          <ServerPanel />
        </div>
        <Panel title={t.settingsPage.prefsTitle} description={t.settingsPage.prefsNote} className="h-fit">
          <div className="space-y-6">
            <Choice<Language>
              legend={t.settingsPage.languageTitle}
              name="language"
              value={prefs.language}
              onChange={prefs.setLanguage}
              options={[
                { value: "es", label: <span lang="es">Español</span> },
                { value: "en", label: <span lang="en">English</span> },
              ]}
            />
            <Choice<ThemePreference>
              legend={t.settingsPage.themeTitle}
              name="theme"
              value={prefs.theme}
              onChange={prefs.setTheme}
              options={[
                { value: "light", label: t.settingsPage.themeLight },
                { value: "dark", label: t.settingsPage.themeDark },
                { value: "system", label: t.settingsPage.themeSystem },
              ]}
            />
            <Choice<MotionPreference>
              legend={t.settingsPage.motionTitle}
              name="motion"
              value={prefs.motion}
              onChange={prefs.setMotion}
              help={t.settingsPage.motionHelp}
              options={[
                { value: "system", label: t.settingsPage.motionSystem },
                { value: "reduce", label: t.settingsPage.motionReduce },
                { value: "full", label: t.settingsPage.motionFull },
              ]}
            />
          </div>
        </Panel>
      </div>
    </>
  );
}
