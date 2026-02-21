"use client"
import { Link as TransitionLink } from "next-transition-router";
import { ReactNode, useRef } from "react";

interface TabProps {
  children: ReactNode
}

export default function Tabbar() {
  return (
    <div >
      <nav>
        <TransitionLink href="/">about</TransitionLink>
        <TransitionLink href="/explore">explore</TransitionLink>
        <TransitionLink href="/vis">vis</TransitionLink>
      </nav>
    </div >
  )
}
