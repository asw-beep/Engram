const STEPS = ["Retrieve", "Generate", "Verify"];

/**
 * Shown while a question is being answered. The API replies in one response, so the steps
 * are a timed illustration, and screen readers get the sentence only.
 */
export default function AskProgress() {
  return (
    <div className="ask-progress">
      <p className="status">Searching your documents and checking citations…</p>
      <ol className="ask-steps" aria-hidden="true">
        {STEPS.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>
    </div>
  );
}
