import { CaregiverSettings } from '../types/events';

const STORAGE_SETTINGS_KEY = 'ringcare_ai_settings_v1';

const INITIAL_SETTINGS: CaregiverSettings = {
  monitoringEnabled: true,
  reviewNotificationsEnabled: true,
  soundAlertsEnabled: false,
  stationaryAlertThresholdSeconds: 5,
  aiReviewSensitivity: 'balanced',
  cameraNightModeEnhance: true,
  securityDetectionEnabled: true,
  residentProfile: {
    name: 'Eleanor Vance',
    residence: 'Residence Apt 4B · Senior Community',
    emergencyContact: 'Dr. Michael Vance (Son)',
    emergencyPhone: '+1 (555) 392-1084',
    notes: 'Mild hypertension, prefers walker in evenings, prone to slow waking.',
  },
};

class MockBackendStore {
  private settings: CaregiverSettings;

  constructor() {
    try {
      const stored = localStorage.getItem(STORAGE_SETTINGS_KEY);
      this.settings = stored ? JSON.parse(stored) : { ...INITIAL_SETTINGS };
    } catch {
      this.settings = { ...INITIAL_SETTINGS };
    }
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
        ...(partial.residentProfile ?? {}),
      },
    };
    try {
      localStorage.setItem(STORAGE_SETTINGS_KEY, JSON.stringify(this.settings));
    } catch {
      /* ignore quota errors */
    }
    return { ...this.settings };
  }
}

export const mockBackendStore = new MockBackendStore();
