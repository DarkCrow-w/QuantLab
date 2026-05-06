/**
 * Agent WebSocket 客户端 + REST 辅助函数。
 */

import axios from 'axios';
import type { SessionSummary } from '../types';

const api = axios.create({ baseURL: '/api/agent', timeout: 120_000 });

// ── WebSocket ──

export function createAgentWebSocket(): WebSocket {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const host = window.location.host;
  return new WebSocket(`${proto}://${host}/api/agent/chat`);
}

// ── REST ──

export async function fetchSessions(): Promise<SessionSummary[]> {
  const { data } = await api.get<SessionSummary[]>('/sessions');
  return data;
}

export async function deleteSession(sessionId: string): Promise<void> {
  await api.delete(`/sessions/${sessionId}`);
}
