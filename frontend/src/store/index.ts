import { create } from "zustand";
import type { Run } from "@/lib/api";

type HiveStore = {
  activeRunId: string | null;
  setActiveRunId: (id: string | null) => void;
  runs: Run[];
  setRuns: (runs: Run[]) => void;
  upsertRun: (run: Run) => void;
};

export const useHiveStore = create<HiveStore>((set) => ({
  activeRunId: null,
  setActiveRunId: (id) => set({ activeRunId: id }),
  runs: [],
  setRuns: (runs) => set({ runs }),
  upsertRun: (run) =>
    set((state) => {
      const idx = state.runs.findIndex((r) => r.id === run.id);
      if (idx === -1) return { runs: [run, ...state.runs] };
      const next = [...state.runs];
      next[idx] = run;
      return { runs: next };
    }),
}));
