import AskForm from "@/components/AskForm";

export default function AskPage() {
  return (
    <main className="page">
      <p className="label page-kicker">Query</p>
      <h1 className="page-title">Ask your engineering documents</h1>
      <p className="lede">
        Every answer cites the passages it comes from. Select a marker such as [1] to read the
        passage beside the answer.
      </p>
      <AskForm />
    </main>
  );
}
