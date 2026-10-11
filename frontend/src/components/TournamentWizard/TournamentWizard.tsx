import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { startWizard, saveWizardStep, finalizeWizard, getWizardProgress, WizardProgressResponse } from '@/api/tournamentWizard';

// Import step components (to be created)
import TournamentBasicsStep from './steps/TournamentBasicsStep';
import PlayerRegistrationStep from './steps/PlayerRegistrationStep';
import ParticipantsStep from './steps/ParticipantsStep';
import DivisionsStep from './steps/DivisionsStep';
import ScheduleStep from './steps/ScheduleStep';
import RulesStep from './steps/RulesStep';
import ReviewStep from './steps/ReviewStep';

interface WizardStep {
  id: number;
  title: string;
  component: React.ComponentType<StepProps>;
}

export interface StepProps {
  data: Record<string, any>;
  onNext: (stepData: Record<string, any>, isComplete: boolean) => void;
  onBack: () => void;
  isFirstStep: boolean;
  isLastStep: boolean;
}

interface TournamentWizardProps {
  setupMode: 'manual' | 'wizard';
  onComplete?: (tournamentId: string) => void;
  onCancel?: () => void;
}

const TournamentWizard: React.FC<TournamentWizardProps> = ({
  setupMode,
  onComplete,
  onCancel
}) => {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(0);
  const [tournamentId, setTournamentId] = useState<string | null>(null);
  const [stepData, setStepData] = useState<Record<number, Record<string, any>>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<WizardProgressResponse | null>(null);

  const wizardSteps: WizardStep[] = [
    { id: 1, title: 'Tournament Basics', component: TournamentBasicsStep },
    { id: 2, title: 'Player Registration', component: PlayerRegistrationStep },
    { id: 3, title: 'Participants', component: ParticipantsStep },
    { id: 4, title: 'Divisions', component: DivisionsStep },
    { id: 5, title: 'Schedule', component: ScheduleStep },
    { id: 6, title: 'Rules & Settings', component: RulesStep },
    { id: 7, title: 'Review & Confirm', component: ReviewStep },
  ];

  // Initialize wizard session
  useEffect(() => {
    const initWizard = async () => {
      if (setupMode !== 'wizard') return;
      
      setLoading(true);
      setError(null);
      
      try {
        const response = await startWizard({
          setup_mode: setupMode,
          is_test_tournament: false
        });
        
        setTournamentId(response.tournament_id);
        setCurrentStep(0);
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to start wizard');
      } finally {
        setLoading(false);
      }
    };

    initWizard();
  }, [setupMode]);

  // Load wizard progress and hydrate step data from saved progress
  useEffect(() => {
    const loadProgress = async () => {
      if (!tournamentId) return;
      
      try {
        const progressData = await getWizardProgress(tournamentId);
        setProgress(progressData);
        const wp = progressData.wizard_progress || {};
        const nextStepData: Record<number, Record<string, any>> = {};
        [1, 2, 3, 4, 5, 6].forEach((stepNum) => {
          const key = `step_${stepNum}_${['', 'basics', 'participants', 'divisions', 'schedule', 'rules', 'review'][stepNum]}`;
          const stepEntry = wp[key];
          if (stepEntry?.data && Object.keys(stepEntry.data).length > 0) {
            nextStepData[stepNum] = stepEntry.data;
          }
        });
        if (Object.keys(nextStepData).length > 0) {
          setStepData((prev) => ({ ...prev, ...nextStepData }));
        }
      } catch (err) {
        console.error('Failed to load progress:', err);
      }
    };

    loadProgress();
  }, [tournamentId, currentStep]);

  const handleStepNext = async (data: Record<string, any>, isComplete: boolean) => {
    if (!tournamentId) return;
    
    // Step index 1 is Player Registration (UI-only); no backend save
    if (currentStep === 1) {
      if (currentStep < wizardSteps.length - 1) {
        setCurrentStep(currentStep + 1);
      }
      return;
    }
    
    setLoading(true);
    setError(null);
    
    try {
      // Map frontend step index to backend step number (1-based; skip index 1)
      const stepNumber = currentStep < 2 ? currentStep + 1 : currentStep;
      await saveWizardStep(tournamentId, {
        step_number: stepNumber,
        data,
        is_complete: isComplete
      });
      
      // Update local state
      setStepData(prev => ({ ...prev, [stepNumber]: data }));
      
      // Move to next step
      if (currentStep < wizardSteps.length - 1) {
        setCurrentStep(currentStep + 1);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save step');
    } finally {
      setLoading(false);
    }
  };

  const handleStepBack = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleFinalize = async () => {
    if (!tournamentId) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const result = await finalizeWizard(tournamentId);
      
      if (result.success) {
        if (onComplete) {
          onComplete(tournamentId);
        } else {
          navigate('/tournaments');
        }
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to finalize wizard');
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    if (onCancel) {
      onCancel();
    } else {
      navigate('/tournaments');
    }
  };

  if (error && !tournamentId) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center p-6">
        <div className="bg-red-900/20 border border-red-500 rounded-lg p-6 max-w-md">
          <h2 className="text-xl font-bold text-red-400 mb-2">Error</h2>
          <p className="text-gray-300">{error}</p>
          <button
            onClick={handleCancel}
            className="mt-4 px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded transition-colors"
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }

  const CurrentStepComponent = wizardSteps[currentStep]?.component;

  return (
    <div className="min-h-screen bg-slate-950 p-6">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-3xl font-bold text-white">
              Tournament Setup Wizard
            </h1>
            <button
              onClick={handleCancel}
              className="px-4 py-2 text-gray-400 hover:text-white transition-colors"
            >
              Cancel
            </button>
          </div>
          
          {/* Progress Indicator */}
          <div className="flex items-center justify-between mb-2">
            {wizardSteps.map((step, index) => (
              <React.Fragment key={step.id}>
                <div className="flex flex-col items-center">
                  <div
                    className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold transition-colors ${
                      index < currentStep
                        ? 'bg-green-600 text-white'
                        : index === currentStep
                        ? 'bg-sky-500 text-white'
                        : 'bg-slate-700 text-gray-400'
                    }`}
                  >
                    {index < currentStep ? '✓' : step.id}
                  </div>
                  <span
                    className={`mt-2 text-xs ${
                      index === currentStep ? 'text-white font-semibold' : 'text-gray-400'
                    }`}
                  >
                    {step.title}
                  </span>
                </div>
                {index < wizardSteps.length - 1 && (
                  <div
                    className={`flex-1 h-1 mx-2 rounded transition-colors ${
                      index < currentStep ? 'bg-green-600' : 'bg-slate-700'
                    }`}
                  />
                )}
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="mb-6 p-4 bg-red-900/20 border border-red-500 rounded-lg">
            <p className="text-red-400">{error}</p>
          </div>
        )}

        {/* Step Content */}
        <div className="bg-slate-900 rounded-lg p-8 shadow-xl">
          {loading && !CurrentStepComponent ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-sky-500"></div>
            </div>
          ) : CurrentStepComponent ? (
            <CurrentStepComponent
              data={{
                ...(stepData[currentStep === 0 ? 1 : currentStep] || {}),
                tournamentId: tournamentId ?? undefined,
              }}
              onNext={handleStepNext}
              onBack={handleStepBack}
              isFirstStep={currentStep === 0}
              isLastStep={currentStep === wizardSteps.length - 1}
            />
          ) : null}
        </div>

        {/* Finalize Button (shown on last step) */}
        {currentStep === wizardSteps.length - 1 && progress?.can_finalize && (
          <div className="mt-6 flex justify-end">
            <button
              onClick={handleFinalize}
              disabled={loading}
              className="px-6 py-3 bg-green-600 hover:bg-green-500 disabled:bg-gray-600 text-white font-semibold rounded-lg transition-colors"
            >
              {loading ? 'Finalizing...' : 'Complete Setup'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default TournamentWizard;
