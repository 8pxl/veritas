"use client"

import { useRef, useLayoutEffect, useState, useCallback } from "react"
import Tabbar from "../components/shared/tabbar"
import Leaderboard from "./leaderboard"
import Graph from "./graph"
import NetworkGraph from "./NetworkGraph"
import Logo from "../components/shared/logo"

const views = [
  { label: "graph" },
  { label: "leaderboard" },
  { label: "network" },
]

export default function VisPage() {
  const navRef = useRef<HTMLDivElement>(null)
  const [activeIndex, setActiveIndex] = useState(0)
  const [bubbleStyle, setBubbleStyle] = useState<{ left: number; width: number }>({ left: 0, width: 0 })
  const initialRef = useRef(true)

  const updateBubble = useCallback((index: number, animate: boolean) => {
    if (!navRef.current) return
    const buttons = navRef.current.querySelectorAll<HTMLElement>("[data-tab]")
    const target = buttons[index]
    if (!target) return

    const navRect = navRef.current.getBoundingClientRect()
    const targetRect = target.getBoundingClientRect()

    if (!animate) {
      const bubble = navRef.current.querySelector<HTMLElement>("[data-bubble]")
      if (bubble) {
        bubble.style.transition = "none"
        requestAnimationFrame(() => {
          bubble.style.transition = ""
        })
      }
    }

    setBubbleStyle({
      left: targetRect.left - navRect.left,
      width: targetRect.width,
    })
  }, [])

  useLayoutEffect(() => {
    updateBubble(activeIndex, false)
    initialRef.current = false
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleClick = (index: number) => {
    if (index === activeIndex) return
    setActiveIndex(index)
    updateBubble(index, true)
  }

  return (
    <main className="min-h-screen px-6 pt-20 pb-12">
      <Tabbar />
      <Logo />

      <div className="w-full">

        <div className="mb-8 flex justify-center">
          <div
            ref={navRef}
            className="relative flex items-center gap-1 rounded-full bg-foreground/5 p-1 backdrop-blur-sm"
          >
            <div
              data-bubble
              className="absolute top-1 bottom-1 rounded-full bg-accent transition-all duration-600 ease-in-out"
              style={{
                left: bubbleStyle.left,
                width: bubbleStyle.width,
              }}
            />
            {views.map((view, i) => (
              <button
                key={view.label}
                data-tab
                onClick={() => handleClick(i)}
                className={`relative z-10 rounded-full px-4 py-1.5 text-sm font-medium transition-colors duration-300 ${i === activeIndex
                  ? "text-background"
                  : "text-muted-foreground hover:text-foreground"
                  }`}
              >
                {view.label}
              </button>
            ))}
          </div>
        </div>


        <div className="mt-8">
          {activeIndex === 0 && <Graph />}
          {activeIndex === 1 && <Leaderboard />}
          {activeIndex === 2 && <NetworkGraph />}
        </div>

      </div>

    </main>
  )
}
