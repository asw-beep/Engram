import BuildLog from "@/components/landing/BuildLog";
import Closing from "@/components/landing/Closing";
import Hero from "@/components/landing/Hero";
import Nav from "@/components/landing/Nav";
import Problem from "@/components/landing/Problem";
import System from "@/components/landing/System";
import Ticker from "@/components/landing/Ticker";
import { GITHUB_URL, PHASES, RULES, SOURCE_TYPES, STORES } from "@/lib/system";

import "./landing.css";

export default function LandingPage() {
  return (
    <>
      <Nav githubUrl={GITHUB_URL} />
      <main className="landing">
        <Hero githubUrl={GITHUB_URL} phases={PHASES} />
        <Ticker types={SOURCE_TYPES} />
        <Problem />
        <System stores={STORES} rules={RULES} />
        <BuildLog phases={PHASES} />
      </main>
      <Closing githubUrl={GITHUB_URL} />
    </>
  );
}
