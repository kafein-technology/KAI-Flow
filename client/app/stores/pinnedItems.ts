import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';

export interface PinnedItem {
  id: string;
  type: 'workflow' | 'chat';
  title: string;
  description?: string;
  pinnedAt: string;
  metadata?: {
    status?: string;
    lastActivity?: string;
    messageCount?: number;
  };
}

interface PinnedItemsState {
  pinnedItems: PinnedItem[];

  // Actions
  addPinnedItem: (item: Omit<PinnedItem, 'pinnedAt'>) => void;
  removePinnedItem: (id: string, type: 'workflow' | 'chat') => void;
  isPinned: (id: string, type: 'workflow' | 'chat') => boolean;
  getPinnedItems: (type?: 'workflow' | 'chat') => PinnedItem[];
  clearAllPinnedItems: () => void;
  updatePinnedItem: (id: string, type: 'workflow' | 'chat', updates: Partial<PinnedItem>) => void;
}

const STORAGE_KEY = 'kai_flow_pinned_items';

// Helper function to load pinned items from localStorage
const loadPinnedItems = (): PinnedItem[] => {
  try {
    // Check if localStorage is available (client-side only)
    if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
      return [];
    }
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch (error) {
    console.error('Failed to load pinned items from localStorage:', error);
    return [];
  }
};

// Helper function to save pinned items to localStorage
const savePinnedItems = (items: PinnedItem[]): void => {
  try {
    // Check if localStorage is available (client-side only)
    if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
      return;
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  } catch (error) {
    console.error('Failed to save pinned items to localStorage:', error);
  }
};

const pinnedItemsStateCreator = (set: any, get: any) => ({
  pinnedItems: loadPinnedItems(),

  addPinnedItem: (item: Omit<PinnedItem, 'pinnedAt'>) => {
    const newItem: PinnedItem = {
      ...item,
      pinnedAt: new Date().toISOString(),
    };

    set((state: PinnedItemsState) => {
      // Check if item already exists
      const exists = state.pinnedItems.some(
        (pinned: PinnedItem) => pinned.id === item.id && pinned.type === item.type
      );

      if (exists) {
        return state; // Don't add if already pinned
      }

      const newPinnedItems = [...state.pinnedItems, newItem];
      savePinnedItems(newPinnedItems);
      return { pinnedItems: newPinnedItems };
    });
  },

  removePinnedItem: (id: string, type: 'workflow' | 'chat') => {
    set((state: PinnedItemsState) => {
      const newPinnedItems = state.pinnedItems.filter(
        (item: PinnedItem) => !(item.id === id && item.type === type)
      );
      savePinnedItems(newPinnedItems);
      return { pinnedItems: newPinnedItems };
    });
  },

  isPinned: (id: string, type: 'workflow' | 'chat') => {
    const state = get();
    return state.pinnedItems.some(
      (item: PinnedItem) => item.id === id && item.type === type
    );
  },

  getPinnedItems: (type?: 'workflow' | 'chat') => {
    const state = get();
    if (type) {
      return state.pinnedItems.filter((item: PinnedItem) => item.type === type);
    }
    return state.pinnedItems;
  },

  clearAllPinnedItems: () => {
    set({ pinnedItems: [] });
    savePinnedItems([]);
  },

  updatePinnedItem: (id: string, type: 'workflow' | 'chat', updates: Partial<PinnedItem>) => {
    set((state: PinnedItemsState) => {
      const newPinnedItems = state.pinnedItems.map((item: PinnedItem) =>
        item.id === id && item.type === type
          ? { ...item, ...updates }
          : item
      );
      savePinnedItems(newPinnedItems);
      return { pinnedItems: newPinnedItems };
    });
  },
});

export const usePinnedItems = create<PinnedItemsState>()(
  subscribeWithSelector(pinnedItemsStateCreator)
);

// Subscribe to changes and save to localStorage
usePinnedItems.subscribe(
  (state) => state.pinnedItems,
  (pinnedItems) => {
    savePinnedItems(pinnedItems);
  }
);
