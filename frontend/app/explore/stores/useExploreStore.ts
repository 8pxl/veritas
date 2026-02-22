import { create } from "zustand";
import type { Video, Proposition, Person } from "@/lib/client/types.gen";

interface ExploreState {
  selectedVideo: Video | null;
  selectedPerson: Person | null;
  selectedOrgName: string | null;
  propositions: Proposition[];
  selectVideo: (video: Video, person: Person, orgName: string, propositions: Proposition[]) => void;
  clearSelection: () => void;
}

export const useExploreStore = create<ExploreState>((set) => ({
  selectedVideo: null,
  selectedPerson: null,
  selectedOrgName: null,
  propositions: [],
  selectVideo: (video, person, orgName, propositions) =>
    set({ selectedVideo: video, selectedPerson: person, selectedOrgName: orgName, propositions }),
  clearSelection: () =>
    set({ selectedVideo: null, selectedPerson: null, selectedOrgName: null, propositions: [] }),
}));
