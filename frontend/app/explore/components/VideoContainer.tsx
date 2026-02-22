"use client"

import { forwardRef, type RefObject, useState, useEffect } from "react"
import { SkipForward } from "lucide-react"
import { PropositionsWithAnalysis } from "../stores/useExploreStore"
import { PropositionPopup, FacialConfidencePopup } from "./ConfidencePopup"
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
    const [controlsVisible, setControlsVisible] = useState(true)
    const [hideTimeout, setHideTimeout] = useState<NodeJS.Timeout | null>(null)

    const handleMouseMove = () => {
      setControlsVisible(true)
      if (hideTimeout) clearTimeout(hideTimeout)
      const timeout = setTimeout(() => setControlsVisible(false), 2000)
      setHideTimeout(timeout)
    }

    const handleMouseLeave = () => {
      if (hideTimeout) clearTimeout(hideTimeout)
      const timeout = setTimeout(() => setControlsVisible(false), 500)
      setHideTimeout(timeout)
    }

    useEffect(() => {
      return () => {
        if (hideTimeout) clearTimeout(hideTimeout)
      }
    }, [hideTimeout])

    return (
      <div
        ref={containerRef}
        className="relative flex-1 rounded-lg border aspect-video min-w-0 self-start"
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      >
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
        {activeProposition && (
          <FacialConfidencePopup
            proposition={activeProposition}
            visible={popupVisible}
            controlsVisible={controlsVisible}
          />
        )}
        {hasPropositions && (
          <button
            onClick={onJumpNext}
            className={`absolute duration-500 ease-in-out z-10 ${controlsVisible ? 'bottom-16' : 'bottom-4'} left-1/2 -translate-x-1/2 flex items-center gap-1.5 rounded-full bg-black/25 px-4 py-1.5 text-xs font-medium text-white backdrop-blur-sm border border-white/20 hover:bg-black/80 transition-all`}
          >
            <SkipForward className="size-3.5 duration-500" />
            Jump to next
          </button>
        )}
      </div>
    )
  },
)
