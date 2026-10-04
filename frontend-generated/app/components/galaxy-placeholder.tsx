import { Link } from "react-router";

import { GalaxyShell } from "@/components/galaxy-shell";

export function GalaxyPlaceholder({ title }: { title: string }) {
  return (
    <GalaxyShell>
      <main className="placeholder-page page-width">
        <span className="section-kicker">GALAXY-RESOLVE</span>
        <h1>{title}</h1>
        <p>
          This page is ready to take shape. Continue prompting to build out this
          experience.
        </p>
        <Link className="button-primary" to="/demo">
          Explore the live demo <span aria-hidden="true">→</span>
        </Link>
      </main>
    </GalaxyShell>
  );
}
