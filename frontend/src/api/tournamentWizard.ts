// Tournament Wizard API Client
import axios from 'axios';

const API_BASE = '/api/tournament-wizard';

export interface WizardStartRequest {
  setup_mode: 'manual' | 'wizard';
  is_test_tournament: boolean;
}

export interface WizardStartResponse {
  tournament_id: string;
  setup_mode: string;
  is_test_tournament: boolean;
  current_step: number;
  total_steps: number;
}

export interface WizardStepData {
  step_number: number;
  data: Record<string, any>;
  is_complete: boolean;
}

export interface WizardStepResponse {
  tournament_id: string;
  step_number: number;
  is_complete: boolean;
  next_step: number | null;
  wizard_progress: Record<string, any>;
}

export interface WizardProgressResponse {
  tournament_id: string;
  setup_mode: string;
  is_test_tournament: boolean;
  wizard_progress: Record<string, any>;
  current_step: number;
  completed_steps: number[];
  can_finalize: boolean;
}

// Start a new wizard session
export const startWizard = async (data: WizardStartRequest): Promise<WizardStartResponse> => {
  const response = await axios.post(`${API_BASE}/start`, data);
  return response.data;
};

// Save a wizard step
export const saveWizardStep = async (
  tournamentId: string,
  stepData: WizardStepData
): Promise<WizardStepResponse> => {
  const response = await axios.post(`${API_BASE}/${tournamentId}/step`, stepData);
  return response.data;
};

// Get wizard progress
export const getWizardProgress = async (
  tournamentId: string
): Promise<WizardProgressResponse> => {
  const response = await axios.get(`${API_BASE}/${tournamentId}/progress`);
  return response.data;
};

// Finalize wizard
export const finalizeWizard = async (
  tournamentId: string
): Promise<{ success: boolean; tournament_id: string; status: string; message: string }> => {
  const response = await axios.post(`${API_BASE}/${tournamentId}/finalize`);
  return response.data;
};
