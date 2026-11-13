import type { Status } from "@/lib/system";

/** The word "planned" beside a part that isn't built yet. Live parts get no tag. */
export default function StatusTag({ status }: { status: Status }) {
  if (status === "live") return null;
  return <span className="status-tag">planned</span>;
}
