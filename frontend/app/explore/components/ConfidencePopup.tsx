"use client"

import { useEffect, useState, useRef } from "react"
import { AlertTriangle } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { Proposition } from "@/lib/client/types.gen"

function Typewriter({ text, speed = 25 }: { text: string; speed?: number }) {
  const [displayed, setDisplayed] = useState("")
  const indexRef = useRef(0)

  useEffect(() => {
    setDisplayed("")
    indexRef.current = 0

    const interval = setInterval(() => {
      indexRef.current++
      if (indexRef.current <= text.length) {
        setDisplayed(text.slice(0, indexRef.current))
      } else {
        clearInterval(interval)
      }
    }, speed)

    return () => clearInterval(interval)
  }, [text, speed])

  return (
    <>
      {displayed}
      {displayed.length < text.length && (
        <span className="inline-block w-px h-3 bg-white/60 animate-pulse ml-px align-baseline" />
      )}
    </>
  )
}

interface PropositionPopupProps {
  proposition: Proposition
  visible: boolean
  onDismiss: () => void
}

export function PropositionPopup({ proposition, visible, onDismiss }: PropositionPopupProps) {
  const [animState, setAnimState] = useState<"entering" | "visible" | "exiting" | "hidden">("hidden")

  useEffect(() => {
    if (visible) {
      // Start entering
      setAnimState("entering")
      const frame = requestAnimationFrame(() => {
        setAnimState("visible")
      })
      return () => cancelAnimationFrame(frame)
    } else {
      // Start exit animation
      setAnimState("exiting")
      const timer = setTimeout(() => {
        setAnimState("hidden")
      }, 500) // match exit transition duration
      return () => clearTimeout(timer)
    }
  }, [visible])

  if (animState === "hidden") return null

  const show = animState === "visible"

  return (
    <div className={`absolute right-4 top-4 z-20 w-80 transition-all duration-500 ease-in-out ${show ? "translate-y-0 opacity-100" : "-translate-y-4 opacity-0 pointer-events-none"}`}>
      <Card className="border-white/10 bg-black/70 text-white backdrop-blur-xl shadow-2xl py-4 gap-3">
        <CardHeader className="pb-0">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="size-4 text-yellow-400" />
              <CardTitle className="text-sm">Verify Claim</CardTitle>
            </div>
            <button onClick={onDismiss} className="text-white/40 hover:text-white/80 transition-colors text-xs leading-none">
              &#x2715;
            </button>
          </div>
        </CardHeader>

        <CardContent className="flex flex-col gap-3">
          {/* Speaker info */}
          <div className="flex items-baseline gap-2">
            <span className="text-sm font-semibold">{proposition.speaker.name}</span>
            {proposition.speaker.position && (
              <span className="text-xs text-white/50">{proposition.speaker.position}</span>
            )}
          </div>

          {/* Timestamp */}
          <div className="text-xs text-white/40">
            at {proposition.verifyAt}
          </div>

          {/* Statement with typewriter */}
          <p className="text-xs italic text-white/70 leading-relaxed border-l-2 border-white/20 pl-2 min-h-[2.5em]">
            &ldquo;<Typewriter text={proposition.statement} />&rdquo;
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
