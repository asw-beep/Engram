import StatusTag from "@/components/landing/StatusTag";
import type { Rule, Store } from "@/lib/system";

export default function System({ stores, rules }: { stores: Store[]; rules: Rule[] }) {
  return (
    <section id="system" className="l-section system">
      <p className="label section-label">04 — System</p>
      <h2 className="section-title">Five stores, three rules.</h2>
      <p className="section-lede">
        PostgreSQL is the record of truth. Everything else is a projection that can be rebuilt from
        it, and three rules hold across every component.
      </p>
      <ul className="store-grid" aria-label="Data stores">
        {stores.map((store) => (
          <li key={store.name} className={store.status === "planned" ? "card planned" : "card"} data-anim="card">
            <span className="card-head">
              <span className="label">{store.name}</span>
              <StatusTag status={store.status} />
            </span>
            <span className="card-text">{store.role}</span>
          </li>
        ))}
      </ul>
      <ul className="rule-grid" aria-label="Rules">
        {rules.map((rule) => (
          <li key={rule.id} className="card rule" data-anim="card">
            <span className="label rule-id">Rule {rule.id}</span>
            <h3 className="rule-title">{rule.title}</h3>
            <p className="card-text">{rule.text}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
