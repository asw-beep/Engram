import Link from "next/link";

export default function Closing({ githubUrl }: { githubUrl: string }) {
  return (
    <footer className="closing">
      <p className="label closing-label">End of sheet</p>
      <p className="closing-type" data-anim="closing-type">
        Ask it
        <br />
        something.
      </p>
      <div className="closing-actions">
        <Link href="/ask" className="button closing-button" data-anim="magnet">
          Open the app <span aria-hidden="true">→</span>
        </Link>
        <a href={githubUrl} className="closing-link" target="_blank" rel="noopener noreferrer">
          Read the source on GitHub <span aria-hidden="true">↗</span>
        </a>
      </div>
    </footer>
  );
}
