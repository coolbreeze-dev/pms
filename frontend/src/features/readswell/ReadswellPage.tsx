import {
  startTransition,
  useDeferredValue,
  useEffect,
  useState,
  type ChangeEvent,
  type CSSProperties,
} from "react";

import {
  BOOKS,
  DEMO_GOODREADS_CSV,
  MOOD_OPTIONS,
  PACE_OPTIONS,
  PROSE_OPTIONS,
  SEARCH_PROMPTS,
  TROPE_OPTIONS,
  type ActivityItem,
  type Book,
  type LibraryEntry,
  type ReadswellState,
  type ShelfStatus,
} from "./data";
import {
  formatTimestamp,
  getDashboardStats,
  getFingerprintBars,
  getRecommendations,
  groupLibraryByStatus,
  importGoodreadsCsv,
  searchCatalog,
  statusLabels,
  type RankedBook,
} from "./logic";
import { loadState, resetState, saveState } from "./storage";
import "./readswell.css";

const statusOrder: ShelfStatus[] = ["want_to_read", "currently_reading", "read", "dnf"];
const THEME_STORAGE_KEY = "readswell-mvp-theme-v1";

const themeOptions = [
  {
    id: "crimson-noir",
    name: "Crimson Noir",
    note: "Red, black, and parchment with a sharper literary feel.",
    swatches: ["#1a1515", "#bc2f2f", "#f6efe4"],
  },
  {
    id: "mustard-room",
    name: "Mustard Room",
    note: "Mustard, espresso, and cream with warmer studio energy.",
    swatches: ["#d0a12a", "#35251c", "#fbf4df"],
  },
  {
    id: "signal-white",
    name: "Signal White",
    note: "Bold #E22725-inspired red on white with crisp contrast.",
    swatches: ["#e22725", "#ffffff", "#171717"],
  },
] as const;

type ThemeId = (typeof themeOptions)[number]["id"];

function loadTheme(): ThemeId {
  if (typeof window === "undefined") {
    return "crimson-noir";
  }

  const saved = window.localStorage.getItem(THEME_STORAGE_KEY);
  if (saved && themeOptions.some((theme) => theme.id === saved)) {
    return saved as ThemeId;
  }

  return "crimson-noir";
}

function createActivity(label: string): ActivityItem {
  const timestamp = new Date().toISOString();
  return {
    id: `${timestamp}-${Math.round(Math.random() * 100_000)}`,
    label,
    timestamp,
  };
}

function addActivity(state: ReadswellState, label: string): ReadswellState {
  return {
    ...state,
    activity: [createActivity(label), ...state.activity].slice(0, 10),
  };
}

function clampProgress(value: number) {
  return Math.max(0, Math.min(100, value));
}

function createOrMergeEntry(existing: LibraryEntry | undefined, patch: Partial<LibraryEntry>): LibraryEntry {
  return {
    status: existing?.status ?? "want_to_read",
    ratingOverall: existing?.ratingOverall ?? 0,
    moodScore: existing?.moodScore ?? 3,
    paceScore: existing?.paceScore ?? 3,
    progress: existing?.progress ?? 0,
    imported: existing?.imported ?? false,
    updatedAt: existing?.updatedAt ?? new Date().toISOString(),
    ...patch,
  };
}

function ToneChips({
  title,
  options,
  selected,
  onToggle,
}: {
  title: string;
  options: readonly string[];
  selected: string[];
  onToggle: (value: string) => void;
}) {
  return (
    <div className="readswell__chip-group">
      <p className="readswell__label">{title}</p>
      <div className="readswell__pill-row">
        {options.map((option) => {
          const isSelected = selected.includes(option);
          return (
            <button
              key={option}
              type="button"
              className={`readswell__pill${isSelected ? " readswell__pill--active" : ""}`}
              onClick={() => onToggle(option)}
            >
              {option}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function BookCard({
  result,
  entry,
  onStatusChange,
  onRatingChange,
  onProgressChange,
}: {
  result: RankedBook;
  entry?: LibraryEntry;
  onStatusChange: (bookId: string, status: ShelfStatus) => void;
  onRatingChange: (bookId: string, field: "ratingOverall" | "moodScore" | "paceScore", value: number) => void;
  onProgressChange: (bookId: string, value: number) => void;
}) {
  const { book, why, matchedTraits } = result;
  const coverStyle = {
    "--cover-start": book.cover.start,
    "--cover-end": book.cover.end,
  } as CSSProperties;

  return (
    <article className="readswell-card">
      <div className="readswell-card__cover" style={coverStyle}>
        <span>{book.title}</span>
      </div>
      <div className="readswell-card__body">
        <p className="readswell-card__meta">
          {book.author} . {book.year}
        </p>
        <h3>{book.title}</h3>
        <p className="readswell-card__copy">{book.description}</p>
        <div className="readswell-card__tags">
          {matchedTraits.slice(0, 3).map((trait) => (
            <span key={trait} className="readswell-card__tag">
              {trait}
            </span>
          ))}
          <span className="readswell-card__tag readswell-card__tag--soft">{book.pace}</span>
          <span className="readswell-card__tag readswell-card__tag--soft">{book.prose}</span>
        </div>
        <p className="readswell-card__why">{why}</p>
        <div className="readswell-card__actions">
          {statusOrder.map((status) => (
            <button
              key={status}
              type="button"
              className={`readswell-card__action${entry?.status === status ? " readswell-card__action--active" : ""}`}
              onClick={() => onStatusChange(book.id, status)}
            >
              {statusLabels[status]}
            </button>
          ))}
        </div>
        {entry ? (
          <div className="readswell-card__controls">
            <label>
              Overall
              <select
                value={entry.ratingOverall}
                onChange={(event) => onRatingChange(book.id, "ratingOverall", Number(event.target.value))}
              >
                {[0, 1, 2, 3, 4, 5].map((value) => (
                  <option key={value} value={value}>
                    {value === 0 ? "No rating" : `${value} stars`}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Mood fit
              <input
                type="range"
                min="1"
                max="5"
                value={entry.moodScore}
                onChange={(event) => onRatingChange(book.id, "moodScore", Number(event.target.value))}
              />
            </label>
            <label>
              Pace fit
              <input
                type="range"
                min="1"
                max="5"
                value={entry.paceScore}
                onChange={(event) => onRatingChange(book.id, "paceScore", Number(event.target.value))}
              />
            </label>
            {entry.status === "currently_reading" ? (
              <label className="readswell-card__progress">
                Progress
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={entry.progress}
                  onChange={(event) => onProgressChange(book.id, Number(event.target.value))}
                />
                <span>{entry.progress}%</span>
              </label>
            ) : null}
          </div>
        ) : null}
      </div>
    </article>
  );
}

function ShelfColumn({
  label,
  entries,
  onStatusChange,
  onProgressChange,
}: {
  label: string;
  entries: Array<[string, LibraryEntry]>;
  onStatusChange: (bookId: string, status: ShelfStatus) => void;
  onProgressChange: (bookId: string, value: number) => void;
}) {
  return (
    <section className="readswell-shelf">
      <div className="readswell-shelf__header">
        <h3>{label}</h3>
        <span>{entries.length}</span>
      </div>
      {entries.length ? (
        <div className="readswell-shelf__list">
          {entries.map(([bookId, entry]) => {
            const book = BOOKS.find((candidate) => candidate.id === bookId);
            if (!book) {
              return null;
            }

            return (
              <article key={bookId} className="readswell-shelf__item">
                <div>
                  <p className="readswell-shelf__title">{book.title}</p>
                  <p className="readswell-shelf__meta">{book.author}</p>
                </div>
                <div className="readswell-shelf__controls">
                  <select
                    value={entry.status}
                    onChange={(event) => onStatusChange(book.id, event.target.value as ShelfStatus)}
                  >
                    {statusOrder.map((status) => (
                      <option key={status} value={status}>
                        {statusLabels[status]}
                      </option>
                    ))}
                  </select>
                  {entry.status === "currently_reading" ? (
                    <label className="readswell-shelf__progress">
                      <span>{entry.progress}%</span>
                      <input
                        type="range"
                        min="0"
                        max="100"
                        value={entry.progress}
                        onChange={(event) => onProgressChange(book.id, Number(event.target.value))}
                      />
                    </label>
                  ) : null}
                </div>
              </article>
            );
          })}
        </div>
      ) : (
        <div className="readswell-shelf__empty">Nothing here yet. Add a book from search or recommendations.</div>
      )}
    </section>
  );
}

export function ReadswellPage() {
  const [appState, setAppState] = useState(loadState);
  const [theme, setTheme] = useState<ThemeId>(loadTheme);
  const [searchInput, setSearchInput] = useState("");
  const deferredQuery = useDeferredValue(searchInput);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    saveState(appState);
  }, [appState]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  useEffect(() => {
    if (!toast) {
      return undefined;
    }

    const timeout = window.setTimeout(() => setToast(null), 2600);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  const recommendations = getRecommendations(appState, 6);
  const searchResults = searchCatalog(deferredQuery, appState);
  const dashboardStats = getDashboardStats(appState);
  const fingerprintBars = getFingerprintBars(appState);
  const libraryGroups = groupLibraryByStatus(appState);
  const activeTaste = [
    ...appState.profile.moods.slice(0, 3),
    ...appState.profile.tropes.slice(0, 2),
    ...(appState.profile.pace ? [`${appState.profile.pace} pace`] : []),
    ...(appState.profile.prose ? [`${appState.profile.prose} prose`] : []),
  ];

  function announce(message: string) {
    setToast(message);
  }

  function updateProfileName(value: string) {
    setAppState((previous) => ({
      ...previous,
      profile: {
        ...previous.profile,
        name: value,
      },
    }));
  }

  function updateProfileSelection(field: "pace" | "prose", value: string) {
    setAppState((previous) => ({
      ...previous,
      profile: {
        ...previous.profile,
        [field]: value,
      },
    }));
  }

  function toggleProfileList(field: "moods" | "tropes", value: string) {
    setAppState((previous) => {
      const existing = previous.profile[field];
      const nextValues = existing.includes(value) ? existing.filter((item) => item !== value) : [...existing, value];
      return {
        ...previous,
        profile: {
          ...previous.profile,
          [field]: nextValues,
        },
      };
    });
  }

  function updateStatus(bookId: string, status: ShelfStatus) {
    const book = BOOKS.find((candidate) => candidate.id === bookId);
    setAppState((previous) => {
      const existing = previous.library[bookId];
      const nextProgress =
        status === "read" ? 100 : status === "currently_reading" ? Math.max(existing?.progress ?? 0, 8) : 0;
      const mergedEntry = createOrMergeEntry(existing, {
        status,
        progress: nextProgress,
        updatedAt: new Date().toISOString(),
      });
      return addActivity(
        {
          ...previous,
          library: {
            ...previous.library,
            [bookId]: mergedEntry,
          },
        },
        `${book?.title ?? "Book"} moved to ${statusLabels[status]}.`,
      );
    });
    announce(`Saved to ${statusLabels[status]}.`);
  }

  function updateRating(bookId: string, field: "ratingOverall" | "moodScore" | "paceScore", value: number) {
    const book = BOOKS.find((candidate) => candidate.id === bookId);
    setAppState((previous) => {
      const existing = previous.library[bookId];
      const mergedEntry = createOrMergeEntry(existing, {
        [field]: value,
        updatedAt: new Date().toISOString(),
      });
      return addActivity(
        {
          ...previous,
          library: {
            ...previous.library,
            [bookId]: mergedEntry,
          },
        },
        `${book?.title ?? "Book"} updated with a new rating signal.`,
      );
    });
  }

  function updateProgress(bookId: string, value: number) {
    const book = BOOKS.find((candidate) => candidate.id === bookId);
    setAppState((previous) => {
      const existing = previous.library[bookId];
      const mergedEntry = createOrMergeEntry(existing, {
        status: "currently_reading",
        progress: clampProgress(value),
        updatedAt: new Date().toISOString(),
      });
      return addActivity(
        {
          ...previous,
          library: {
            ...previous.library,
            [bookId]: mergedEntry,
          },
        },
        `${book?.title ?? "Book"} progress set to ${clampProgress(value)}%.`,
      );
    });
  }

  function applyImport(csvText: string, source: string) {
    const { importedEntries, report } = importGoodreadsCsv(csvText, source);
    setAppState((previous) => {
      const nextLibrary = { ...previous.library };
      importedEntries.forEach(({ bookId, entry }) => {
        const existing = nextLibrary[bookId];
        nextLibrary[bookId] = createOrMergeEntry(existing, {
          ...entry,
          ratingOverall: entry.ratingOverall || existing?.ratingOverall || 0,
          moodScore: entry.ratingOverall > 0 ? entry.moodScore : existing?.moodScore || entry.moodScore,
          paceScore: entry.ratingOverall > 0 ? entry.paceScore : existing?.paceScore || entry.paceScore,
        });
      });
      return addActivity(
        {
          ...previous,
          library: nextLibrary,
          importReport: report,
        },
        `Imported ${report.matchedCount} books from ${source}.`,
      );
    });
    announce(`Imported ${report.matchedCount} books from ${source}.`);
  }

  async function handleFileImport(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    const text = await file.text();
    applyImport(text, file.name);
  }

  function handleReset() {
    if (!window.confirm("Reset the Readswell MVP back to its demo profile?")) {
      return;
    }

    setAppState(resetState());
    setSearchInput("");
    announce("Readswell reset to the demo profile.");
  }

  function handleReadNext() {
    const nextPick = recommendations[0];
    if (!nextPick) {
      return;
    }

    startTransition(() => {
      setSearchInput(nextPick.book.title);
    });
    announce(`${nextPick.book.title} is your best next pick.`);
  }

  return (
    <div className="readswell" data-theme={theme}>
      <div className="readswell__halo readswell__halo--one" />
      <div className="readswell__halo readswell__halo--two" />
      <header className="readswell__topbar">
        <div>
          <p className="readswell__eyebrow">Readswell MVP</p>
          <h1>Book discovery for people with picky taste.</h1>
        </div>
        <div className="readswell__topbar-actions">
          <a className="readswell__toplink" href="/">
            Portfolio workspace
          </a>
          <a className="readswell__toplink" href="#import">
            Import
          </a>
          <a className="readswell__toplink" href="#profile">
            Profile
          </a>
          <button type="button" className="readswell__reset" onClick={handleReset}>
            Reset demo
          </button>
        </div>
      </header>

      <section className="readswell__theme-studio" aria-label="Theme options">
        <div className="readswell__theme-copy">
          <p className="readswell__eyebrow">Style Studies</p>
          <h2>Try a few completely different visual directions.</h2>
          <p className="readswell__helper">
            These themes change the palette, tone, and typography treatment so we can compare design systems instead
            of only swapping one accent color.
          </p>
        </div>
        <div className="readswell__theme-grid">
          {themeOptions.map((option) => (
            <button
              key={option.id}
              type="button"
              className={`readswell__theme-card${theme === option.id ? " readswell__theme-card--active" : ""}`}
              onClick={() => setTheme(option.id)}
            >
              <div className="readswell__theme-swatches">
                {option.swatches.map((swatch) => (
                  <span key={swatch} style={{ backgroundColor: swatch }} />
                ))}
              </div>
              <strong>{option.name}</strong>
              <span>{option.note}</span>
            </button>
          ))}
        </div>
      </section>

      <main className="readswell__main">
        <section className="readswell__hero" id="discover">
          <div className="readswell__hero-copy">
            <p className="readswell__eyebrow">Local-first prototype</p>
            <h2>
              Search by feeling, import your history, and get recommendations that explain themselves.
            </h2>
            <p className="readswell__lede">
              This build focuses on the demo-worthy core: natural-language search, fast shelf logging, Goodreads CSV
              import, and a recommendation layer grounded in taste cues instead of bestseller gravity.
            </p>
            <div className="readswell__stat-grid">
              {dashboardStats.map((stat) => (
                <article key={stat.label} className="readswell__stat-card">
                  <span>{stat.label}</span>
                  <strong>{stat.value}</strong>
                </article>
              ))}
            </div>
            <div className="readswell__prompt-row">
              {SEARCH_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  className="readswell__prompt"
                  onClick={() =>
                    startTransition(() => {
                      setSearchInput(prompt);
                    })
                  }
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>

          <section className="readswell__panel readswell__panel--taste">
            <div className="readswell__panel-heading">
              <div>
                <p className="readswell__eyebrow">Taste profile</p>
                <h3>{appState.profile.name}'s reading lens</h3>
              </div>
              <button type="button" className="readswell__save" onClick={() => announce("Taste profile saved locally.")}>
                Save locally
              </button>
            </div>
            <label className="readswell__field">
              Reader name
              <input value={appState.profile.name} onChange={(event) => updateProfileName(event.target.value)} />
            </label>
            <div className="readswell__field-grid">
              <label className="readswell__field">
                Ideal pace
                <select
                  value={appState.profile.pace}
                  onChange={(event) => updateProfileSelection("pace", event.target.value)}
                >
                  <option value="">Choose one</option>
                  {PACE_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
              <label className="readswell__field">
                Preferred prose
                <select
                  value={appState.profile.prose}
                  onChange={(event) => updateProfileSelection("prose", event.target.value)}
                >
                  <option value="">Choose one</option>
                  {PROSE_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <ToneChips
              title="Mood cues"
              options={MOOD_OPTIONS}
              selected={appState.profile.moods}
              onToggle={(value) => toggleProfileList("moods", value)}
            />
            <ToneChips
              title="Recurring tropes"
              options={TROPE_OPTIONS}
              selected={appState.profile.tropes}
              onToggle={(value) => toggleProfileList("tropes", value)}
            />
            <p className="readswell__helper">
              Everything in this MVP persists in your browser, so you can demo it immediately without wiring a backend.
            </p>
          </section>
        </section>

        <section className="readswell__grid">
          <section className="readswell__panel">
            <div className="readswell__panel-heading">
              <div>
                <p className="readswell__eyebrow">Discover</p>
                <h3>Ask for a book the way readers actually think.</h3>
              </div>
              <div className="readswell__search-controls">
                <input
                  value={searchInput}
                  onChange={(event) => setSearchInput(event.target.value)}
                  placeholder="Try: a quiet fantasy with yearning and a little mystery"
                />
                <button type="button" className="readswell__save" onClick={handleReadNext}>
                  Read next
                </button>
              </div>
            </div>
            <div className="readswell__active-taste">
              {activeTaste.map((item) => (
                <span key={item} className="readswell__active-pill">
                  {item}
                </span>
              ))}
            </div>
            <div className="readswell__card-grid">
              {searchResults.map((result) => (
                <BookCard
                  key={result.book.id}
                  result={result}
                  entry={appState.library[result.book.id]}
                  onStatusChange={updateStatus}
                  onRatingChange={updateRating}
                  onProgressChange={updateProgress}
                />
              ))}
            </div>
          </section>

          <aside className="readswell__panel">
            <div className="readswell__panel-heading">
              <div>
                <p className="readswell__eyebrow">For you</p>
                <h3>Recommendations with receipts</h3>
              </div>
            </div>
            <div className="readswell__stack">
              {recommendations.map((result) => (
                <BookCard
                  key={result.book.id}
                  result={result}
                  entry={appState.library[result.book.id]}
                  onStatusChange={updateStatus}
                  onRatingChange={updateRating}
                  onProgressChange={updateProgress}
                />
              ))}
            </div>
          </aside>
        </section>

        <section className="readswell__grid readswell__grid--secondary">
          <section className="readswell__panel">
            <div className="readswell__panel-heading">
              <div>
                <p className="readswell__eyebrow">Shelves</p>
                <h3>Track with almost no friction.</h3>
              </div>
            </div>
            <div className="readswell__shelves">
              <ShelfColumn
                label="Want to read"
                entries={[...libraryGroups.want_to_read].sort(
                  (left, right) => right[1].updatedAt.localeCompare(left[1].updatedAt),
                )}
                onStatusChange={updateStatus}
                onProgressChange={updateProgress}
              />
              <ShelfColumn
                label="Currently reading"
                entries={[...libraryGroups.currently_reading].sort(
                  (left, right) => right[1].updatedAt.localeCompare(left[1].updatedAt),
                )}
                onStatusChange={updateStatus}
                onProgressChange={updateProgress}
              />
              <ShelfColumn
                label="Read"
                entries={[...libraryGroups.read].sort((left, right) => right[1].updatedAt.localeCompare(left[1].updatedAt))}
                onStatusChange={updateStatus}
                onProgressChange={updateProgress}
              />
              <ShelfColumn
                label="DNF"
                entries={[...libraryGroups.dnf].sort((left, right) => right[1].updatedAt.localeCompare(left[1].updatedAt))}
                onStatusChange={updateStatus}
                onProgressChange={updateProgress}
              />
            </div>
          </section>

          <section className="readswell__panel" id="import">
            <div className="readswell__panel-heading">
              <div>
                <p className="readswell__eyebrow">Import</p>
                <h3>Pull in a Goodreads CSV and get instant taste signal.</h3>
              </div>
            </div>
            <div className="readswell__import-actions">
              <label className="readswell__file-field">
                <span>Upload Goodreads CSV</span>
                <input type="file" accept=".csv" onChange={handleFileImport} />
              </label>
              <button type="button" className="readswell__save" onClick={() => applyImport(DEMO_GOODREADS_CSV, "Demo CSV")}>
                Load demo import
              </button>
            </div>
            {appState.importReport ? (
              <div className="readswell__import-report">
                <div className="readswell__import-kpis">
                  <article>
                    <span>Rows</span>
                    <strong>{appState.importReport.totalRows}</strong>
                  </article>
                  <article>
                    <span>Matched</span>
                    <strong>{appState.importReport.matchedCount}</strong>
                  </article>
                  <article>
                    <span>Unresolved</span>
                    <strong>{appState.importReport.unresolved.length}</strong>
                  </article>
                </div>
                <p className="readswell__helper">
                  Last import from {appState.importReport.source} on {formatTimestamp(appState.importReport.lastImportedAt)}.
                </p>
                {appState.importReport.unresolved.length ? (
                  <ul className="readswell__issue-list">
                    {appState.importReport.unresolved.map((issue) => (
                      <li key={`${issue.title}-${issue.author}`}>
                        {issue.title} by {issue.author}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="readswell__helper">Everything in this import matched the seeded catalog cleanly.</p>
                )}
              </div>
            ) : (
              <p className="readswell__helper">
                Use the built-in demo import if you just want to see the flow without hunting down a CSV export first.
              </p>
            )}
          </section>
        </section>

        <section className="readswell__grid readswell__grid--profile" id="profile">
          <section className="readswell__panel">
            <div className="readswell__panel-heading">
              <div>
                <p className="readswell__eyebrow">Profile</p>
                <h3>Shareable identity, not just a database row.</h3>
              </div>
            </div>
            <div className="readswell__stat-grid readswell__stat-grid--compact">
              {dashboardStats.map((stat) => (
                <article key={stat.label} className="readswell__stat-card">
                  <span>{stat.label}</span>
                  <strong>{stat.value}</strong>
                </article>
              ))}
            </div>
          </section>

          <section className="readswell__panel">
            <div className="readswell__panel-heading">
              <div>
                <p className="readswell__eyebrow">Reading fingerprint</p>
                <h3>What this reader tends to chase.</h3>
              </div>
            </div>
            <div className="readswell__fingerprint">
              {fingerprintBars.map((bar) => (
                <article key={bar.label} className="readswell__fingerprint-row">
                  <div className="readswell__fingerprint-labels">
                    <span>{bar.label}</span>
                    <span>{bar.value}%</span>
                  </div>
                  <div className="readswell__fingerprint-track">
                    <div className="readswell__fingerprint-fill" style={{ width: `${bar.value}%` }} />
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="readswell__panel readswell__panel--wide">
            <div className="readswell__panel-heading">
              <div>
                <p className="readswell__eyebrow">Activity</p>
                <h3>Recent taste signals</h3>
              </div>
            </div>
            <div className="readswell__activity-list">
              {appState.activity.map((item) => (
                <article key={item.id} className="readswell__activity-item">
                  <p>{item.label}</p>
                  <span>{formatTimestamp(item.timestamp)}</span>
                </article>
              ))}
            </div>
          </section>
        </section>
      </main>

      {toast ? <div className="readswell__toast">{toast}</div> : null}
    </div>
  );
}
