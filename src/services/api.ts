/**
 * RingCare AI - API client.
 *
 *   Ring -> FastAPI (OpenCV + AI assessment) -> /api (Vite proxy in dev) -> this client -> UI
 *
 * Events, cameras, summary and chart data come from the FastAPI backend.
 * Caregiver settings and camera on/off preferences stay in this browser (localStorage).
 */

import {
  Event,
  Camera,
  DashboardSummary,
  HourlyActivityBucket,
  CaregiverSettings,
  EventFilterCriteria,
} from '../types/events';
import { mockBackendStore } from './mockApi'; // settings only

const BASE = '/api';
const CAM_PREF_KEY = 'ringcare_camera_offline_v1';

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + path, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
    });
  } catch {
    throw new ApiError(0, 'Cannot reach the backend. Is it running on port 8000?');
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = j.detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<T>;
}

function loadOfflineIds(): string[] {
  try {
    return JSON.parse(localStorage.getItem(CAM_PREF_KEY) || '[]');
  } catch {
    return [];
  }
}

function applyFilters(events: Event[], c?: EventFilterCriteria): Event[] {
  let result = [...events];
  if (c?.status && c.status !== 'all') result = result.filter(e => e.aiStatus === c.status);
  if (c?.cameraId) result = result.filter(e => e.cameraId === c.cameraId);
  if (c?.severity && c.severity !== 'all') result = result.filter(e => e.severity === c.severity);
  if (c?.searchQuery && c.searchQuery.trim()) {
    const q = c.searchQuery.toLowerCase();
    result = result.filter(
      e =>
        e.cameraName.toLowerCase().includes(q) ||
        e.summary.toLowerCase().includes(q) ||
        e.recommendedAction.toLowerCase().includes(q) ||
        e.eventType.toLowerCase().includes(q)
    );
  }
  return result.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
}

export interface FetchResult {
  events: Event[];
  source: 'ring' | 'sample';
  notes: string[];
}

export const ringCareApi = {
  async getEvents(criteria?: EventFilterCriteria): Promise<Event[]> {
    return applyFilters(await http<Event[]>('/events'), criteria);
  },

  /** Full event including keyframe thumbnail (list responses omit it to stay small). */
  async getEvent(id: string): Promise<Event | null> {
    try {
      return await http<Event>(`/events/${encodeURIComponent(id)}`);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) return null;
      throw e;
    }
  },

  acknowledgeEvent(id: string, caregiverNote?: string): Promise<Event> {
    return http<Event>(`/events/${encodeURIComponent(id)}/acknowledge`, {
      method: 'POST',
      body: JSON.stringify({ note: caregiverNote ?? null }),
    });
  },

  dismissEvent(id: string, caregiverNote?: string): Promise<Event> {
    return http<Event>(`/events/${encodeURIComponent(id)}/dismiss`, {
      method: 'POST',
      body: JSON.stringify({ note: caregiverNote ?? null }),
    });
  },

  async getCameras(): Promise<Camera[]> {
    const offline = new Set(loadOfflineIds());
    const cams = await http<Camera[]>('/cameras');
    return cams.map(c => (offline.has(c.id) ? { ...c, status: 'offline' as const } : c));
  },

  async toggleCameraState(id: string): Promise<Camera> {
    const offline = new Set(loadOfflineIds());
    if (offline.has(id)) offline.delete(id);
    else offline.add(id);
    try {
      localStorage.setItem(CAM_PREF_KEY, JSON.stringify([...offline]));
    } catch {
      /* ignore quota errors */
    }
    const cam = (await ringCareApi.getCameras()).find(c => c.id === id);
    if (!cam) throw new ApiError(404, `Camera ${id} not found`);
    return cam;
  },

  getDashboardSummary(): Promise<DashboardSummary> {
    return http<DashboardSummary>('/dashboard/summary');
  },

  getHourlyActivity(): Promise<HourlyActivityBucket[]> {
    return http<HourlyActivityBucket[]>('/analytics/hourly-activity');
  },

  async getSettings(): Promise<CaregiverSettings> {
    try {
      return await http<CaregiverSettings>('/settings');
    } catch {
      return mockBackendStore.getSettings();
    }
  },

  async updateSettings(partial: Partial<CaregiverSettings>): Promise<CaregiverSettings> {
    const cur = await ringCareApi.getSettings();
    const updated = { ...cur, ...partial };
    try {
      return await http<CaregiverSettings>('/settings', {
        method: 'PUT',
        body: JSON.stringify(updated),
      });
    } catch {
      return mockBackendStore.updateSettings(partial);
    }
  },

  /**
   * Header button. If Ring is configured on the backend, pull new events + clips from Ring.
   * Otherwise (no token yet) analyse a local sample clip so the dashboard can still be demoed.
   */
  async fetchNewEvents(): Promise<FetchResult> {
    const health = await http<{ ring_configured: boolean }>('/health');
    if (health.ring_configured) {
      const r = await http<{ added: number; events: Event[]; notes: string[] }>('/ring/sync', {
        method: 'POST',
        body: JSON.stringify({ limit: 5 }),
      });
      return { events: r.events, source: 'ring', notes: r.notes };
    }
    const ev = await http<Event>('/events/simulate', { method: 'POST', body: JSON.stringify({}) });
    return { events: [ev], source: 'sample', notes: ['Ring is not configured - analysed a local sample clip.'] };
  },

  async resetDemoData(): Promise<void> {
    await http('/reset', { method: 'POST' });
    mockBackendStore.resetAll();
    try {
      localStorage.removeItem(CAM_PREF_KEY);
    } catch {
      /* ignore */
    }
  },

  /** Live updates via Server-Sent Events. Returns an unsubscribe function. */
  subscribeToEvents(onEvent: (e: Event) => void): () => void {
    if (typeof EventSource === 'undefined') return () => {};
    const es = new EventSource(`${BASE}/stream`);
    es.onmessage = msg => {
      try {
        onEvent(JSON.parse(msg.data) as Event);
      } catch {
        /* ignore malformed frames */
      }
    };
    return () => es.close(); // EventSource auto-reconnects on network errors
  },
};
