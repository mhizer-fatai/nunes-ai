"use client";

import Link from "next/link";
import ThemeToggle from "./ThemeToggle";
import { useStuck } from "./Motion";

export default function Nav({ links = [], cta }) {
  const stuck = useStuck();
  return (
    <nav className={"nav" + (stuck ? " stuck" : "")}>
      <div className="wrap nav-inner">
        <Link href="/" className="brand">
          <span className="brand-mark">N</span>
          Nunes <em>AI</em>
        </Link>
        {links.length > 0 && (
          <div className="nav-links">
            {links.map((l) =>
              l.href.startsWith("#") ? (
                <a href={l.href} key={l.href}>
                  {l.label}
                </a>
              ) : (
                <Link href={l.href} key={l.href}>
                  {l.label}
                </Link>
              )
            )}
          </div>
        )}
        <div className="nav-right">
          {cta}
          <ThemeToggle />
        </div>
      </div>
    </nav>
  );
}
