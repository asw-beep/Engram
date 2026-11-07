import type { Metadata } from "next";
import Link from "next/link";

import "./globals.css";

export const metadata: Metadata = {
  title: "Engram",
  description: "Ask questions about your engineering documents and check every answer against its sources.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <Link href="/" className="brand">
            Engram
          </Link>
          <nav aria-label="Main">
            <Link href="/">Ask</Link>
            <Link href="/sources">Sources</Link>
          </nav>
        </header>
        {children}
      </body>
    </html>
  );
}
