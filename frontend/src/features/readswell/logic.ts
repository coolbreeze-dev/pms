import { BOOKS, type Book, type ImportIssue, type ImportReport, type LibraryEntry, type ReadswellState } from "./data";

export interface RankedBook {
  book: Book;
  score: number;
  why: string;
  matchedTraits: string[];
}

export interface FingerprintBar {
  label: string;
  value: number;
}

export interface DashboardStat {
  label: string;
  value: string;
}

export const statusLabels = {
  want_to_read: "Want to read",
  currently_reading: "Currently reading",
  read: "Read",
  dnf: "DNF",
} as const;

const synonymMap: Record<string, string[]> = {
  cozy: ["cozy", "warm", "gentle", "small town"],
  rainy: ["atmospheric", "moody", "melancholy"],
  romantic: ["romantic", "romance", "yearning", "slow burn"],
  warmer: ["warm", "hopeful", "romantic"],
  piranesi: ["dreamlike", "atmospheric", "scholarly mystery", "quiet fantasy"],
  mystery: ["mystery", "clues", "scholarly mystery", "literary mystery"],
  literary: ["literary", "introspective", "character study"],
  fantasy: ["fantasy", "quiet fantasy", "myth retelling"],
  sunday: ["quiet", "atmospheric", "cozy"],
};

function normalizeText(text: string) {
  return text
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function tokenize(text: string) {
  return normalizeText(text).split(" ").filter(Boolean);
}

function unique(values: string[]) {
  return Array.from(new Set(values));
}

function average(values: number[]) {
  if (!values.length) {
    return 0;
  }

  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function addWeight(bucket: Map<string, number>, values: string[], amount: number) {
  values.forEach((value) => {
    bucket.set(value, (bucket.get(value) ?? 0) + amount);
  });
}

function scoreOverlap(left: string[], right: string[]) {
  const leftSet = new Set(left);
  return right.reduce((score, value) => score + (leftSet.has(value) ? 1 : 0), 0);
}

function getBookSearchCorpus(book: Book) {
  return normalizeText(
    [
      book.title,
      book.author,
      book.description,
      ...book.subjects,
      ...book.moods,
      ...book.tropes,
      ...book.hooks,
      book.pace,
      book.prose,
    ].join(" "),
  );
}

function getBookById(bookId: string) {
  return BOOKS.find((book) => book.id === bookId);
}

function buildTasteModel(state: ReadswellState) {
  const moods = new Map<string, number>();
  const tropes = new Map<string, number>();
  const subjects = new Map<string, number>();
  const authors = new Map<string, number>();
  const pace = new Map<string, number>();
  const prose = new Map<string, number>();
  const likedBooks: Book[] = [];

  addWeight(moods, state.profile.moods, 4);
  addWeight(tropes, state.profile.tropes, 4);

  if (state.profile.pace) {
    pace.set(state.profile.pace, 3);
  }

  if (state.profile.prose) {
    prose.set(state.profile.prose, 3);
  }

  Object.entries(state.library).forEach(([bookId, entry]) => {
    const book = getBookById(bookId);
    if (!book) {
      return;
    }

    let weight = 0;
    if (entry.ratingOverall >= 4) {
      weight += 4 + (entry.ratingOverall - 4);
    } else if (entry.ratingOverall === 3) {
      weight += 1;
    } else if (entry.ratingOverall > 0) {
      weight -= 2;
    }

    if (entry.status === "currently_reading") {
      weight += 2;
    }
    if (entry.status === "want_to_read") {
      weight += 1;
    }
    if (entry.status === "dnf") {
      weight -= 3;
    }

    if (weight > 0) {
      likedBooks.push(book);
    }

    addWeight(moods, book.moods, weight);
    addWeight(tropes, book.tropes, weight);
    addWeight(subjects, book.subjects, weight);
    addWeight(authors, [book.author], weight);
    addWeight(pace, [book.pace], weight);
    addWeight(prose, [book.prose], weight);
  });

  return { moods, tropes, subjects, authors, pace, prose, likedBooks };
}

function getMapScore(bucket: Map<string, number>, key: string) {
  return bucket.get(key) ?? 0;
}

function scoreBookAgainstTaste(book: Book, state: ReadswellState) {
  const taste = buildTasteModel(state);

  const moodScore = book.moods.reduce((sum, mood) => sum + getMapScore(taste.moods, mood), 0) * 1.6;
  const tropeScore = book.tropes.reduce((sum, trope) => sum + getMapScore(taste.tropes, trope), 0) * 1.4;
  const subjectScore = book.subjects.reduce((sum, subject) => sum + getMapScore(taste.subjects, subject), 0) * 1.1;
  const authorScore = getMapScore(taste.authors, book.author) * 1.6;
  const paceScore = getMapScore(taste.pace, book.pace) * 1.2;
  const proseScore = getMapScore(taste.prose, book.prose) * 1.2;

  return moodScore + tropeScore + subjectScore + authorScore + paceScore + proseScore + book.communityRating * 0.65;
}

function scoreBookSimilarity(left: Book, right: Book) {
  return (
    scoreOverlap(left.moods, right.moods) * 2.2 +
    scoreOverlap(left.tropes, right.tropes) * 2 +
    scoreOverlap(left.subjects, right.subjects) * 1.4 +
    (left.pace === right.pace ? 1.5 : 0) +
    (left.prose === right.prose ? 1.5 : 0)
  );
}

function findReferencedBook(query: string) {
  const normalizedQuery = normalizeText(query);
  return BOOKS.find((book) => normalizedQuery.includes(normalizeText(book.title)));
}

function expandTokens(query: string) {
  const base = tokenize(query);
  return unique(
    base.flatMap((token) => {
      const extras = synonymMap[token] ?? [];
      return [token, ...extras.flatMap((value) => tokenize(value))];
    }),
  );
}

function pickSharedTraits(book: Book, state: ReadswellState, queryTokens: string[] = [], referencedBook?: Book) {
  const highlighted = [
    ...book.moods.filter((mood) => state.profile.moods.includes(mood)),
    ...book.tropes.filter((trope) => state.profile.tropes.includes(trope)),
    ...book.subjects.filter((subject) => queryTokens.includes(normalizeText(subject))),
  ];

  if (referencedBook) {
    highlighted.push(
      ...book.moods.filter((mood) => referencedBook.moods.includes(mood)),
      ...book.tropes.filter((trope) => referencedBook.tropes.includes(trope)),
    );
  }

  return unique(highlighted).slice(0, 3);
}

function buildRecommendationWhy(book: Book, state: ReadswellState) {
  const taste = buildTasteModel(state);
  const sharedWithTaste = pickSharedTraits(book, state);
  const anchorBook = taste.likedBooks
    .map((likedBook) => ({
      likedBook,
      score: scoreBookSimilarity(book, likedBook),
    }))
    .sort((left, right) => right.score - left.score)[0]?.likedBook;

  if (anchorBook) {
    const shared = unique([
      ...book.moods.filter((mood) => anchorBook.moods.includes(mood)),
      ...book.tropes.filter((trope) => anchorBook.tropes.includes(trope)),
    ]).slice(0, 2);
    const sharedText = shared.length ? shared.join(" and ") : `${book.pace} pacing`;
    return `Because you responded well to ${anchorBook.title} and this keeps its ${sharedText} energy.`;
  }

  if (sharedWithTaste.length) {
    return `Because it lines up with your ${sharedWithTaste.join(", ")} preferences right now.`;
  }

  return `Because it fits a ${book.pace} pace with ${book.prose} prose and a strong community response.`;
}

function buildSearchWhy(book: Book, state: ReadswellState, queryTokens: string[], referencedBook?: Book) {
  const sharedTraits = pickSharedTraits(book, state, queryTokens, referencedBook);

  if (referencedBook && referencedBook.id !== book.id) {
    const bridge = sharedTraits[0] ?? book.moods[0] ?? book.tropes[0] ?? book.subjects[0];
    return `It keeps the ${bridge} pull of ${referencedBook.title} while steering toward ${book.moods[0] ?? book.subjects[0]}.`;
  }

  if (sharedTraits.length) {
    return `This matches your query through ${sharedTraits.join(", ")}.`;
  }

  return `This is a strong fit for ${book.pace} pacing, ${book.prose} prose, and the themes in your prompt.`;
}

function scoreQueryAgainstBook(book: Book, queryTokens: string[]) {
  const title = normalizeText(book.title);
  const author = normalizeText(book.author);
  const corpus = getBookSearchCorpus(book);

  return queryTokens.reduce((score, token) => {
    if (title.includes(token)) {
      return score + 6;
    }
    if (author.includes(token)) {
      return score + 4;
    }
    if (corpus.includes(token)) {
      return score + 1.4;
    }
    return score;
  }, 0);
}

export function searchCatalog(query: string, state: ReadswellState) {
  const normalizedQuery = normalizeText(query);
  if (!normalizedQuery) {
    return getRecommendations(state, 6);
  }

  const queryTokens = expandTokens(query);
  const referencedBook = findReferencedBook(query);

  return BOOKS.map((book) => {
    const queryScore = scoreQueryAgainstBook(book, queryTokens);
    const tasteScore = scoreBookAgainstTaste(book, state) * 0.28;
    const referenceScore =
      referencedBook && referencedBook.id !== book.id ? scoreBookSimilarity(book, referencedBook) * 1.7 : 0;
    const sameBookPenalty = referencedBook && referencedBook.id === book.id ? 3 : 0;
    const score = queryScore + tasteScore + referenceScore - sameBookPenalty;
    return {
      book,
      score,
      matchedTraits: pickSharedTraits(book, state, queryTokens, referencedBook),
      why: buildSearchWhy(book, state, queryTokens, referencedBook),
    };
  })
    .filter((result) => result.score > 2.2)
    .sort((left, right) => right.score - left.score)
    .slice(0, 8);
}

export function getRecommendations(state: ReadswellState, limit = 6) {
  return BOOKS.map((book) => {
    const entry = state.library[book.id];
    let score = scoreBookAgainstTaste(book, state);

    if (entry?.status === "read") {
      score -= 40;
    }
    if (entry?.status === "currently_reading") {
      score -= 25;
    }
    if (entry?.status === "dnf") {
      score -= 50;
    }
    if (entry?.status === "want_to_read") {
      score -= 8;
    }

    return {
      book,
      score,
      matchedTraits: pickSharedTraits(book, state),
      why: buildRecommendationWhy(book, state),
    };
  })
    .sort((left, right) => right.score - left.score)
    .slice(0, limit);
}

export function getDashboardStats(state: ReadswellState): DashboardStat[] {
  const entries = Object.values(state.library);
  const ratings = entries.filter((entry) => entry.ratingOverall > 0).map((entry) => entry.ratingOverall);
  const readCount = entries.filter((entry) => entry.status === "read").length;
  const importedCount = entries.filter((entry) => entry.imported).length;

  return [
    { label: "Tracked books", value: String(entries.length) },
    { label: "Finished", value: String(readCount) },
    { label: "Average rating", value: ratings.length ? `${average(ratings).toFixed(1)}/5` : "No ratings yet" },
    { label: "Imported", value: String(importedCount) },
  ];
}

export function getFingerprintBars(state: ReadswellState): FingerprintBar[] {
  const taste = buildTasteModel(state);
  const topMoods = Array.from(taste.moods.entries())
    .sort((left, right) => right[1] - left[1])
    .slice(0, 3);
  const topTropes = Array.from(taste.tropes.entries())
    .sort((left, right) => right[1] - left[1])
    .slice(0, 2);

  const rawBars = [
    ...topMoods.map(([label, value]) => ({ label, value })),
    ...topTropes.map(([label, value]) => ({ label, value })),
    ...(state.profile.pace ? [{ label: `${state.profile.pace} pacing`, value: 5 }] : []),
    ...(state.profile.prose ? [{ label: `${state.profile.prose} prose`, value: 5 }] : []),
  ];

  const maxValue = Math.max(...rawBars.map((bar) => bar.value), 1);
  return rawBars.map((bar) => ({
    label: bar.label,
    value: Math.max(18, Math.round((bar.value / maxValue) * 100)),
  }));
}

export function groupLibraryByStatus(state: ReadswellState) {
  return {
    currently_reading: Object.entries(state.library).filter(([, entry]) => entry.status === "currently_reading"),
    want_to_read: Object.entries(state.library).filter(([, entry]) => entry.status === "want_to_read"),
    read: Object.entries(state.library).filter(([, entry]) => entry.status === "read"),
    dnf: Object.entries(state.library).filter(([, entry]) => entry.status === "dnf"),
  };
}

function parseCsv(text: string) {
  const rows: string[][] = [];
  let currentRow: string[] = [];
  let currentCell = "";
  let inQuotes = false;

  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    const nextCharacter = text[index + 1];

    if (character === '"') {
      if (inQuotes && nextCharacter === '"') {
        currentCell += '"';
        index += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (character === "," && !inQuotes) {
      currentRow.push(currentCell);
      currentCell = "";
      continue;
    }

    if ((character === "\n" || character === "\r") && !inQuotes) {
      if (character === "\r" && nextCharacter === "\n") {
        index += 1;
      }
      currentRow.push(currentCell);
      if (currentRow.some((value) => value.trim().length > 0)) {
        rows.push(currentRow);
      }
      currentRow = [];
      currentCell = "";
      continue;
    }

    currentCell += character;
  }

  if (currentCell.length > 0 || currentRow.length > 0) {
    currentRow.push(currentCell);
    rows.push(currentRow);
  }

  const [headerRow, ...bodyRows] = rows;
  if (!headerRow) {
    return [];
  }

  const headers = headerRow.map((header) => normalizeText(header).replace(/\s+/g, "_"));
  return bodyRows.map((row) =>
    headers.reduce<Record<string, string>>((record, header, index) => {
      record[header] = row[index] ?? "";
      return record;
    }, {}),
  );
}

function scoreImportCandidate(rowTitle: string, rowAuthor: string, book: Book) {
  const titleTokens = tokenize(rowTitle);
  const authorTokens = tokenize(rowAuthor);
  const bookTitleTokens = tokenize(book.title);
  const bookAuthorTokens = tokenize(book.author);

  const titleOverlap = scoreOverlap(titleTokens, bookTitleTokens);
  const authorOverlap = scoreOverlap(authorTokens, bookAuthorTokens);
  const exactTitle = normalizeText(rowTitle) === normalizeText(book.title) ? 3 : 0;
  const exactAuthor = normalizeText(rowAuthor) === normalizeText(book.author) ? 2 : 0;

  return titleOverlap * 2 + authorOverlap * 1.5 + exactTitle + exactAuthor;
}

function findImportMatch(row: Record<string, string>) {
  const isbn13 = row.isbn13?.trim();
  if (isbn13) {
    const isbnMatch = BOOKS.find((book) => book.isbn13 === isbn13);
    if (isbnMatch) {
      return isbnMatch;
    }
  }

  const title = row.title ?? "";
  const author = row.author ?? "";
  const bestMatch = BOOKS.map((book) => ({
    book,
    score: scoreImportCandidate(title, author, book),
  })).sort((left, right) => right.score - left.score)[0];

  if (!bestMatch || bestMatch.score < 4) {
    return null;
  }

  return bestMatch.book;
}

function mapShelf(exclusiveShelf: string): LibraryEntry["status"] {
  const normalized = normalizeText(exclusiveShelf).replace(/\s+/g, "_");
  if (normalized === "read") {
    return "read";
  }
  if (normalized === "currently_reading") {
    return "currently_reading";
  }
  if (normalized === "to_read") {
    return "want_to_read";
  }
  return "want_to_read";
}

function nowIso() {
  return new Date().toISOString();
}

export function importGoodreadsCsv(csvText: string, source = "Goodreads") {
  const rows = parseCsv(csvText);
  const importedEntries: Array<{ bookId: string; entry: LibraryEntry }> = [];
  const unresolved: ImportIssue[] = [];

  rows.forEach((row) => {
    const match = findImportMatch(row);
    if (!match) {
      unresolved.push({
        title: row.title ?? "Unknown title",
        author: row.author ?? "Unknown author",
      });
      return;
    }

    const ratingOverall = Number.parseInt(row.my_rating ?? "0", 10) || 0;
    const status = mapShelf(row.exclusive_shelf ?? row.bookshelves ?? "to-read");
    importedEntries.push({
      bookId: match.id,
      entry: {
        status,
        ratingOverall,
        moodScore: ratingOverall > 0 ? Math.min(5, Math.max(3, ratingOverall)) : 3,
        paceScore: 3,
        progress: status === "read" ? 100 : 0,
        imported: true,
        updatedAt: nowIso(),
      },
    });
  });

  const report: ImportReport = {
    source,
    totalRows: rows.length,
    matchedCount: importedEntries.length,
    unresolved,
    importedBookIds: importedEntries.map((result) => result.bookId),
    lastImportedAt: nowIso(),
  };

  return { report, importedEntries };
}

export function formatTimestamp(timestamp: string) {
  return new Date(timestamp).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}
