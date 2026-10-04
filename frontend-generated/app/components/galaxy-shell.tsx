import { IconCircleCheck } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router";

import { galaxyApiUrl } from "@/lib/galaxy-api";

const navigation = [
  { label: "Home", href: "/" },
  { label: "Demo", href: "/demo" },
  { label: "Features", href: "/features" },
  { label: "Metrics", href: "/metrics" },
];

export function GalaxyShell({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation();
  const [health, setHealth] = useState<"checking" | "healthy" | "offline">(
    "checking",
  );

  useEffect(() => {
    document.documentElement.classList.add("motion-ready");
    if (!("IntersectionObserver" in window)) {
      document
        .querySelectorAll(".reveal")
        .forEach((element) => element.classList.add("is-revealed"));
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-revealed");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12 },
    );
    document
      .querySelectorAll(".reveal")
      .forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, [pathname]);

  useEffect(() => {
    let active = true;
    const checkHealth = async () => {
      try {
        const response = await fetch(galaxyApiUrl("/health"), {
          cache: "no-store",
        });
        if (active) setHealth(response.ok ? "healthy" : "offline");
      } catch {
        if (active) setHealth("offline");
      }
    };

    void checkHealth();
    const interval = window.setInterval(checkHealth, 30000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  return (
    <div className="galaxy-site">
      <header className="site-header">
        <div className="site-header-inner">
          <Link
            className="brand-lockup"
            to="/"
            aria-label="Galaxy-Resolve home"
          >
            <span className="brand-mark" aria-hidden="true">
              <span />
            </span>
            <span>Galaxy-Resolve</span>
          </Link>
          <nav className="site-nav" aria-label="Main navigation">
            {navigation.map((item) => (
              <Link
                key={item.href}
                to={item.href}
                className={
                  pathname === item.href ? "nav-link is-active" : "nav-link"
                }
                aria-current={pathname === item.href ? "page" : undefined}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <div className={`health-status health-${health}`} aria-live="polite">
            <span className="health-dot" />
            <span>
              {health === "checking"
                ? "Checking"
                : health === "healthy"
                  ? "System live"
                  : "API offline"}
            </span>
          </div>
        </div>
      </header>
      {children}
      <footer className="site-footer">
        <div className="site-footer-inner">
          <div className="footer-brand">
            <span className="brand-mark brand-mark-small" aria-hidden="true">
              <span />
            </span>
            <div>
              <strong>Galaxy-Resolve</strong>
              <p>Built for Samsung PRISM GenAI Hackathon 2026 · Theme 2</p>
            </div>
          </div>
          <div className="footer-links">
            {navigation.map((item) => (
              <Link key={item.href} to={item.href}>
                {item.label}
              </Link>
            ))}
          </div>
          <div className="footer-signoff">
            <IconCircleCheck size={15} stroke={1.7} /> Smart Guided
            Troubleshooting Engine
          </div>
        </div>
      </footer>
    </div>
  );
}
