import { create } from 'zustand';
import type {
  AgentRuntimeStatus,
  AgentMode,
  AgentStatus,
  AgentToolCall,
  ChatMessage,
  ServerFrame,
  SessionSummary,
} from '../types';
import {
  createAgentWebSocket,
  deleteSession,
  fetchAgentRuntime,
  fetchSessions,
} from '../api/agent';

type ConnectionState = 'offline' | 'connecting' | 'connected' | 'error';
type CachedConversation = {
  sessionId: string | null;
  messages: ChatMessage[];
};

const AGENT_MODES: AgentMode[] = [
  'auto',
  'quant',
  'market',
  'screening',
  'backtest',
];
const CONVERSATION_STORAGE_KEY = 'quantlab.agent.conversations.v1';
const SELECTED_MODE_STORAGE_KEY = 'quantlab.agent.selected-mode.v1';

const emptyConversation = (): CachedConversation => ({
  sessionId: null,
  messages: [],
});

const loadConversationCache = (): Record<AgentMode, CachedConversation> => {
  const initial = Object.fromEntries(
    AGENT_MODES.map((mode) => [mode, emptyConversation()]),
  ) as Record<AgentMode, CachedConversation>;
  if (typeof window === 'undefined') return initial;
  try {
    const stored = JSON.parse(
      window.localStorage.getItem(CONVERSATION_STORAGE_KEY) ?? '{}',
    ) as Partial<Record<AgentMode, CachedConversation>>;
    for (const mode of AGENT_MODES) {
      const conversation = stored[mode];
      if (conversation && Array.isArray(conversation.messages)) {
        initial[mode] = {
          sessionId: conversation.sessionId ?? null,
          messages: conversation.messages,
        };
      }
    }
  } catch {
    window.localStorage.removeItem(CONVERSATION_STORAGE_KEY);
  }
  return initial;
};

const loadSelectedMode = (): AgentMode => {
  if (typeof window === 'undefined') return 'auto';
  const stored = window.localStorage.getItem(SELECTED_MODE_STORAGE_KEY);
  return AGENT_MODES.includes(stored as AgentMode)
    ? (stored as AgentMode)
    : 'auto';
};

let conversationCache = loadConversationCache();
const initialSelectedMode = loadSelectedMode();

const persistConversation = (
  mode: AgentMode,
  sessionId: string | null,
  messages: ChatMessage[],
) => {
  conversationCache = {
    ...conversationCache,
    [mode]: { sessionId, messages },
  };
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(
      CONVERSATION_STORAGE_KEY,
      JSON.stringify(conversationCache),
    );
  }
};

interface AgentStore {
  selectedMode: AgentMode;
  sessionId: string | null;
  sessions: SessionSummary[];
  messages: ChatMessage[];
  isStreaming: boolean;
  streamingContent: string;
  activeAgents: AgentStatus[];
  pendingToolCalls: AgentToolCall[];
  ws: WebSocket | null;
  connected: boolean;
  connectionState: ConnectionState;
  connectionError: string | null;
  runtime: AgentRuntimeStatus | null;
  setAgentMode: (mode: AgentMode) => void;
  connect: () => void;
  disconnect: () => void;
  reconnect: () => void;
  loadRuntime: () => Promise<void>;
  sendMessage: (content: string, images?: string[]) => void;
  stopGeneration: () => void;
  clearSession: () => void;
  loadSessions: () => Promise<void>;
  removeSession: (id: string) => Promise<void>;
}

let counter = 0;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let reconnectAttempts = 0;
let allowReconnect = true;
let pendingPayload: Record<string, unknown> | null = null;
let stopRequested = false;

const nextId = (prefix = 'msg') => `${prefix}_${Date.now()}_${++counter}`;

const assistantMessage = (content: string): ChatMessage => ({
  id: nextId(),
  role: 'assistant',
  content,
  timestamp: Date.now(),
});

export const useAgentStore = create<AgentStore>((set, get) => ({
  selectedMode: initialSelectedMode,
  sessionId: conversationCache[initialSelectedMode].sessionId,
  sessions: [],
  messages: conversationCache[initialSelectedMode].messages,
  isStreaming: false,
  streamingContent: '',
  activeAgents: [],
  pendingToolCalls: [],
  ws: null,
  connected: false,
  connectionState: 'offline',
  connectionError: null,
  runtime: null,

  setAgentMode: (mode) => {
    if (mode === get().selectedMode || get().isStreaming) return;
    pendingPayload = null;
    const current = get();
    persistConversation(
      current.selectedMode,
      current.sessionId,
      current.messages,
    );
    const next = conversationCache[mode] ?? emptyConversation();
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(SELECTED_MODE_STORAGE_KEY, mode);
    }
    set({
      selectedMode: mode,
      sessionId: next.sessionId,
      messages: next.messages,
      streamingContent: '',
      activeAgents: [],
      pendingToolCalls: [],
      connectionError: null,
    });
  },

  loadRuntime: async () => {
    try {
      const runtime = await fetchAgentRuntime();
      set({ runtime, connectionError: runtime.reason ?? null });
    } catch (error: unknown) {
      set({
        runtime: null,
        connectionState: 'error',
        connectionError:
          error instanceof Error ? error.message : '无法读取 Agent 运行状态',
      });
    }
  },

  connect: () => {
    const current = get().ws;
    if (
      current &&
      (current.readyState === WebSocket.OPEN ||
        current.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    allowReconnect = true;
    set({ connectionState: 'connecting', connectionError: null });
    const socket = createAgentWebSocket();
    set({ ws: socket });

    socket.onopen = () => {
      if (get().ws !== socket) return;
      reconnectAttempts = 0;
      set({
        connected: true,
        connectionState: 'connected',
        connectionError: null,
      });
      if (pendingPayload) {
        socket.send(JSON.stringify(pendingPayload));
        pendingPayload = null;
      }
    };

    socket.onmessage = (event) => {
      try {
        handleFrame(JSON.parse(event.data) as ServerFrame, set, get);
        const state = get();
        persistConversation(
          state.selectedMode,
          state.sessionId,
          state.messages,
        );
      } catch {
        set({ connectionError: '收到无法解析的 Agent 消息' });
      }
    };

    socket.onerror = () => {
      if (get().ws !== socket) return;
      set({
        connectionState: 'error',
        connectionError: '研究服务连接失败',
      });
    };

    socket.onclose = () => {
      if (get().ws !== socket) return;
      set({ ws: null, connected: false, connectionState: 'offline' });
      if (get().isStreaming && !stopRequested) {
        set((state) => ({
          isStreaming: false,
          messages: [
            ...state.messages,
            assistantMessage('连接中断，本次分析未完成。'),
          ],
        }));
        const state = get();
        persistConversation(
          state.selectedMode,
          state.sessionId,
          state.messages,
        );
      }
      stopRequested = false;
      if (allowReconnect) {
        reconnectAttempts += 1;
        const delay = Math.min(15_000, 750 * 2 ** (reconnectAttempts - 1));
        reconnectTimer = setTimeout(() => get().connect(), delay);
      }
    };
  },

  disconnect: () => {
    allowReconnect = false;
    pendingPayload = null;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    get().ws?.close();
    set({
      ws: null,
      connected: false,
      connectionState: 'offline',
    });
  },

  reconnect: () => {
    allowReconnect = true;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    get().ws?.close();
    set({ ws: null, connected: false });
    setTimeout(() => get().connect(), 50);
  },

  sendMessage: (content, images) => {
    const text = content.trim();
    if ((!text && !images?.length) || get().isStreaming) return;

    const userMessage: ChatMessage = {
      id: nextId(),
      role: 'user',
      content: text,
      images,
      timestamp: Date.now(),
    };
    const payload: Record<string, unknown> = {
      type: 'message',
      session_id: get().sessionId,
      content: text,
      agent_mode: get().selectedMode,
    };
    if (images?.length) {
      payload.images = images.map((data) => ({
        data,
        media_type: 'image/png',
      }));
    }

    set((state) => ({
      messages: [...state.messages, userMessage],
      isStreaming: true,
      streamingContent: '',
      activeAgents: [],
      pendingToolCalls: [],
      connectionError: null,
    }));
    const state = get();
    persistConversation(
      state.selectedMode,
      state.sessionId,
      state.messages,
    );

    const socket = get().ws;
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(payload));
    } else {
      pendingPayload = payload;
      get().connect();
    }
  },

  stopGeneration: () => {
    if (!get().isStreaming) return;
    stopRequested = true;
    pendingPayload = null;
    get().ws?.close(1000, 'cancelled');
    set((state) => ({
      isStreaming: false,
      streamingContent: '',
      activeAgents: [],
      pendingToolCalls: [],
      messages: [...state.messages, assistantMessage('已停止本次分析。')],
    }));
    const state = get();
    persistConversation(
      state.selectedMode,
      state.sessionId,
      state.messages,
    );
  },

  clearSession: () => {
    pendingPayload = null;
    const mode = get().selectedMode;
    persistConversation(mode, null, []);
    set({
      sessionId: null,
      messages: [],
      isStreaming: false,
      streamingContent: '',
      activeAgents: [],
      pendingToolCalls: [],
    });
  },

  loadSessions: async () => {
    try {
      set({ sessions: await fetchSessions() });
    } catch {
      set({ sessions: [] });
    }
  },

  removeSession: async (id) => {
    await deleteSession(id);
    set((state) => ({
      sessions: state.sessions.filter((session) => session.session_id !== id),
    }));
    if (get().sessionId === id) get().clearSession();
  },
}));

function handleFrame(
  frame: ServerFrame,
  set: (
    value:
      | Partial<AgentStore>
      | ((state: AgentStore) => Partial<AgentStore>),
  ) => void,
  get: () => AgentStore,
) {
  switch (frame.type) {
    case 'session_init':
      set({ sessionId: frame.session_id ?? null });
      break;
    case 'text_delta':
      if (frame.content) {
        set((state) => ({
          streamingContent: state.streamingContent + frame.content,
        }));
      }
      break;
    case 'agent_dispatch':
      if (frame.agent) {
        const names: Record<string, string> = {
          backtest_agent: '回测专家',
          screening_agent: '选股专家',
          market_agent: '行情专家',
          quant_agent: 'Quant Agent',
          supervisor: '研究主管',
        };
        set((state) => ({
          activeAgents: [
            ...state.activeAgents.filter((agent) => agent.name !== frame.agent),
            {
              name: frame.agent!,
              displayName: names[frame.agent!] ?? frame.agent!,
              status: 'working',
              task: frame.content,
            },
          ],
        }));
      }
      break;
    case 'agent_complete':
      if (frame.agent) {
        set((state) => ({
          activeAgents: state.activeAgents.map((agent) =>
            agent.name === frame.agent
              ? { ...agent, status: 'done' as const }
              : agent,
          ),
        }));
      }
      break;
    case 'tool_call':
      if (frame.tool) {
        set((state) => ({
          pendingToolCalls: [
            ...state.pendingToolCalls,
            {
              id: nextId('tool'),
              tool: frame.tool!,
              agent: frame.agent,
              input: frame.input ?? {},
              status: 'running',
            },
          ],
        }));
      }
      break;
    case 'tool_result':
      if (frame.tool) {
        const calls = [...get().pendingToolCalls];
        const index = calls.findIndex(
          (call) => call.tool === frame.tool && call.status === 'running',
        );
        if (index >= 0) {
          calls[index] = {
            ...calls[index],
            result: frame.data,
            status: 'done',
          };
          set({ pendingToolCalls: calls });
        }
      }
      break;
    case 'error':
      pendingPayload = null;
      set((state) => ({
        isStreaming: false,
        streamingContent: '',
        activeAgents: [],
        messages: [
          ...state.messages,
          assistantMessage(frame.error ?? 'Agent 执行失败'),
        ],
      }));
      break;
    case 'done': {
      const { streamingContent, pendingToolCalls } = get();
      set((state) => ({
        isStreaming: false,
        streamingContent: '',
        pendingToolCalls: [],
        activeAgents: [],
        messages: [
          ...state.messages,
          {
            id: nextId(),
            role: 'assistant',
            content: streamingContent || '分析已完成。',
            toolCalls:
              pendingToolCalls.length > 0 ? [...pendingToolCalls] : undefined,
            timestamp: Date.now(),
          },
        ],
      }));
      break;
    }
  }
}
