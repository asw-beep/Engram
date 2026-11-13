"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const SECTIONS = [
  { href: "#problem", label: "Problem" },
  { href: "#pipeline", label: "Pipeline" },
  { href: "#specimen", label: "Specimen" },
  { href: "#system", label: "System" },
];

/** The landing header. It slides away while the visitor scrolls down and returns on the way up. */
export default function Nav({ githubUrl }: { githubUrl: string }) {
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    let last = window.scrollY;
    function onScroll() {
      const now = window.scrollY;
      setHidden(now > last && now > 160);
      last = now;
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header className="l-nav" data-hidden={hidden}>
      <Link href="/" className="brand">
        Engram
      </Link>
      <nav aria-label="Main">
        <ol className="l-nav-sections">
          {SECTIONS.map((section, index) => (
            <li key={section.href}>
              <a href={section.href}>
                <span aria-hidden="true">0{index + 1} </span>
                {section.label}
              </a>
            </li>
          ))}
        </ol>
        <a href={githubUrl} target="_blank" rel="noopener noreferrer">
          GitHub <span aria-hidden="true">↗</span>
        </a>
        <Link href="/ask" className="l-nav-ask">
          Ask <span aria-hidden="true">→</span>
        </Link>
      </nav>
    </header>
  );
}
