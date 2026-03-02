import { create } from 'zustand';

/**
 * Tutorial progress data stored per tutorial in localStorage.
 * Follows the same localStorage pattern as pinnedItems.ts and theme.ts.
 */
export interface TutorialProgressEntry {
    tutorial_id: string;
    current_step: number;
    completed_steps: string[];
    updated_at: number; // timestamp for ordering
}

interface TutorialProgressState {
    progressMap: Record<string, TutorialProgressEntry>;

    /** Get all progress entries sorted by most recently updated first */
    getProgressList: () => TutorialProgressEntry[];

    /** Get progress for a specific tutorial (returns null if not found) */
    getProgress: (tutorialId: string) => TutorialProgressEntry | null;

    /** Save progress for a specific tutorial */
    saveProgress: (tutorialId: string, currentStep: number, completedSteps: string[]) => void;

    /** Check if any progress has been saved */
    hasAnyProgress: () => boolean;
}

const STORAGE_KEY = 'kai_fusion_tutorial_progress';

// Load from localStorage
const loadProgress = (): Record<string, TutorialProgressEntry> => {
    try {
        if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
            return {};
        }
        const stored = localStorage.getItem(STORAGE_KEY);
        return stored ? JSON.parse(stored) : {};
    } catch (error) {
        console.error('Failed to load tutorial progress from localStorage:', error);
        return {};
    }
};

// Save to localStorage
const persistProgress = (progressMap: Record<string, TutorialProgressEntry>): void => {
    try {
        if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
            return;
        }
        localStorage.setItem(STORAGE_KEY, JSON.stringify(progressMap));
    } catch (error) {
        console.error('Failed to save tutorial progress to localStorage:', error);
    }
};

export const useTutorialProgress = create<TutorialProgressState>()((set, get) => ({
    progressMap: loadProgress(),

    getProgressList: () => {
        const map = get().progressMap;
        return Object.values(map).sort((a, b) => b.updated_at - a.updated_at);
    },

    getProgress: (tutorialId: string) => {
        return get().progressMap[tutorialId] ?? null;
    },

    saveProgress: (tutorialId: string, currentStep: number, completedSteps: string[]) => {
        set((state) => {
            const newMap = {
                ...state.progressMap,
                [tutorialId]: {
                    tutorial_id: tutorialId,
                    current_step: currentStep,
                    completed_steps: completedSteps,
                    updated_at: Date.now(),
                },
            };
            persistProgress(newMap);
            return { progressMap: newMap };
        });
    },

    hasAnyProgress: () => {
        return Object.keys(get().progressMap).length > 0;
    },
}));
