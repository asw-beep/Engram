"use client";

import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger);

const PENDING = "motion-pending";

/**
 * Runs before the page paints, so the hero doesn't flash before its entrance. It hides the
 * hero only when motion is allowed, and gives up after three seconds if the app never loads.
 */
export const PENDING_SCRIPT = `(function(){try{if(matchMedia("(prefers-reduced-motion: reduce)").matches)return;var c=document.documentElement.classList;c.add("${PENDING}");setTimeout(function(){c.remove("${PENDING}")},3000)}catch(e){}})()`;

const STAGES = 10;

/** All scroll and load animation for the landing page. Renders nothing. */
export default function LandingMotion() {
  useGSAP(() => {
    const media = gsap.matchMedia();
    media.add(
      {
        motion: "(prefers-reduced-motion: no-preference)",
        wide: "(min-width: 52.01rem)",
        pointer: "(hover: hover) and (pointer: fine)",
      },
      (context) => {
        const { motion, wide, pointer } = context.conditions as Record<string, boolean>;
        document.documentElement.classList.remove(PENDING);
        if (!motion) return;

        // Hero entrance.
        const intro = gsap.timeline({ defaults: { ease: "power4.out" } });
        intro
          .from('[data-anim="hero-line"]', { yPercent: 115, duration: 1.1, stagger: 0.09 }, 0.1)
          .from(
            ".hero-kicker, .hero-lede, .hero-actions",
            { autoAlpha: 0, y: 18, duration: 0.8, stagger: 0.08 },
            0.5,
          )
          .from('.qd [data-anim="node"]', { autoAlpha: 0, y: 14, duration: 0.5, stagger: 0.14 }, 0.5)
          .from('.qd [data-anim="wire"]', { scaleY: 0, duration: 0.4, stagger: 0.14, ease: "power2.out" }, 0.64)
          .from(".qd figcaption, .title-block", { autoAlpha: 0, duration: 0.6 }, 1.1);

        // The problem statement fills in word by word.
        gsap.fromTo(
          '[data-anim="problem-word"]',
          { opacity: 0.16 },
          {
            opacity: 1,
            ease: "none",
            stagger: 0.05,
            scrollTrigger: { trigger: ".problem-text", start: "top 80%", end: "bottom 65%", scrub: true },
          },
        );

        // Section headings, cards and phases rise in as they arrive.
        for (const selector of [
          ".l-section .section-label, .l-section .section-title, .l-section .section-lede",
          '[data-anim="card"]',
          ".bl-phase",
        ]) {
          gsap.set(selector, { autoAlpha: 0, y: 28 });
          ScrollTrigger.batch(selector, {
            start: "top 90%",
            once: true,
            onEnter: (batch) =>
              gsap.to(batch, { autoAlpha: 1, y: 0, duration: 0.7, stagger: 0.08, ease: "power3.out" }),
          });
        }

        gsap.from('[data-anim="build-line"]', {
          scaleX: 0,
          duration: 1.3,
          ease: "power3.inOut",
          scrollTrigger: { trigger: ".bl-rail", start: "top 85%" },
        });

        gsap.from('[data-anim="closing-type"]', {
          scale: 0.8,
          yPercent: 18,
          ease: "none",
          scrollTrigger: { trigger: ".closing", start: "top 95%", end: "top 25%", scrub: true },
        });

        if (wide) pinPipeline();
        if (wide && pointer) return magnet();
      },
    );
    return () => media.revert();
  });

  return null;
}

/** Hold the pipeline in place and step through its stages as the visitor scrolls. */
function pinPipeline() {
  const section = document.querySelector<HTMLElement>(".pipeline");
  const body = section?.querySelector<HTMLElement>(".pl-body");
  if (!section || !body) return;
  const buttons = [...section.querySelectorAll<HTMLButtonElement>("[data-stage-index]")];
  // Pin the whole section when it fits the window, otherwise only the stages.
  const fits = section.offsetHeight <= window.innerHeight;
  let current = 0;
  ScrollTrigger.create({
    trigger: fits ? section : body,
    start: fits ? "top top" : "center center",
    end: `+=${STAGES * 180}`,
    pin: true,
    onUpdate: (self) => {
      const index = Math.min(STAGES - 1, Math.floor(self.progress * STAGES));
      if (index === current) return;
      current = index;
      buttons[index]?.click();
    },
  });
}

/** The closing button leans toward the cursor. Returns its cleanup. */
function magnet() {
  const area = document.querySelector<HTMLElement>(".closing-actions");
  const button = area?.querySelector<HTMLElement>('[data-anim="magnet"]');
  if (!area || !button) return;
  const moveX = gsap.quickTo(button, "x", { duration: 0.4, ease: "power3.out" });
  const moveY = gsap.quickTo(button, "y", { duration: 0.4, ease: "power3.out" });
  function onMove(event: PointerEvent) {
    const box = button!.getBoundingClientRect();
    const dx = event.clientX - (box.left + box.width / 2);
    const dy = event.clientY - (box.top + box.height / 2);
    const near = Math.abs(dx) < box.width && Math.abs(dy) < box.height * 1.5;
    moveX(near ? dx * 0.3 : 0);
    moveY(near ? dy * 0.3 : 0);
  }
  function onLeave() {
    moveX(0);
    moveY(0);
  }
  area.addEventListener("pointermove", onMove);
  area.addEventListener("pointerleave", onLeave);
  return () => {
    area.removeEventListener("pointermove", onMove);
    area.removeEventListener("pointerleave", onLeave);
  };
}
