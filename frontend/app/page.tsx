import BuildLog from "@/components/landing/BuildLog";
import Closing from "@/components/landing/Closing";
import Hero from "@/components/landing/Hero";
import LandingMotion, { PENDING_SCRIPT } from "@/components/landing/LandingMotion";
import Nav from "@/components/landing/Nav";
import Pipeline from "@/components/landing/Pipeline";
import Problem from "@/components/landing/Problem";
import Specimen from "@/components/landing/Specimen";
import System from "@/components/landing/System";
import Ticker from "@/components/landing/Ticker";
import SmoothScroll from "@/components/motion/SmoothScroll";
import {
  GITHUB_URL,
  INGESTION_STAGES,
  PHASES,
  QUERY_STAGES,
  RULES,
  SAMPLE,
  SOURCE_TYPES,
  STORES,
} from "@/lib/system";

import "./landing.css";

export default function LandingPage() {
  return (
    <SmoothScroll>
      <script dangerouslySetInnerHTML={{ __html: PENDING_SCRIPT }} />
      <LandingMotion />
      <Nav githubUrl={GITHUB_URL} />
      <main className="landing">
        <Hero githubUrl={GITHUB_URL} phases={PHASES} />
        <Ticker types={SOURCE_TYPES} />
        <Problem />
        <Pipeline ingestion={INGESTION_STAGES} query={QUERY_STAGES} />
        <Specimen sample={SAMPLE} />
        <System stores={STORES} rules={RULES} />
        <BuildLog phases={PHASES} />
      </main>
      <Closing githubUrl={GITHUB_URL} />
    </SmoothScroll>
  );
}
