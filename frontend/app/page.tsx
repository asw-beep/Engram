import Link from "next/link";

export default function LandingPage() {
  return (
    <main className="page">
      <h1 className="page-title">Engram</h1>
      <p className="lede">
        <Link href="/ask">Ask a question</Link>
      </p>
    </main>
  );
}
