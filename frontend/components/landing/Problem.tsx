const STATEMENT =
  "Engineering knowledge lives in code, design docs and old incident threads. Search finds files. It doesn't find answers, it can't show where an answer came from, and it doesn't know what you're allowed to read.";

/** One large statement. Each word is its own element so it can fill in as the page scrolls. */
export default function Problem() {
  return (
    <section id="problem" className="l-section problem">
      <p className="label section-label">01 — Problem</p>
      <p className="problem-text">
        {STATEMENT.split(" ").map((word, index) => (
          <span key={index} data-anim="problem-word">
            {word}{" "}
          </span>
        ))}
      </p>
    </section>
  );
}
