"use client";

import { startTransition } from "react";
import { gsap } from "gsap";
import { TransitionRouter } from "next-transition-router";
import TransitionLayer from "./transition";
import Tabbar from "./tabbar";
import { useWindowSize } from "@uidotdev/usehooks";


export default function Providers({ children }: { children: React.ReactNode }) {
  const { width, height } = useWindowSize();
  const diagonal = Math.sqrt((width ?? 0) ** 2 + (height ?? 0) ** 2)
  const numCircles = 3;
  const wipeDir = 0.7;
  const staggerOffset = 0.54;
  return (
    <TransitionRouter
      auto={true}

      leave={(next) => {
        const tl = gsap.timeline({});
        tl
          .to("#transitionCircle1", { width: diagonal, height: diagonal, duration: wipeDir })
          .to("#transitionCircle2", { width: diagonal, height: diagonal, duration: wipeDir }, `-=${staggerOffset}`)
          .fromTo("#transitionRing",
            { outlineWidth: "0px" },
            { outlineWidth: `${diagonal / 2.0}px`, duration: wipeDir }, `-=${staggerOffset}`
          )
          .set("#transitionRing", { background: "none" })
          .call(() => {
            requestAnimationFrame(() => startTransition(next));
          }, undefined, wipeDir);
        // return () => tl.kill();
      }}
      enter={(next) => {
        const tl = gsap.timeline({ onComplete: next });
        tl
          .set("#transitionCircle1", {
            width: 0, height: 0, delay: (numCircles - 1) * (wipeDir - staggerOffset)
          })
          .set("#transitionCircle2", { width: 0, height: 0 })
          .to("#transitionRing", { width: diagonal, height: diagonal, duration: 0.7 })
          .to("#transitionRing", { outlineWidth: "0px", duration: 0.7 })
          .set("#transitionRing", { width: "1px", height: 1 });
        return () => tl.kill();
      }}
    >
      <main>{children}</main>
      <TransitionLayer />

    </TransitionRouter >
  );
}
