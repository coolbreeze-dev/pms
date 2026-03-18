import type { ReadswellState } from "./data";

const STORAGE_KEY = "readswell-mvp-state-v1";

function nowIso() {
  return new Date().toISOString();
}

function createActivity(label: string, timestamp = nowIso()) {
  return {
    id: `${timestamp}-${Math.round(Math.random() * 10_000)}`,
    label,
    timestamp,
  };
}

export function createDefaultState(): ReadswellState {
  return {
    profile: {
      name: "Avery",
      moods: ["atmospheric", "hopeful", "introspective"],
      tropes: ["quiet fantasy", "slow burn", "found family"],
      pace: "slow",
      prose: "lyrical",
    },
    library: {
      piranesi: {
        status: "read",
        ratingOverall: 5,
        moodScore: 5,
        paceScore: 2,
        progress: 100,
        imported: false,
        updatedAt: nowIso(),
      },
      "night-circus": {
        status: "read",
        ratingOverall: 4,
        moodScore: 5,
        paceScore: 2,
        progress: 100,
        imported: false,
        updatedAt: nowIso(),
      },
      "gentleman-moscow": {
        status: "currently_reading",
        ratingOverall: 0,
        moodScore: 4,
        paceScore: 2,
        progress: 42,
        imported: false,
        updatedAt: nowIso(),
      },
      "thursday-murder-club": {
        status: "want_to_read",
        ratingOverall: 0,
        moodScore: 3,
        paceScore: 3,
        progress: 0,
        imported: false,
        updatedAt: nowIso(),
      },
    },
    importReport: null,
    activity: [
      createActivity("Rated Piranesi 5 stars and logged it as read."),
      createActivity("Started A Gentleman in Moscow and set progress to 42%."),
      createActivity("Saved The Thursday Murder Club to Want to Read."),
    ],
  };
}

export function loadState(): ReadswellState {
  if (typeof window === "undefined") {
    return createDefaultState();
  }

  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return createDefaultState();
  }

  try {
    const parsed = JSON.parse(raw) as ReadswellState;
    return {
      ...createDefaultState(),
      ...parsed,
      profile: {
        ...createDefaultState().profile,
        ...parsed.profile,
      },
      library: parsed.library ?? {},
      activity: parsed.activity ?? [],
      importReport: parsed.importReport ?? null,
    };
  } catch {
    return createDefaultState();
  }
}

export function saveState(state: ReadswellState) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

export function resetState() {
  const fresh = createDefaultState();
  saveState(fresh);
  return fresh;
}
