"use client"

import { forwardRef } from "react"
import { PropositionsWithAnalysis } from "../stores/useExploreStore"
import { parseTimestamp, formatTimestamp } from "./videoPlayerUtils"

interface TimestampSidebarProps {
  propositions: PropositionsWithAnalysis[]
  activeProposition: PropositionsWithAnalysis | null
  onJumpTo: (prop: PropositionsWithAnalysis) => void
}

export const TimestampSidebar = forwardRef<HTMLDivElement, TimestampSidebarProps>(
  function TimestampSidebar({ propositions, activeProposition, onJumpTo }, ref) {
    return (
      <div
        ref={ref}
        className="w-48 shrink-0 flex flex-col rounded-lg border overflow-hidden self-start"
      >
        <div className="flex-1 overflow-y-auto divide-y divide-border flex flex-col">
          {propositions.map((prop) => {
            const timeLabel = formatTimestamp(parseTimestamp(prop.start))
            const verdict = prop.verdict?.toLowerCase()
            const isActive = prop.start === activeProposition?.start

            return (
              <button
                key={`${prop.id}-${prop.start}`}
                ref={isActive ? (el) => el?.scrollIntoView({ block: "nearest", behavior: "smooth" }) : undefined}
                onClick={() => onJumpTo(prop)}
                className={`flex items-start gap-2 px-3 py-2.5 text-left transition-all shrink-0 ${
                  isActive
                    ? "bg-accent/15 border-l-4 border-accent pl-2"
                    : "hover:bg-muted/50 border-l-4 border-transparent pl-2"
                }`}
              >
                <span
                  className={`shrink-0 text-[10px] font-mono w-8 pt-0.5 ${
                    isActive ? "text-accent font-bold" : "text-muted-foreground"
                  }`}
                >
                  {timeLabel}
                </span>
                <div className="flex flex-col gap-0.5 min-w-0 flex-1">
                  <span
                    className={`text-xs leading-snug line-clamp-2 ${
                      isActive ? "text-accent font-semibold" : "text-foreground"
                    }`}
                  >
                    {prop.statement}
                  </span>
                  <span className="text-[10px] text-muted-foreground">
                    {prop.speaker?.name ?? "Unknown"}
                  </span>
                </div>
                {verdict && (
                  <span
                    className={`shrink-0 text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                      verdict === "true"
                        ? "bg-green-500/15 text-green-600"
                        : verdict === "false"
                          ? "bg-red-500/15 text-red-600"
                          : "bg-yellow-500/15 text-yellow-600"
                    }`}
                  >
                    {verdict === "true" ? "\u2713" : verdict === "false" ? "\u2717" : "?"}
                  </span>
                )}
              </button>
            )
          })}
        </div>
      </div>
    )
  },
)
