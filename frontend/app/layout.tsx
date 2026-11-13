import type { Metadata } from "next";
import { JetBrains_Mono, Space_Grotesk } from "next/font/google";

import "./globals.css";

const text = Space_Grotesk({ subsets: ["latin"], variable: "--font-text", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono", display: "swap" });

export const metadata: Metadata = {
  title: "Engram",
  description: "Ask questions about your engineering documents and check every answer against its sources.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // The landing page's pre-paint script adds a class to <html>, which React must leave alone.
    <html lang="en" className={`${text.variable} ${mono.variable}`} suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
