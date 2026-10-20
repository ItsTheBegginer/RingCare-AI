export type EventStatus = 'normal' | 'review' | 'acknowledged' | 'dismissed';
export type EventSeverity = 'low' | 'medium' | 'high';
export type EventType = 'motion' | 'person' | 'stationary' | 'door_access';
export interface CVAnalysis {
  personDetected: boolean;
  motionDetected: boolean;
  motionScore: number; // 0.00 to 1.00
  stationaryDuration: number; // in seconds
  confidence: number; // e.g. 0.94
  primaryZone: string;
  postureEstimation?: 'standing' | 'sitting' | 'reclined' | 'ambulatory' | 'floor_level';
  boundingBoxes?: Array<{
    id: string;
    label: string;
    confidence: number;
    color: string;
    rect: { top: number; left: number; width: number; height: number }; // percentages 0-100
  }>;
}
export type EventCategory = 'caretaking' | 'security' | 'both';
export interface FallIndicator {
  level: 'none' | 'possible' | 'likely';
  signals: string[];
  missedSignals?: string[];
}
export interface SecuritySignal {
  label: string;
  confidence: number;
  frameTime?: number;
}
export interface SecurityIndicator {
  level: 'none' | 'possible';
  signals: SecuritySignal[];
  notes?: string;
}
export interface AIAssessment {
  statusLabel: string;
  summary: string;
  recommendedAction: string;
  urgency: 'routine' | 'prompt' | 'immediate';
  rationale: string;
  evidence?: string[];
  limitations?: string[];
  analysisVersion?: string;
}
export type VideoStatus = 'ring_clip' | 'converted' | 'sample' | 'unavailable' | 'error';
export interface Event {
  id: string;
  cameraId: string;
  cameraName: string;
  eventType: EventType;
  timestamp: string; // ISO 8601 string
  personDetected: boolean;
  motionScore: number; // 0.00 to 1.00
  stationaryDuration: number; // in seconds
  aiStatus: EventStatus;
  severity: EventSeverity;
  summary: string;
  recommendedAction: string;
  cvAnalysis: CVAnalysis;
  aiAssessment: AIAssessment;
  category?: EventCategory;
  fallIndicator?: FallIndicator;
  securityIndicator?: SecurityIndicator;
  source?: string; // 'ring' | 'ring+sample-clip' | 'simulated'
  videoStatus?: VideoStatus;
  engine?: string; // 'rules'
  thumbnail?: string | null; // base64 JPEG keyframe (only on single-event fetch)
  clipUrl?: string | null; // MP4 clip served by the backend
  actionLog?: {
    action: 'acknowledged' | 'dismissed';
    timestamp: string;
    caregiverNote?: string;
    actor: string;
  };
}
export interface Camera {
  id: string;
  name: string;
  location: string;
  status: 'online' | 'offline';
  lastActivity: string;
  motionEventsToday: number;
  reviewEventsToday: number;
  resolution: string;
  signalStrength: 'excellent' | 'good' | 'fair';
  batteryPercentage?: number;
  firmwareVersion: string;
  zoneTags: string[];
}
export interface DashboardSummary {
  todayEventsCount: number;
  requiresReviewCount: number;
  normalActivityCount: number;
  camerasOnlineCount: number;
  totalCamerasCount: number;
  lastUpdated: string;
  monitoringActive: boolean;
}
export interface HourlyActivityBucket {
  hourLabel: string; // e.g., "12 AM", "03 AM", "06 AM"
  totalEvents: number;
  reviewEvents: number;
  normalEvents: number;
  motionAverage: number;
}
export interface CaregiverSettings {
  monitoringEnabled: boolean;
  reviewNotificationsEnabled: boolean;
  soundAlertsEnabled: boolean;
  stationaryAlertThresholdSeconds: number;
  aiReviewSensitivity: 'low' | 'balanced' | 'high';
  cameraNightModeEnhance: boolean;
  securityDetectionEnabled: boolean;
  residentProfile: {
    name: string;
    residence: string;
    emergencyContact: string;
    emergencyPhone: string;
    notes: string;
  };
}
export interface EventFilterCriteria {
  status?: 'all' | EventStatus;
  cameraId?: string;
  severity?: 'all' | EventSeverity;
  searchQuery?: string;
  timeRange?: 'today' | 'all';
}
