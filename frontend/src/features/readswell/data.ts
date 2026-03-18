export type PaceValue = "slow" | "steady" | "fast";
export type ProseValue = "lyrical" | "clean" | "dense";
export type ShelfStatus = "want_to_read" | "currently_reading" | "read" | "dnf";

export interface Book {
  id: string;
  title: string;
  author: string;
  year: number;
  isbn13: string;
  description: string;
  subjects: string[];
  moods: string[];
  tropes: string[];
  hooks: string[];
  pace: PaceValue;
  prose: ProseValue;
  communityRating: number;
  cover: {
    start: string;
    end: string;
  };
}

export interface LibraryEntry {
  status: ShelfStatus;
  ratingOverall: number;
  moodScore: number;
  paceScore: number;
  progress: number;
  imported: boolean;
  updatedAt: string;
}

export interface ProfileState {
  name: string;
  moods: string[];
  tropes: string[];
  pace: PaceValue | "";
  prose: ProseValue | "";
}

export interface ActivityItem {
  id: string;
  label: string;
  timestamp: string;
}

export interface ImportIssue {
  title: string;
  author: string;
}

export interface ImportReport {
  source: string;
  totalRows: number;
  matchedCount: number;
  unresolved: ImportIssue[];
  importedBookIds: string[];
  lastImportedAt: string;
}

export interface ReadswellState {
  profile: ProfileState;
  library: Record<string, LibraryEntry>;
  importReport: ImportReport | null;
  activity: ActivityItem[];
}

export const MOOD_OPTIONS = [
  "atmospheric",
  "hopeful",
  "introspective",
  "cozy",
  "tense",
  "romantic",
  "melancholy",
  "witty",
] as const;

export const TROPE_OPTIONS = [
  "quiet fantasy",
  "scholarly mystery",
  "slow burn",
  "small town",
  "found family",
  "unreliable narrator",
  "second chances",
  "ghostly house",
] as const;

export const PACE_OPTIONS: PaceValue[] = ["slow", "steady", "fast"];
export const PROSE_OPTIONS: ProseValue[] = ["lyrical", "clean", "dense"];

export const SEARCH_PROMPTS = [
  "like Piranesi but warmer and more romantic",
  "cozy mystery with a sharp older cast",
  "lyrical fantasy for a rainy Sunday",
  "literary family drama that still feels hopeful",
];

export const BOOKS: Book[] = [
  {
    id: "piranesi",
    title: "Piranesi",
    author: "Susanna Clarke",
    year: 2020,
    isbn13: "9781635575637",
    description: "A solitary man maps an endless house of tides, statues, and half-remembered secrets.",
    subjects: ["fantasy", "literary", "mystery"],
    moods: ["atmospheric", "dreamlike", "introspective"],
    tropes: ["quiet fantasy", "scholarly mystery", "unreliable narrator"],
    hooks: ["rainy sunday", "solitude", "strange house"],
    pace: "slow",
    prose: "lyrical",
    communityRating: 4.3,
    cover: { start: "#16324f", end: "#4f6d8a" },
  },
  {
    id: "night-circus",
    title: "The Night Circus",
    author: "Erin Morgenstern",
    year: 2011,
    isbn13: "9780307744432",
    description: "A black-and-white circus appears at dusk, carrying enchantment, rivalry, and longing.",
    subjects: ["fantasy", "romance", "historical"],
    moods: ["atmospheric", "romantic", "whimsical"],
    tropes: ["slow burn", "star-crossed", "magical competition"],
    hooks: ["lush", "midnight", "showstopper"],
    pace: "slow",
    prose: "lyrical",
    communityRating: 4.1,
    cover: { start: "#1c1b29", end: "#8d6a9f" },
  },
  {
    id: "emily-wilde",
    title: "Emily Wilde's Encyclopaedia of Faeries",
    author: "Heather Fawcett",
    year: 2023,
    isbn13: "9780593500132",
    description: "A brilliant scholar studies faeries in a snowbound village and accidentally falls into adventure.",
    subjects: ["fantasy", "romance", "adventure"],
    moods: ["cozy", "witty", "hopeful"],
    tropes: ["scholarly mystery", "small town", "slow burn"],
    hooks: ["snowy village", "academic banter", "faerie lore"],
    pace: "steady",
    prose: "clean",
    communityRating: 4.2,
    cover: { start: "#355070", end: "#6d597a" },
  },
  {
    id: "thursday-murder-club",
    title: "The Thursday Murder Club",
    author: "Richard Osman",
    year: 2020,
    isbn13: "9781984880987",
    description: "Four retirees at a quiet village community crack open a very live murder case.",
    subjects: ["mystery", "crime", "humor"],
    moods: ["cozy", "witty", "hopeful"],
    tropes: ["small town", "found family", "amateur sleuths"],
    hooks: ["older cast", "dry humor", "tea and clues"],
    pace: "steady",
    prose: "clean",
    communityRating: 4,
    cover: { start: "#a23e48", end: "#f2cc8f" },
  },
  {
    id: "gentleman-moscow",
    title: "A Gentleman in Moscow",
    author: "Amor Towles",
    year: 2016,
    isbn13: "9780143110439",
    description: "Confined to a grand hotel, a count builds a full life inside one elegant address.",
    subjects: ["historical", "literary", "character study"],
    moods: ["hopeful", "introspective", "warm"],
    tropes: ["second chances", "found family", "elegant setting"],
    hooks: ["hotel life", "grace under pressure", "slow unfolding"],
    pace: "slow",
    prose: "clean",
    communityRating: 4.4,
    cover: { start: "#5f0f40", end: "#e36414" },
  },
  {
    id: "remarkably-bright-creatures",
    title: "Remarkably Bright Creatures",
    author: "Shelby Van Pelt",
    year: 2022,
    isbn13: "9780063204157",
    description: "An octopus, a grieving widow, and a gentle mystery about belonging find one another.",
    subjects: ["literary", "mystery", "contemporary"],
    moods: ["hopeful", "tender", "witty"],
    tropes: ["found family", "second chances", "gentle mystery"],
    hooks: ["sea creature narrator", "heart-forward", "community"],
    pace: "steady",
    prose: "clean",
    communityRating: 4.3,
    cover: { start: "#0f4c5c", end: "#3c6e71" },
  },
  {
    id: "station-eleven",
    title: "Station Eleven",
    author: "Emily St. John Mandel",
    year: 2014,
    isbn13: "9780804172448",
    description: "Art, memory, and survival braid together after a flu pandemic reshapes the world.",
    subjects: ["science fiction", "literary", "post-apocalyptic"],
    moods: ["melancholy", "hopeful", "atmospheric"],
    tropes: ["interconnected lives", "traveling troupe", "before and after"],
    hooks: ["elegiac", "human connection", "quiet apocalypse"],
    pace: "steady",
    prose: "lyrical",
    communityRating: 4.1,
    cover: { start: "#1b4332", end: "#588157" },
  },
  {
    id: "circe",
    title: "Circe",
    author: "Madeline Miller",
    year: 2018,
    isbn13: "9780316556323",
    description: "The witch of myth claims power, loneliness, and self-definition in a luminous retelling.",
    subjects: ["fantasy", "myth retelling", "literary"],
    moods: ["introspective", "romantic", "atmospheric"],
    tropes: ["myth retelling", "self-discovery", "fierce women"],
    hooks: ["island setting", "gods and mortals", "feminine rage"],
    pace: "slow",
    prose: "lyrical",
    communityRating: 4.4,
    cover: { start: "#7f1d1d", end: "#f59e0b" },
  },
  {
    id: "secret-history",
    title: "The Secret History",
    author: "Donna Tartt",
    year: 1992,
    isbn13: "9781400031702",
    description: "A classics clique, a moral collapse, and a campus atmosphere so thick it almost smokes.",
    subjects: ["literary", "mystery", "dark academia"],
    moods: ["tense", "atmospheric", "introspective"],
    tropes: ["unreliable narrator", "scholarly mystery", "elite friend group"],
    hooks: ["campus obsession", "snowy dread", "moral rot"],
    pace: "slow",
    prose: "dense",
    communityRating: 4.2,
    cover: { start: "#2f1b25", end: "#7a2e3a" },
  },
  {
    id: "mexican-gothic",
    title: "Mexican Gothic",
    author: "Silvia Moreno-Garcia",
    year: 2020,
    isbn13: "9780525620785",
    description: "A glamorous debutante enters a decaying manor and discovers a fungus-fed nightmare.",
    subjects: ["horror", "historical", "gothic"],
    moods: ["tense", "atmospheric", "glamorous"],
    tropes: ["ghostly house", "family secrets", "isolated estate"],
    hooks: ["velvet dread", "creeping horror", "bold heroine"],
    pace: "steady",
    prose: "lyrical",
    communityRating: 3.9,
    cover: { start: "#5f0f40", end: "#9a031e" },
  },
  {
    id: "in-the-woods",
    title: "In the Woods",
    author: "Tana French",
    year: 2007,
    isbn13: "9780143113492",
    description: "A detective returns to the woods that nearly erased his childhood and stirs up old ruin.",
    subjects: ["mystery", "crime", "psychological"],
    moods: ["tense", "melancholy", "atmospheric"],
    tropes: ["unreliable narrator", "past returns", "literary mystery"],
    hooks: ["haunted detective", "foggy woods", "emotional fallout"],
    pace: "slow",
    prose: "dense",
    communityRating: 4,
    cover: { start: "#283618", end: "#606c38" },
  },
  {
    id: "psalm-wild-built",
    title: "A Psalm for the Wild-Built",
    author: "Becky Chambers",
    year: 2021,
    isbn13: "9781250236210",
    description: "A tea monk and a robot have a small, searching conversation about what people need.",
    subjects: ["science fiction", "hopepunk", "philosophical"],
    moods: ["hopeful", "cozy", "introspective"],
    tropes: ["quiet fantasy", "road trip", "gentle questions"],
    hooks: ["soft sci-fi", "tea ritual", "comfort read"],
    pace: "slow",
    prose: "clean",
    communityRating: 4.2,
    cover: { start: "#386641", end: "#a7c957" },
  },
  {
    id: "small-things-like-these",
    title: "Small Things Like These",
    author: "Claire Keegan",
    year: 2021,
    isbn13: "9780802158741",
    description: "A coal merchant notices a local wrong and quietly decides what kind of man he will be.",
    subjects: ["literary", "historical", "novella"],
    moods: ["melancholy", "hopeful", "quiet"],
    tropes: ["moral reckoning", "small town", "winter story"],
    hooks: ["short and sharp", "ethical tension", "Irish setting"],
    pace: "slow",
    prose: "clean",
    communityRating: 4.2,
    cover: { start: "#3d405b", end: "#81b29a" },
  },
  {
    id: "rebecca",
    title: "Rebecca",
    author: "Daphne du Maurier",
    year: 1938,
    isbn13: "9780380730407",
    description: "A young bride enters Manderley and finds the first wife has not truly left.",
    subjects: ["gothic", "mystery", "classic"],
    moods: ["tense", "atmospheric", "romantic"],
    tropes: ["ghostly house", "unreliable narrator", "obsession"],
    hooks: ["windswept estate", "haunting marriage", "classic suspense"],
    pace: "slow",
    prose: "dense",
    communityRating: 4.3,
    cover: { start: "#1d3557", end: "#6d597a" },
  },
  {
    id: "lessons-in-chemistry",
    title: "Lessons in Chemistry",
    author: "Bonnie Garmus",
    year: 2022,
    isbn13: "9780385547345",
    description: "A chemist pushed out of science turns a cooking show into a sly, furious reinvention.",
    subjects: ["historical", "contemporary", "literary"],
    moods: ["witty", "hopeful", "determined"],
    tropes: ["second chances", "found family", "workplace rebellion"],
    hooks: ["sharp voice", "cultural critique", "big feelings"],
    pace: "steady",
    prose: "clean",
    communityRating: 4,
    cover: { start: "#3a86ff", end: "#ffbe0b" },
  },
  {
    id: "bear-and-the-nightingale",
    title: "The Bear and the Nightingale",
    author: "Katherine Arden",
    year: 2017,
    isbn13: "9781101885956",
    description: "In a frozen village, old spirits stir while a girl refuses to shrink from myth and winter.",
    subjects: ["fantasy", "historical", "folklore"],
    moods: ["atmospheric", "tense", "romantic"],
    tropes: ["quiet fantasy", "winter village", "mythic danger"],
    hooks: ["snowbound", "folklore roots", "icy wonder"],
    pace: "slow",
    prose: "lyrical",
    communityRating: 4.1,
    cover: { start: "#274c77", end: "#6096ba" },
  },
  {
    id: "normal-people",
    title: "Normal People",
    author: "Sally Rooney",
    year: 2018,
    isbn13: "9781984822178",
    description: "Two people circle one another through years of class, intimacy, and missed timing.",
    subjects: ["literary", "romance", "contemporary"],
    moods: ["introspective", "melancholy", "romantic"],
    tropes: ["slow burn", "miscommunication", "coming of age"],
    hooks: ["close interiority", "quiet ache", "emotional precision"],
    pace: "slow",
    prose: "clean",
    communityRating: 4,
    cover: { start: "#023047", end: "#8ecae6" },
  },
  {
    id: "ninth-house",
    title: "Ninth House",
    author: "Leigh Bardugo",
    year: 2019,
    isbn13: "9781250313072",
    description: "A survivor enters Yale's occult societies and finds blood, debt, and power in the walls.",
    subjects: ["fantasy", "dark academia", "mystery"],
    moods: ["tense", "atmospheric", "sharp"],
    tropes: ["scholarly mystery", "ghosts", "elite institutions"],
    hooks: ["campus occult", "gritty magic", "secret societies"],
    pace: "steady",
    prose: "dense",
    communityRating: 4,
    cover: { start: "#111827", end: "#7c3aed" },
  },
  {
    id: "project-hail-mary",
    title: "Project Hail Mary",
    author: "Andy Weir",
    year: 2021,
    isbn13: "9780593135204",
    description: "A stranded astronaut solves world-ending science problems with one extremely lovable ally.",
    subjects: ["science fiction", "adventure", "humor"],
    moods: ["hopeful", "witty", "tense"],
    tropes: ["found family", "problem solving", "space survival"],
    hooks: ["page-turner", "science puzzles", "big-hearted"],
    pace: "fast",
    prose: "clean",
    communityRating: 4.5,
    cover: { start: "#1d3557", end: "#457b9d" },
  },
  {
    id: "song-of-achilles",
    title: "The Song of Achilles",
    author: "Madeline Miller",
    year: 2011,
    isbn13: "9780062060624",
    description: "A doomed war story becomes an intimate love story told with aching tenderness.",
    subjects: ["myth retelling", "romance", "historical"],
    moods: ["romantic", "melancholy", "lyrical"],
    tropes: ["slow burn", "fated love", "myth retelling"],
    hooks: ["aching devotion", "beautiful tragedy", "intimate voice"],
    pace: "slow",
    prose: "lyrical",
    communityRating: 4.4,
    cover: { start: "#7f5539", end: "#ddb892" },
  },
];

export const DEMO_GOODREADS_CSV = `Book Id,Title,Author,ISBN,ISBN13,My Rating,Average Rating,Exclusive Shelf,Date Read
1,Piranesi,Susanna Clarke,,9781635575637,5,4.3,read,2026/03/01
2,The Night Circus,Erin Morgenstern,,9780307744432,4,4.1,read,2026/02/19
3,Emily Wilde's Encyclopaedia of Faeries,Heather Fawcett,,9780593500132,0,4.2,to-read,
4,A Psalm for the Wild-Built,Becky Chambers,,9781250236210,5,4.2,read,2026/03/06
5,In the Woods,Tana French,,9780143113492,4,4.0,read,2026/01/15`;
