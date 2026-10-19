import {
  Event,
  Camera,
  DashboardSummary,
  HourlyActivityBucket,
  CaregiverSettings,
  EventFilterCriteria,
} from '../types/events';

// Storage key for state persistence across page views
const STORAGE_EVENTS_KEY = 'ringcare_ai_events_v1';
const STORAGE_CAMERAS_KEY = 'ringcare_ai_cameras_v1';
const STORAGE_SETTINGS_KEY = 'ringcare_ai_settings_v1';

// Base helper to generate timestamps for today
function getTodayIso(hours: number, minutes: number, seconds = 0): string {
  const d = new Date();
  d.setHours(hours, minutes, seconds, 0);
  return d.toISOString();
}

const INITIAL_CAMERAS: Camera[] = [
  {
    id: 'cam_living_room',
    name: 'Living Room',
    location: 'Main living space & armchair zone',
    status: 'online',
    lastActivity: getTodayIso(22, 42, 31),
    motionEventsToday: 8,
    reviewEventsToday: 1,
    resolution: '1080p HD (HDR)',
    signalStrength: 'excellent',
    batteryPercentage: 92,
    firmwareVersion: 'v4.18.2-rc',
    zoneTags: ['Recliner Zone', 'Walkway', 'Coffee Table Area'],
  },
  {
    id: 'cam_bedroom',
    name: 'Bedroom',
    location: 'Primary bedroom & bedside exit',
    status: 'online',
    lastActivity: getTodayIso(21, 17, 10),
    motionEventsToday: 5,
    reviewEventsToday: 1,
    resolution: '1080p HD (Night Vision IR)',
    signalStrength: 'good',
    batteryPercentage: 88,
    firmwareVersion: 'v4.18.2-rc',
    zoneTags: ['Bed Perimeter', 'Nightstand', 'En-suite Path'],
  },
  {
    id: 'cam_front_door',
    name: 'Front Door',
    location: 'Main foyer & exterior threshold',
    status: 'online',
    lastActivity: getTodayIso(20, 51, 45),
    motionEventsToday: 5,
    reviewEventsToday: 0,
    resolution: '1080p HD (Wide 160°)',
    signalStrength: 'excellent',
    firmwareVersion: 'v4.19.0-rc',
    zoneTags: ['Entry Porch', 'Doorbell Step', 'Foyer Vestibule'],
  },
  {
    id: 'cam_kitchen',
    name: 'Kitchen',
    location: 'Meal prep counter & pantry',
    status: 'online',
    lastActivity: getTodayIso(19, 15, 20),
    motionEventsToday: 4,
    reviewEventsToday: 0,
    resolution: '1080p HD',
    signalStrength: 'good',
    batteryPercentage: 96,
    firmwareVersion: 'v4.18.2-rc',
    zoneTags: ['Stove Area', 'Sink Basin', 'Dining Table'],
  },
];

const INITIAL_EVENTS: Event[] = [
  {
    id: 'evt_001',
    cameraId: 'cam_living_room',
    cameraName: 'Living Room',
    eventType: 'motion',
    timestamp: getTodayIso(22, 42, 31),
    personDetected: true,
    motionScore: 0.73,
    stationaryDuration: 6.2,
    aiStatus: 'review',
    severity: 'medium',
    summary: 'Person detected moving in the living room before remaining stationary for several seconds.',
    recommendedAction: 'Review event and verify resident is comfortable.',
    cvAnalysis: {
      personDetected: true,
      motionDetected: true,
      motionScore: 0.73,
      stationaryDuration: 6.2,
      confidence: 0.94,
      primaryZone: 'Recliner Zone',
      postureEstimation: 'sitting',
      boundingBoxes: [
        {
          id: 'box_1',
          label: 'Resident',
          confidence: 0.94,
          color: '#f59e0b',
          rect: { top: 28, left: 34, width: 28, height: 52 },
        },
        {
          id: 'box_2',
          label: 'Living Room Chair',
          confidence: 0.98,
          color: '#38bdf8',
          rect: { top: 35, left: 30, width: 36, height: 48 },
        },
      ],
    },
    aiAssessment: {
      statusLabel: 'Review Recommended',
      summary: 'A person was detected moving in the living room and then remained stationary for several seconds near the recliner chair.',
      recommendedAction: 'Review the event playback. Confirm posture stability and normal settling into the chair.',
      urgency: 'prompt',
      rationale: 'Motion stopped abruptly following a brief hesitation near furniture. Stationary duration (6.2s) crossed the configured review threshold.',
    },
  },
  {
    id: 'evt_002',
    cameraId: 'cam_bedroom',
    cameraName: 'Bedroom',
    eventType: 'stationary',
    timestamp: getTodayIso(21, 17, 10),
    personDetected: true,
    motionScore: 0.42,
    stationaryDuration: 18.5,
    aiStatus: 'review',
    severity: 'high',
    summary: 'Prolonged stillness detected near bedside table after brief stumbling motion sequence.',
    recommendedAction: 'Check resident status immediately via bedside intercom or in-person verification.',
    cvAnalysis: {
      personDetected: true,
      motionDetected: true,
      motionScore: 0.42,
      stationaryDuration: 18.5,
      confidence: 0.91,
      primaryZone: 'Bed Perimeter',
      postureEstimation: 'floor_level',
      boundingBoxes: [
        {
          id: 'box_3',
          label: 'Resident (Low Posture)',
          confidence: 0.91,
          color: '#ef4444',
          rect: { top: 54, left: 42, width: 38, height: 32 },
        },
      ],
    },
    aiAssessment: {
      statusLabel: 'Immediate Attention Advised',
      summary: 'Low-elevation posture detected adjacent to the bed. Inactivity exceeded 18 seconds without regular return-to-bed motion pattern.',
      recommendedAction: 'Initiate voice check-in or visit room to ensure no slip or fall has occurred.',
      urgency: 'immediate',
      rationale: 'Optical flow vectors indicated a sudden vertical descent followed by 18.5 seconds of static pixel regions near the carpet edge.',
    },
  },
  {
    id: 'evt_003',
    cameraId: 'cam_front_door',
    cameraName: 'Front Door',
    eventType: 'door_access',
    timestamp: getTodayIso(20, 51, 45),
    personDetected: true,
    motionScore: 0.88,
    stationaryDuration: 1.1,
    aiStatus: 'normal',
    severity: 'low',
    summary: 'Scheduled caregiver evening check-in arrival detected at front door entrance.',
    recommendedAction: 'Routine entry verified. No caregiver action required.',
    cvAnalysis: {
      personDetected: true,
      motionDetected: true,
      motionScore: 0.88,
      stationaryDuration: 1.1,
      confidence: 0.98,
      primaryZone: 'Doorbell Step',
      postureEstimation: 'standing',
      boundingBoxes: [
        {
          id: 'box_4',
          label: 'Visitor / Caregiver',
          confidence: 0.98,
          color: '#10b981',
          rect: { top: 18, left: 38, width: 24, height: 68 },
        },
      ],
    },
    aiAssessment: {
      statusLabel: 'Normal Entry Activity',
      summary: 'Authorized doorway approach matching expected caregiver check-in time window. Door unlatched normally.',
      recommendedAction: 'Event logged under routine access registry.',
      urgency: 'routine',
      rationale: 'Expected evening shift transition window. Keypad code 8820 acknowledged.',
    },
  },
  {
    id: 'evt_004',
    cameraId: 'cam_kitchen',
    cameraName: 'Kitchen',
    eventType: 'motion',
    timestamp: getTodayIso(19, 15, 20),
    personDetected: true,
    motionScore: 0.65,
    stationaryDuration: 3.2,
    aiStatus: 'normal',
    severity: 'low',
    summary: 'Evening tea preparation routine detected at kitchen counter.',
    recommendedAction: 'Routine daily living activity observed.',
    cvAnalysis: {
      personDetected: true,
      motionDetected: true,
      motionScore: 0.65,
      stationaryDuration: 3.2,
      confidence: 0.93,
      primaryZone: 'Stove Area',
      postureEstimation: 'standing',
      boundingBoxes: [
        {
          id: 'box_5',
          label: 'Resident',
          confidence: 0.93,
          color: '#10b981',
          rect: { top: 22, left: 45, width: 22, height: 60 },
        },
      ],
    },
    aiAssessment: {
      statusLabel: 'Routine ADL Activity',
      summary: 'Continuous and confident gait observed along the kitchen island. Electric kettle area accessed.',
      recommendedAction: 'No action required. Typical evening habit.',
      urgency: 'routine',
      rationale: 'Motion cadence matched baseline mobility profile with 0 anomalies detected.',
    },
  },
  {
    id: 'evt_005',
    cameraId: 'cam_living_room',
    cameraName: 'Living Room',
    eventType: 'motion',
    timestamp: getTodayIso(17, 40, 15),
    personDetected: true,
    motionScore: 0.52,
    stationaryDuration: 2.0,
    aiStatus: 'acknowledged',
    severity: 'low',
    summary: 'Resident seated in favorite armchair watching television.',
    recommendedAction: 'Acknowledged by primary caregiver during shift check.',
    cvAnalysis: {
      personDetected: true,
      motionDetected: true,
      motionScore: 0.52,
      stationaryDuration: 2.0,
      confidence: 0.96,
      primaryZone: 'Recliner Zone',
      postureEstimation: 'sitting',
      boundingBoxes: [
        {
          id: 'box_6',
          label: 'Resident',
          confidence: 0.96,
          color: '#3b82f6',
          rect: { top: 32, left: 35, width: 26, height: 50 },
        },
      ],
    },
    aiAssessment: {
      statusLabel: 'Normal Activity (Acknowledged)',
      summary: 'Expected afternoon TV viewing pattern.',
      recommendedAction: 'Logged and approved by caregiver.',
      urgency: 'routine',
      rationale: 'Caregiver note attached: resident enjoying reading and program.',
    },
    actionLog: {
      action: 'acknowledged',
      timestamp: getTodayIso(17, 45, 0),
      caregiverNote: 'Checked on Eleanor, she is reading her book happily.',
      actor: 'Nurse Sarah',
    },
  },
  {
    id: 'evt_006',
    cameraId: 'cam_front_door',
    cameraName: 'Front Door',
    eventType: 'person',
    timestamp: getTodayIso(15, 22, 10),
    personDetected: true,
    motionScore: 0.91,
    stationaryDuration: 0.8,
    aiStatus: 'dismissed',
    severity: 'low',
    summary: 'Courier package drop-off at exterior porch doorstep.',
    recommendedAction: 'Dismissed: standard non-resident delivery.',
    cvAnalysis: {
      personDetected: true,
      motionDetected: true,
      motionScore: 0.91,
      stationaryDuration: 0.8,
      confidence: 0.97,
      primaryZone: 'Entry Porch',
      postureEstimation: 'standing',
      boundingBoxes: [
        {
          id: 'box_7',
          label: 'Delivery Courier',
          confidence: 0.97,
          color: '#64748b',
          rect: { top: 15, left: 30, width: 22, height: 65 },
        },
      ],
    },
    aiAssessment: {
      statusLabel: 'Dismissed Event',
      summary: 'Exterior movement by postal worker. Left parcel and departed in 8 seconds.',
      recommendedAction: 'Parcel placed on porch table. Safe to dismiss.',
      urgency: 'routine',
      rationale: 'Exterior perimeter only, interior security untouched.',
    },
    actionLog: {
      action: 'dismissed',
      timestamp: getTodayIso(15, 25, 0),
      caregiverNote: 'Amazon package delivery confirmed via porch camera.',
      actor: 'Caregiver Marcus',
    },
  },
  {
    id: 'evt_007',
    cameraId: 'cam_bedroom',
    cameraName: 'Bedroom',
    eventType: 'stationary',
    timestamp: getTodayIso(13, 10, 0),
    personDetected: true,
    motionScore: 0.22,
    stationaryDuration: 28.0,
    aiStatus: 'normal',
    severity: 'low',
    summary: 'Afternoon scheduled rest period initiated on bed mattress.',
    recommendedAction: 'Scheduled rest cycle in progress.',
    cvAnalysis: {
      personDetected: true,
      motionDetected: false,
      motionScore: 0.22,
      stationaryDuration: 28.0,
      confidence: 0.95,
      primaryZone: 'Bed Perimeter',
      postureEstimation: 'reclined',
    },
    aiAssessment: {
      statusLabel: 'Normal Nap Cycle',
      summary: 'Resident settled comfortably on mattress. Steady respiratory rhythm estimated.',
      recommendedAction: 'Permit undisturbed rest cycle.',
      urgency: 'routine',
      rationale: 'Consistent with 1:00 PM - 2:30 PM customary nap window.',
    },
  },
  {
    id: 'evt_008',
    cameraId: 'cam_kitchen',
    cameraName: 'Kitchen',
    eventType: 'motion',
    timestamp: getTodayIso(12, 5, 40),
    personDetected: true,
    motionScore: 0.79,
    stationaryDuration: 4.1,
    aiStatus: 'normal',
    severity: 'low',
    summary: 'Lunch preparation and hydration activity detected.',
    recommendedAction: 'Positive nutritional routine observed.',
    cvAnalysis: {
      personDetected: true,
      motionDetected: true,
      motionScore: 0.79,
      stationaryDuration: 4.1,
      confidence: 0.94,
      primaryZone: 'Sink Basin',
      postureEstimation: 'standing',
    },
    aiAssessment: {
      statusLabel: 'Normal Mealtime Activity',
      summary: 'Fluid movements between refrigerator and food preparation counter.',
      recommendedAction: 'No action required.',
      urgency: 'routine',
      rationale: 'Active movement sequence lasting 18 minutes.',
    },
  },
  {
    id: 'evt_009',
    cameraId: 'cam_living_room',
    cameraName: 'Living Room',
    eventType: 'motion',
    timestamp: getTodayIso(10, 15, 12),
    personDetected: true,
    motionScore: 0.84,
    stationaryDuration: 1.5,
    aiStatus: 'normal',
    severity: 'low',
    summary: 'Morning stretching and gentle mobility walk through living room hallway.',
    recommendedAction: 'Routine healthy mobility.',
    cvAnalysis: {
      personDetected: true,
      motionDetected: true,
      motionScore: 0.84,
      stationaryDuration: 1.5,
      confidence: 0.96,
      primaryZone: 'Walkway',
      postureEstimation: 'ambulatory',
    },
    aiAssessment: {
      statusLabel: 'Normal Mobility',
      summary: 'Brisk, balanced pacing observed during physical therapy routine window.',
      recommendedAction: 'Maintain current care plan.',
      urgency: 'routine',
      rationale: 'Gait velocity within optimal safety tolerances.',
    },
  },
  {
    id: 'evt_010',
    cameraId: 'cam_bedroom',
    cameraName: 'Bedroom',
    eventType: 'person',
    timestamp: getTodayIso(7, 45, 0),
    personDetected: true,
    motionScore: 0.64,
    stationaryDuration: 4.8,
    aiStatus: 'normal',
    severity: 'low',
    summary: 'Morning wake-up routine: safely transitioned out of bed toward bathroom.',
    recommendedAction: 'Normal morning wakefulness pattern.',
    cvAnalysis: {
      personDetected: true,
      motionDetected: true,
      motionScore: 0.64,
      stationaryDuration: 4.8,
      confidence: 0.93,
      primaryZone: 'En-suite Path',
      postureEstimation: 'standing',
    },
    aiAssessment: {
      statusLabel: 'Morning Routine Confirmed',
      summary: 'Prompt transition from lying to standing posture with 0 balance loss indications.',
      recommendedAction: 'Log as normal morning waking.',
      urgency: 'routine',
      rationale: 'Normal transition time recorded.',
    },
  },
  {
    id: 'evt_011',
    cameraId: 'cam_front_door',
    cameraName: 'Front Door',
    eventType: 'door_access',
    timestamp: getTodayIso(8, 0, 15),
    personDetected: true,
    motionScore: 0.85,
    stationaryDuration: 1.2,
    aiStatus: 'acknowledged',
    severity: 'low',
    summary: 'Morning nurse arrival verified with digital door pin entry.',
    recommendedAction: 'Morning shift handover verified.',
    cvAnalysis: {
      personDetected: true,
      motionDetected: true,
      motionScore: 0.85,
      stationaryDuration: 1.2,
      confidence: 0.99,
      primaryZone: 'Doorbell Step',
      postureEstimation: 'standing',
    },
    aiAssessment: {
      statusLabel: 'Authorized Entry (Acknowledged)',
      summary: 'Healthcare staff entry confirmed via PIN authentication code.',
      recommendedAction: 'Shift transition logged.',
      urgency: 'routine',
      rationale: 'Scheduled morning nurse arrival.',
    },
    actionLog: {
      action: 'acknowledged',
      timestamp: getTodayIso(8, 2, 0),
      caregiverNote: 'Morning nurse Jessica clocked in on time.',
      actor: 'System Auto-Audit',
    },
  },
  {
    id: 'evt_012',
    cameraId: 'cam_living_room',
    cameraName: 'Living Room',
    eventType: 'motion',
    timestamp: getTodayIso(2, 30, 40),
    personDetected: true,
    motionScore: 0.48,
    stationaryDuration: 11.8,
    aiStatus: 'acknowledged',
    severity: 'medium',
    summary: 'Late night movement detected in living room before returning to bedroom.',
    recommendedAction: 'Acknowledged: resident fetched water from kitchen dispenser.',
    cvAnalysis: {
      personDetected: true,
      motionDetected: true,
      motionScore: 0.48,
      stationaryDuration: 11.8,
      confidence: 0.89,
      primaryZone: 'Coffee Table Area',
      postureEstimation: 'ambulatory',
    },
    aiAssessment: {
      statusLabel: 'Nighttime Motion (Acknowledged)',
      summary: 'Brief nocturia or hydration episode. Resident navigated back to bedroom safely.',
      recommendedAction: 'Night monitor reviewed and confirmed safety.',
      urgency: 'prompt',
      rationale: 'Total night traversal was 4 minutes; resident returned to bed unassisted.',
    },
    actionLog: {
      action: 'acknowledged',
      timestamp: getTodayIso(2, 36, 0),
      caregiverNote: 'Verified night audio; resident got water and is safely back asleep.',
      actor: 'Night On-Call Nurse',
    },
  },
];

const INITIAL_SETTINGS: CaregiverSettings = {
  monitoringEnabled: true,
  reviewNotificationsEnabled: true,
  soundAlertsEnabled: false,
  stationaryAlertThresholdSeconds: 5,
  aiReviewSensitivity: 'balanced',
  cameraNightModeEnhance: true,
  residentProfile: {
    name: 'Eleanor Vance',
    residence: 'Residence Apt 4B • Senior Community',
    emergencyContact: 'Dr. Michael Vance (Son)',
    emergencyPhone: '+1 (555) 392-1084',
    notes: 'Mild hypertension, prefers walker in evenings, prone to slow waking.',
  },
};

// State helpers with localStorage sync
class MockBackendStore {
  private events: Event[];
  private cameras: Camera[];
  private settings: CaregiverSettings;

  constructor() {
    this.events = this.loadEvents();
    this.cameras = this.loadCameras();
    this.settings = this.loadSettings();
  }

  private loadEvents(): Event[] {
    try {
      const stored = localStorage.getItem(STORAGE_EVENTS_KEY);
      if (stored) {
        return JSON.parse(stored);
      }
    } catch {
      // Fallback
    }
    return [...INITIAL_EVENTS];
  }

  private loadCameras(): Camera[] {
    try {
      const stored = localStorage.getItem(STORAGE_CAMERAS_KEY);
      if (stored) {
        return JSON.parse(stored);
      }
    } catch {
      // Fallback
    }
    return [...INITIAL_CAMERAS];
  }

  private loadSettings(): CaregiverSettings {
    try {
      const stored = localStorage.getItem(STORAGE_SETTINGS_KEY);
      if (stored) {
        return JSON.parse(stored);
      }
    } catch {
      // Fallback
    }
    return { ...INITIAL_SETTINGS };
  }

  private persist() {
    try {
      localStorage.setItem(STORAGE_EVENTS_KEY, JSON.stringify(this.events));
      localStorage.setItem(STORAGE_CAMERAS_KEY, JSON.stringify(this.cameras));
      localStorage.setItem(STORAGE_SETTINGS_KEY, JSON.stringify(this.settings));
    } catch {
      // Ignore quota errors
    }
  }

  public resetAll() {
    this.events = [...INITIAL_EVENTS];
    this.cameras = [...INITIAL_CAMERAS];
    this.settings = { ...INITIAL_SETTINGS };
    this.persist();
  }

  public getEvents(criteria?: EventFilterCriteria): Event[] {
    let result = [...this.events];

    if (!criteria) {
      return result.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
    }

    if (criteria.status && criteria.status !== 'all') {
      result = result.filter(e => e.aiStatus === criteria.status);
    }

    if (criteria.cameraId) {
      result = result.filter(e => e.cameraId === criteria.cameraId);
    }

    if (criteria.severity && criteria.severity !== 'all') {
      result = result.filter(e => e.severity === criteria.severity);
    }

    if (criteria.searchQuery && criteria.searchQuery.trim().length > 0) {
      const query = criteria.searchQuery.toLowerCase();
      result = result.filter(
        e =>
          e.cameraName.toLowerCase().includes(query) ||
          e.summary.toLowerCase().includes(query) ||
          e.recommendedAction.toLowerCase().includes(query) ||
          e.eventType.toLowerCase().includes(query)
      );
    }

    return result.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  }

  public getEventById(id: string): Event | null {
    const found = this.events.find(e => e.id === id);
    return found ? { ...found } : null;
  }

  public acknowledgeEvent(id: string, note?: string): Event {
    const idx = this.events.findIndex(e => e.id === id);
    if (idx === -1) {
      throw new Error(`Event ${id} not found.`);
    }

    const updated: Event = {
      ...this.events[idx],
      aiStatus: 'acknowledged',
      actionLog: {
        action: 'acknowledged',
        timestamp: new Date().toISOString(),
        caregiverNote: note || 'Acknowledged by caregiver via dashboard.',
        actor: 'Primary Caregiver',
      },
    };

    this.events[idx] = updated;
    this.recalculateCameraCounts();
    this.persist();
    return { ...updated };
  }

  public dismissEvent(id: string, note?: string): Event {
    const idx = this.events.findIndex(e => e.id === id);
    if (idx === -1) {
      throw new Error(`Event ${id} not found.`);
    }

    const updated: Event = {
      ...this.events[idx],
      aiStatus: 'dismissed',
      actionLog: {
        action: 'dismissed',
        timestamp: new Date().toISOString(),
        caregiverNote: note || 'Dismissed as non-critical by caregiver.',
        actor: 'Primary Caregiver',
      },
    };

    this.events[idx] = updated;
    this.recalculateCameraCounts();
    this.persist();
    return { ...updated };
  }

  public getCameras(): Camera[] {
    return [...this.cameras];
  }

  public toggleCameraStatus(cameraId: string): Camera {
    const idx = this.cameras.findIndex(c => c.id === cameraId);
    if (idx === -1) throw new Error(`Camera ${cameraId} not found`);
    const nextStatus = this.cameras[idx].status === 'online' ? 'offline' : 'online';
    this.cameras[idx] = { ...this.cameras[idx], status: nextStatus };
    this.persist();
    return { ...this.cameras[idx] };
  }

  public getDashboardSummary(): DashboardSummary {
    const totalEvents = this.events.length;
    const requiresReview = this.events.filter(e => e.aiStatus === 'review').length;
    // Normal activity is normal + acknowledged + dismissed
    const normalActivity = this.events.filter(e => e.aiStatus !== 'review').length;
    const onlineCameras = this.cameras.filter(c => c.status === 'online').length;

    return {
      todayEventsCount: totalEvents,
      requiresReviewCount: requiresReview,
      normalActivityCount: normalActivity,
      camerasOnlineCount: onlineCameras,
      totalCamerasCount: this.cameras.length,
      lastUpdated: new Date().toISOString(),
      monitoringActive: this.settings.monitoringEnabled,
    };
  }

  public getHourlyActivity(): HourlyActivityBucket[] {
    // Generate buckets for a 24-hour day broken into 4-hour intervals
    const buckets: HourlyActivityBucket[] = [
      { hourLabel: '12 AM', totalEvents: 1, reviewEvents: 0, normalEvents: 1, motionAverage: 0.32 },
      { hourLabel: '03 AM', totalEvents: 2, reviewEvents: 1, normalEvents: 1, motionAverage: 0.45 },
      { hourLabel: '06 AM', totalEvents: 1, reviewEvents: 0, normalEvents: 1, motionAverage: 0.58 },
      { hourLabel: '09 AM', totalEvents: 3, reviewEvents: 0, normalEvents: 3, motionAverage: 0.72 },
      { hourLabel: '12 PM', totalEvents: 2, reviewEvents: 0, normalEvents: 2, motionAverage: 0.68 },
      { hourLabel: '03 PM', totalEvents: 2, reviewEvents: 0, normalEvents: 2, motionAverage: 0.74 },
      { hourLabel: '06 PM', totalEvents: 2, reviewEvents: 0, normalEvents: 2, motionAverage: 0.61 },
      { hourLabel: '09 PM', totalEvents: 3, reviewEvents: 2, normalEvents: 1, motionAverage: 0.65 },
      { hourLabel: 'Now', totalEvents: 2, reviewEvents: 1, normalEvents: 1, motionAverage: 0.73 },
    ];
    return buckets;
  }

  public getSettings(): CaregiverSettings {
    return { ...this.settings };
  }

  public updateSettings(partial: Partial<CaregiverSettings>): CaregiverSettings {
    this.settings = {
      ...this.settings,
      ...partial,
      residentProfile: {
        ...this.settings.residentProfile,
        ...(partial.residentProfile || {}),
      },
    };
    this.persist();
    return { ...this.settings };
  }

  public triggerSimulatedEvent(): Event {
    const id = `evt_${Date.now()}`;
    const newEvent: Event = {
      id,
      cameraId: 'cam_living_room',
      cameraName: 'Living Room',
      eventType: 'motion',
      timestamp: new Date().toISOString(),
      personDetected: true,
      motionScore: 0.78,
      stationaryDuration: 7.4,
      aiStatus: 'review',
      severity: 'medium',
      summary: 'New motion burst detected near hallway entrance. Stationary posture noted for 7.4s.',
      recommendedAction: 'Review event and check visual posture.',
      cvAnalysis: {
        personDetected: true,
        motionDetected: true,
        motionScore: 0.78,
        stationaryDuration: 7.4,
        confidence: 0.95,
        primaryZone: 'Walkway',
        postureEstimation: 'standing',
      },
      aiAssessment: {
        statusLabel: 'Review Recommended',
        summary: 'Newly captured simulated motion event from camera feed.',
        recommendedAction: 'Check resident status to ensure comfort.',
        urgency: 'prompt',
        rationale: 'Motion cadence momentarily halted near threshold.',
      },
    };

    this.events.unshift(newEvent);
    this.recalculateCameraCounts();
    this.persist();
    return { ...newEvent };
  }

  private recalculateCameraCounts() {
    this.cameras = this.cameras.map(cam => {
      const camEvents = this.events.filter(e => e.cameraId === cam.id);
      const reviewEvents = camEvents.filter(e => e.aiStatus === 'review').length;
      return {
        ...cam,
        motionEventsToday: camEvents.length,
        reviewEventsToday: reviewEvents,
      };
    });
  }
}

export const mockBackendStore = new MockBackendStore();
