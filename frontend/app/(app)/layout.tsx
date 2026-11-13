import Link from "next/link";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <header className="app-header">
        <Link href="/" className="brand">
          Engram
        </Link>
        <nav aria-label="Main">
          <Link href="/ask">Ask</Link>
          <Link href="/sources">Sources</Link>
        </nav>
      </header>
      {children}
    </>
  );
}
