import { create } from "zustand";
import type { Video } from "@/app/types";

interface ExploreState {
  selectedVideo: Video | null;
  selectedPersonName: string | null;
  selectedCompanyName: string | null;
  selectVideo: (video: Video, personName: string, companyName: string) => void;
  clearSelection: () => void;
}

export const useExploreStore = create<ExploreState>((set) => ({
  selectedVideo: null,
  selectedPersonName: null,
  selectedCompanyName: null,
  selectVideo: (video, personName, companyName) =>
    set({ selectedVideo: video, selectedPersonName: personName, selectedCompanyName: companyName }),
  clearSelection: () =>
    set({ selectedVideo: null, selectedPersonName: null, selectedCompanyName: null }),
}));
