"use client"

import { Link as TransitionLink } from "next-transition-router"
import { usePathname } from "next/navigation"
import { useRef, useLayoutEffect, useState, useCallback } from "react"

const tabs = [
  { label: "about", href: "/" },
  { label: "explore", href: "/explore" },
  { label: "visualize", href: "/vis" },
]

function getIndexFromPathname(pathname: string) {
  return tabs.findIndex(
    (tab) => tab.href === "/" ? pathname === "/" : pathname.startsWith(tab.href)
  )
}

export default function Tabbar() {
  const pathname = usePathname()
  const navRef = useRef<HTMLDivElement>(null)
  const [activeIndex, setActiveIndex] = useState(() => getIndexFromPathname(pathname))
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
      // Suppress transition for initial positioning
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

  // Position bubble on mount without animation
  useLayoutEffect(() => {
    const index = getIndexFromPathname(pathname)
    setActiveIndex(index)
    updateBubble(index, false)
    initialRef.current = false
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Sync if pathname changes externally (e.g. browser back/forward)
  useLayoutEffect(() => {
    if (initialRef.current) return
    const index = getIndexFromPathname(pathname)
    if (index !== activeIndex) {
      setActiveIndex(index)
      updateBubble(index, true)
    }
  }, [pathname]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleClick = (index: number) => {
    if (index === activeIndex) return
    setActiveIndex(index)
    updateBubble(index, true)
  }

  return (
    <div className="fixed top-4 right-4 z-50">
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
        {tabs.map((tab, i) => (
          <TransitionLink
            key={tab.href}
            href={tab.href}
            data-tab
            onClick={() => handleClick(i)}
            className={`relative z-10 rounded-full px-4 py-1.5 text-sm font-medium transition-colors duration-300 ${i === activeIndex ? "text-background" : "text-muted-foreground hover:text-foreground"}`}
          >
            {tab.label}
          </TransitionLink>
        ))}
      </div>
    </div>
  )
}
