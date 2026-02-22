"use client"

import { forwardRef, type RefObject } from "react"
import { SkipForward } from "lucide-react"
import { PropositionsWithAnalysis } from "../stores/useExploreStore"
import { PropositionPopup } from "./ConfidencePopup"
import { AudioEmotionOverlay } from "./AudioEmotionOverlay"

interface VideoContainerProps {
  containerRef?: RefObject<HTMLDivElement | null>
  videoId: string
  videoUrl: string
  activeProposition: PropositionsWithAnalysis | null
  popupVisible: boolean
  hasPropositions: boolean
  onTimeUpdate: () => void
  onSeeked: () => void
  onPause: () => void
  onPlay: () => void
  onDismiss: () => void
  onJumpNext: () => void
}

export const VideoContainer = forwardRef<HTMLVideoElement, VideoContainerProps>(
  function VideoContainer(
    {
      containerRef,
      videoId,
      videoUrl,
      activeProposition,
      popupVisible,
      hasPropositions,
      onTimeUpdate,
      onSeeked,
      onPause,
      onPlay,
      onDismiss,
      onJumpNext,
    },
    ref,
  ) {
    return (
      <div ref={containerRef} className="relative flex-1 rounded-lg border aspect-video min-w-0 self-start">
        <video
          ref={ref}
          key={videoId}
          src={videoUrl}
          controls
          className="h-full w-full rounded-lg"
          disablePictureInPicture
          onTimeUpdate={onTimeUpdate}
          onSeeked={onSeeked}
          onPause={onPause}
          onPlay={onPlay}
        />
        {activeProposition && (
          <PropositionPopup
            proposition={activeProposition}
            visible={popupVisible}
            onDismiss={onDismiss}
          />
        )}
        {activeProposition && (
          <AudioEmotionOverlay
            proposition={activeProposition}
            visible={popupVisible}
            videoRef={ref as React.RefObject<HTMLVideoElement>}
          />
        )}
        {hasPropositions && (
          <button
            onClick={onJumpNext}
            className="absolute z-1 bottom-12 left-1/2 -translate-x-1/2 flex items-center gap-1.5 rounded-full bg-black/60 px-4 py-1.5 text-xs font-medium text-white backdrop-blur-sm border border-white/20 hover:bg-black/80 transition-colors z-10"
          >
            <SkipForward className="size-3.5" />
            Jump to next statement
          </button>
        )}
      </div>
    )
  },
)
