"use client";

import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { type ElementType, type ReactNode, useRef } from "react";

import { useReducedMotion } from "@/components/motion/useReducedMotion";

gsap.registerPlugin(ScrollTrigger);

/**
 * Fade content up as it scrolls into view. The content is rendered visible, and the hidden
 * starting state is set from JavaScript, so it shows without animation too.
 */
export default function Reveal({
  as: Tag = "div",
  delay = 0,
  className,
  children,
}: {
  as?: ElementType;
  delay?: number;
  className?: string;
  children: ReactNode;
}) {
  const element = useRef<HTMLElement>(null);
  const reduced = useReducedMotion();

  useGSAP(
    () => {
      if (reduced || !element.current) return;
      gsap.from(element.current, {
        y: 24,
        autoAlpha: 0,
        duration: 0.7,
        delay,
        ease: "power3.out",
        scrollTrigger: { trigger: element.current, start: "top 85%" },
      });
    },
    { dependencies: [reduced, delay] },
  );

  return (
    <Tag ref={element} className={className}>
      {children}
    </Tag>
  );
}
