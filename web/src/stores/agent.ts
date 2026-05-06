/**
 * Agent 聊天 Zustand Store — 管理 WebSocket 连接、消息列表、流式状态。
 */

import { create } from 'zustand';
import type { AgentStatus, AgentToolCall, ChatMessage, ServerFrame, SessionSummary } from '../types';
import { createAgentWebSocket, deleteSession, fetchSessions } from '../api/agent';

interface AgentStore {
  // 会话
  sessionId: string | null;
  sessions: SessionSummary[];

  // 消息
  messages: ChatMessage[];

  // 流式状态
  isStreaming: boolean;
  streamingContent: string;
  activeAgents: AgentStatus[];
  pendingToolCalls: AgentToolCall[];

  // WebSocket
  ws: WebSocket | null;
  connected: boolean;

  // Actions
  connect: () => void;
  disconnect: () => void;
  sendMessage: (content: string, images?: string[]) => void;
  clearSession: () => void;
  loadSessions: () => Promise<void>;
  removeSession: (id: string) => Promise<void>;
}

let msgIdCounter = 0;
const nextId = () => `msg_${Date.now()}_${++msgIdCounter}`;
const toolCallId = () => `tc_${Date.now()}_${++msgIdCounter}`;

export const useAgentStore = create<AgentStore>((set, get) => ({
  sessionId: null,
  sessions: [],
  messages: [],
  isStreaming: false,
  streamingContent: '',
  activeAgents: [],
  pendingToolCalls: [],
  ws: null,
  connected: false,

  connect: () => {
    const { ws } = get();
    if (ws && ws.readyState <= WebSocket.OPEN) return;

    const socket = createAgentWebSocket();

    socket.onopen = () => {
      set({ ws: socket, connected: true });
    };

    socket.onclose = () => {
      set({ ws: null, connected: false });
    };

    socket.onerror = () => {
      set({ ws: null, connected: false });
    };

    socket.onmessage = (event) => {
      try {
        const frame: ServerFrame = JSON.parse(event.data);
        handleFrame(frame, set, get);
      } catch {
        // ignore parse errors
      }
    };

    set({ ws: socket });
  },

  disconnect: () => {
    const { ws } = get();
    if (ws) {
      ws.close();
      set({ ws: null, connected: false });
    }
  },

  sendMessage: (content: string, images?: string[]) => {
    const { ws, connected, sessionId } = get();
    if (!ws || !connected) {
      // 自动重连
      get().connect();
      // 延迟发送
      setTimeout(() => get().sendMessage(content, images), 500);
      return;
    }

    // 添加用户消息到列表
    const userMsg: ChatMessage = {
      id: nextId(),
      role: 'user',
      content,
      images,
      timestamp: Date.now(),
    };
    set((s) => ({ messages: [...s.messages, userMsg] }));

    // 发送到服务端
    const payload: Record<string, unknown> = {
      type: 'message',
      session_id: sessionId,
      content,
    };
    if (images?.length) {
      payload.images = images.map((data) => ({
        data,
        media_type: 'image/png',
      }));
    }
    ws.send(JSON.stringify(payload));

    set({ isStreaming: true, streamingContent: '', activeAgents: [], pendingToolCalls: [] });
  },

  clearSession: () => {
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
    const sessions = await fetchSessions();
    set({ sessions });
  },

  removeSession: async (id: string) => {
    await deleteSession(id);
    set((s) => ({ sessions: s.sessions.filter((ss) => ss.session_id !== id) }));
    if (get().sessionId === id) {
      get().clearSession();
    }
  },
}));

// ── WebSocket 帧处理 ──

function handleFrame(
  frame: ServerFrame,
  set: (fn: AgentStore | Partial<AgentStore> | ((s: AgentStore) => Partial<AgentStore>)) => void,
  get: () => AgentStore,
) {
  switch (frame.type) {
    case 'session_init':
      set({ sessionId: frame.session_id ?? null });
      break;

    case 'text_delta':
      if (frame.content) {
        set((s) => ({ streamingContent: s.streamingContent + frame.content }));
      }
      break;

    case 'agent_dispatch':
      if (frame.agent) {
        const displayNames: Record<string, string> = {
          backtest_agent: '回测专家',
          screening_agent: '选股专家',
          market_agent: '行情专家',
          rag_agent: '知识检索',
          chart_agent: '图表分析',
        };
        set((s) => ({
          activeAgents: [
            ...s.activeAgents.filter((a) => a.name !== frame.agent),
            {
              name: frame.agent!,
              displayName: displayNames[frame.agent!] ?? frame.agent!,
              status: 'working',
              task: frame.content,
            },
          ],
        }));
      }
      break;

    case 'agent_complete':
      if (frame.agent) {
        set((s) => ({
          activeAgents: s.activeAgents.map((a) =>
            a.name === frame.agent ? { ...a, status: 'done' as const } : a,
          ),
        }));
      }
      break;

    case 'tool_call':
      if (frame.tool) {
        const tc: AgentToolCall = {
          id: toolCallId(),
          tool: frame.tool,
          agent: frame.agent,
          input: frame.input ?? {},
          status: 'running',
        };
        set((s) => ({ pendingToolCalls: [...s.pendingToolCalls, tc] }));
      }
      break;

    case 'tool_result':
      if (frame.tool) {
        set((s) => ({
          pendingToolCalls: s.pendingToolCalls.map((tc) =>
            tc.tool === frame.tool && tc.status === 'running'
              ? { ...tc, result: frame.data, status: 'done' as const }
              : tc,
          ),
        }));
      }
      break;

    case 'error':
      // 将错误作为 assistant 消息显示
      set((s) => ({
        isStreaming: false,
        messages: [
          ...s.messages,
          {
            id: nextId(),
            role: 'assistant',
            content: `⚠️ ${frame.error ?? '未知错误'}`,
            timestamp: Date.now(),
          },
        ],
      }));
      break;

    case 'done': {
      // 将 streamingContent 和 pendingToolCalls 合并为最终 assistant 消息
      const { streamingContent, pendingToolCalls } = get();
      const assistantMsg: ChatMessage = {
        id: nextId(),
        role: 'assistant',
        content: streamingContent,
        toolCalls: pendingToolCalls.length > 0 ? [...pendingToolCalls] : undefined,
        timestamp: Date.now(),
      };
      set((s) => ({
        isStreaming: false,
        streamingContent: '',
        pendingToolCalls: [],
        activeAgents: [],
        messages: [...s.messages, assistantMsg],
      }));
      break;
    }
  }
}
