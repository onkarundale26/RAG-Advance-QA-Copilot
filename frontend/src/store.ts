import { create } from 'zustand';

interface Source {
  index: number;
  source: string;
  type: string;
  snippet: string;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  routing?: string[];
  sources?: Source[];
  isLoading?: boolean;
}

interface ChatStore {
  messages: Message[];
  isStreaming: boolean;
  activeSources: Source[];
  
  addMessage: (msg: Message) => void;
  updateLastMessage: (content: string) => void;
  setStreaming: (val: boolean) => void;
  setRouting: (collections: string[]) => void;
  setSources: (sources: Source[]) => void;
  clearChat: () => void;
}

export const useChatStore = create<ChatStore>((set) => ({
  messages: [],
  isStreaming: false,
  activeSources: [],

  addMessage: (msg) => set((state) => ({ messages: [...state.messages, msg] })),
  
  updateLastMessage: (content) => set((state) => {
    const newMessages = [...state.messages];
    if (newMessages.length > 0) {
      newMessages[newMessages.length - 1].content += content;
    }
    return { messages: newMessages };
  }),

  setStreaming: (val) => set({ isStreaming: val }),
  
  setRouting: (collections) => set((state) => {
    const newMessages = [...state.messages];
    if (newMessages.length > 0) {
      newMessages[newMessages.length - 1].routing = collections;
    }
    return { messages: newMessages };
  }),

  setSources: (sources) => set({ activeSources: sources }),
  
  clearChat: () => set({ messages: [], activeSources: [] }),
}));
