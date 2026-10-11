import React from 'react';
import { StepProps } from '../TournamentWizard';

const ReviewStep: React.FC<StepProps> = ({
  data,
  onNext,
  onBack,
  isFirstStep,
  isLastStep
}) => {
  // In a real implementation, you would gather data from all previous steps
  // For now, this displays the data from the current step
  
  const handleConfirm = () => {
    onNext(data, true);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white mb-2">Review & Confirm</h2>
        <p className="text-gray-400">Review your tournament settings before finalizing</p>
      </div>

      <div className="bg-slate-800 rounded-lg p-6 space-y-4">
        <div className="pb-4 border-b border-slate-700">
          <h3 className="text-lg font-semibold text-white mb-3">Summary</h3>
          <p className="text-gray-300">
            Please review all settings from the previous steps. If everything looks correct,
            click "Confirm & Continue" below. You can go back to any step to make changes.
          </p>
        </div>

        <div className="space-y-3 text-sm">
          <div className="flex justify-between py-2">
            <span className="text-gray-400">Tournament Basics:</span>
            <span className="text-green-400">✓ Complete</span>
          </div>
          <div className="flex justify-between py-2">
            <span className="text-gray-400">Participants:</span>
            <span className="text-green-400">✓ Complete</span>
          </div>
          <div className="flex justify-between py-2">
            <span className="text-gray-400">Divisions:</span>
            <span className="text-green-400">✓ Complete</span>
          </div>
          <div className="flex justify-between py-2">
            <span className="text-gray-400">Schedule:</span>
            <span className="text-green-400">✓ Complete</span>
          </div>
          <div className="flex justify-between py-2">
            <span className="text-gray-400">Rules & Settings:</span>
            <span className="text-green-400">✓ Complete</span>
          </div>
        </div>

        <div className="pt-4 border-t border-slate-700">
          <div className="bg-sky-900/20 border border-sky-700 rounded p-4">
            <p className="text-sky-300 text-sm">
              <strong>Note:</strong> After confirming, your tournament will be set to
              "Registration" status, and players will be able to register. You can still
              make changes from the tournament management page.
            </p>
          </div>
        </div>
      </div>

      {/* Navigation Buttons */}
      <div className="flex justify-between pt-6 border-t border-slate-700">
        <button
          onClick={onBack}
          className="px-6 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
        >
          Back
        </button>
        <button
          onClick={handleConfirm}
          className="px-6 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg transition-colors font-semibold"
        >
          Confirm & Continue
        </button>
      </div>
    </div>
  );
};

export default ReviewStep;
