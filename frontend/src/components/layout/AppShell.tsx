import { AnimatePresence, motion } from "motion/react";
import {
  Activity,
  ClipboardList,
  FlaskConical,
  Gauge,
  LayoutDashboard,
  Menu,
  MessageSquareText,
  Settings,
  Stethoscope,
  X,
} from "lucide-react";
import { useState } from "react";
import { NavLink, useLocation, useOutlet } from "react-router-dom";
import { useI18n } from "@/app/preferencesContext";
import { PulseField } from "@/components/background/PulseField";
import { HealthIndicator } from "@/components/layout/HealthIndicator";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", key: "dashboard", icon: LayoutDashboard },
  { to: "/triage", key: "triage", icon: Stethoscope },
  { to: "/ask", key: "ask", icon: MessageSquareText },
  { to: "/review", key: "review", icon: ClipboardList },
  { to: "/evaluation", key: "evaluation", icon: FlaskConical },
  { to: "/operations", key: "operations", icon: Gauge },
  { to: "/settings", key: "settings", icon: Settings },
] as const;

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useI18n();
  return (
    <ul className="flex flex-col gap-0.5">
      {NAV.map(({ to, key, icon: Icon }) => (
        <li key={to}>
          <NavLink
            to={to}
            end={to === "/"}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                "flex h-10 items-center gap-3 rounded-md px-3 text-body transition-colors duration-[140ms]",
                isActive
                  ? "bg-surface-sunken font-semibold text-ink"
                  : "text-ink-muted hover:bg-surface-sunken/70 hover:text-ink",
              )
            }
          >
            <Icon className="size-[18px] shrink-0" aria-hidden="true" />
            {t.nav[key]}
          </NavLink>
        </li>
      ))}
    </ul>
  );
}

function Brand() {
  const { t } = useI18n();
  return (
    <div className="flex items-center gap-2.5">
      <Activity className="size-5 text-accent" aria-hidden="true" />
      <div className="leading-tight">
        <p className="text-body font-semibold text-ink" translate="no">
          {t.app.name}
        </p>
        <p className="text-caption text-ink-subtle">{t.app.scope}</p>
      </div>
    </div>
  );
}

/** Route transitions: keep the outgoing page mounted while it fades out (≤ 220 ms). */
function AnimatedOutlet() {
  const location = useLocation();
  const outlet = useOutlet();
  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={location.pathname}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0, transition: { duration: 0.22, ease: [0, 0, 0, 1] } }}
        exit={{ opacity: 0, transition: { duration: 0.12, ease: [0.4, 0, 1, 1] } }}
      >
        {outlet}
      </motion.div>
    </AnimatePresence>
  );
}

export function AppShell() {
  const { t } = useI18n();
  const location = useLocation();
  // The menu belongs to the page it was opened on: navigating (links, back/forward) closes it.
  const [menuOpenOn, setMenuOpenOn] = useState<string | null>(null);
  const menuOpen = menuOpenOn === location.pathname;
  const setMenuOpen = (open: boolean) => setMenuOpenOn(open ? location.pathname : null);
  const mockMode = import.meta.env.VITE_USE_MOCKS === "true";

  return (
    <div className="relative min-h-dvh">
      <PulseField />
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-surface px-3 py-2 text-ink focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
      >
        {t.app.skip}
      </a>

      <div className="relative flex min-h-dvh">
        {/* Desktop sidebar */}
        <aside className="sticky top-0 hidden h-dvh w-[232px] shrink-0 flex-col border-r border-line bg-surface/85 px-3 py-5 lg:flex">
          <div className="px-2">
            <Brand />
          </div>
          <nav aria-label={t.nav.label} className="mt-7 flex-1">
            <NavItems />
          </nav>
          <div className="px-2">
            <HealthIndicator />
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          {/* Phone / tablet top bar */}
          <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-line bg-surface/90 px-4 lg:hidden">
            <Brand />
            <Button
              variant="ghost"
              size="icon"
              aria-expanded={menuOpen}
              aria-controls="mobile-nav"
              aria-label={menuOpen ? t.app.closeMenu : t.app.menu}
              onClick={() => setMenuOpen(!menuOpen)}
            >
              {menuOpen ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}
            </Button>
          </header>
          {menuOpen && (
            <nav
              id="mobile-nav"
              aria-label={t.nav.label}
              className="sticky top-14 z-20 border-b border-line bg-surface px-3 py-3 lg:hidden"
            >
              <NavItems onNavigate={() => setMenuOpen(false)} />
              <div className="mt-3 px-2">
                <HealthIndicator />
              </div>
            </nav>
          )}

          {mockMode && (
            <p role="status" className="border-b border-info-line bg-info-bg px-6 py-2 text-small text-info">
              {t.app.mockMode}
            </p>
          )}

          <main id="main" tabIndex={-1} className="mx-auto w-full max-w-[1200px] flex-1 px-4 py-6 outline-none sm:px-6 lg:py-8">
            <AnimatedOutlet />
          </main>

          <footer className="border-t border-line bg-surface/85 px-4 py-2.5 sm:px-6">
            <p className="text-caption text-ink-muted">{t.app.disclaimer}</p>
          </footer>
        </div>
      </div>
    </div>
  );
}
