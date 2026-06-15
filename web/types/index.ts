export interface UserSettings {
  aiProvider: string;
  dailyTarget: number;
  targetBand: number;
  examDate: string | null;
  focusModules: string[];
}

export interface User {
  id: string;
  email: string;
  name: string;
  settings: UserSettings;
}

export interface Word {
  id: string;
  word: string;
  lemma: string;
  frequency: number;
  priorityScore: number;
  difficulty: string;
  partOfSpeech: string;
  persianMeaning: string;
  simpleEnglishMeaning: string;
  ieltsUseCases: string[];
  collocations: string[];
  examples: string[];
  commonMistakes: string[];
  notes?: string;
  status: string;
  important?: boolean;
  hidden?: boolean;
  aiEnriched?: boolean;
  sources?: { id: string; title: string; type: string }[];
}

export interface Phrase {
  id: string;
  phrase: string;
  frequency: number;
  confidence: number;
  section: string;
  priorityScore: number;
  persianMeaning: string;
  simpleEnglishMeaning: string;
  examples: string[];
  notes?: string;
  status: string;
  important?: boolean;
}

export interface Pattern {
  id: string;
  sentence: string;
  template: string;
  category: string;
  section: string;
  priorityScore: number;
  usefulness: number;
  notes?: string;
  status: string;
}

export interface Source {
  id: string;
  type: string;
  title: string;
  status: string;
  charCount?: number;
  stats?: Record<string, number>;
  createdAt: string;
}

export interface Job {
  id: string;
  status: string;
  kind: string;
  logs?: { t: string; msg: string }[];
  result?: { words: number; phrases: number; patterns: number };
  error?: string;
  createdAt: string;
}

export interface Card {
  id: string;
  type: string;
  front: string;
  back: {
    persianMeaning: string;
    simpleEnglishMeaning: string;
    examples: string[];
    collocations: string[];
    notes: string;
  };
  status: string;
  nextReviewAt: string;
}

export interface Dashboard {
  totalSources: number;
  totalWords: number;
  totalPhrases: number;
  totalPatterns: number;
  dueToday: number;
  mastered: number;
  learning: number;
  streak: number;
  focus: string[];
  targetBand: number | null;
  examDate: string | null;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
}
