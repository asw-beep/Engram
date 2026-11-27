import type { Measurement } from "@/lib/system";

type Data = {
  questions: number;
  documents: number;
  served: string;
  rows: Measurement[];
  note: string;
  resultsUrl: string;
};

/** Retrieval quality per configuration, from the evaluation's test split. */
export default function Measured({ data }: { data: Data }) {
  return (
    <section id="measured" className="l-section measured">
      <p className="label section-label">
        04 — Measured <span className="status-tag">provisional</span>
      </p>
      <h2 className="section-title">Measured, not assumed.</h2>
      <p className="section-lede">
        Every configuration answers the same {data.questions} test questions over{" "}
        {data.documents} pages of the Kubernetes documentation. Recall@5 counts a question when
        every section that answers it is in the top five passages.
      </p>
      <div className="ms-frame">
        <table className="ms-table">
          <caption className="visually-hidden">Retrieval quality by configuration</caption>
          <thead>
            <tr>
              <th scope="col">Configuration</th>
              <th scope="col">Recall@5</th>
              <th scope="col">MRR@10</th>
              <th scope="col">NDCG@10</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => (
              <tr key={row.config} className={row.config === data.served ? "ms-served" : undefined}>
                <th scope="row">
                  <span className="ms-config">
                    {row.label}
                    {row.config === data.served && <span className="status-tag">served</span>}
                  </span>
                </th>
                <td>{row.recallAt5.toFixed(3)}</td>
                <td>{row.mrrAt10.toFixed(3)}</td>
                <td>{row.ndcgAt10.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="ms-note">{data.note}</p>
      <a href={data.resultsUrl} className="ms-link" target="_blank" rel="noopener noreferrer">
        Full results and limits
      </a>
    </section>
  );
}
