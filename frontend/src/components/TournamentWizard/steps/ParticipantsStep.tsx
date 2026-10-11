import React, { useState } from 'react';
import { StepProps } from '../TournamentWizard';

const ParticipantsStep: React.FC<StepProps> = ({
  data,
  onNext,
  onBack,
  isFirstStep,
  isLastStep
}) => {
  const [formData, setFormData] = useState({
    registration_method: data.registration_method || 'open',
    allow_walk_ins: data.allow_walk_ins !== undefined ? data.allow_walk_ins : true,
    advance_registration_required: data.advance_registration_required || false,
    registration_deadline: data.registration_deadline || '',
    entry_fee: data.entry_fee || 0,
  });

  const handleNext = () => {
    onNext(formData, true);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white mb-2">Participants</h2>
        <p className="text-gray-400">Configure how players can register for your tournament</p>
      </div>

      <div className="space-y-4">
        {/* Registration Method */}
        <div>
          <label htmlFor="registration_method" className="block text-sm font-medium text-gray-300 mb-2">
            Registration Method
          </label>
          <select
            id="registration_method"
            value={formData.registration_method}
            onChange={(e) => setFormData({ ...formData, registration_method: e.target.value })}
            className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
          >
            <option value="open">Open Registration</option>
            <option value="invite-only">Invite Only</option>
            <option value="qualification">Qualification Required</option>
          </select>
        </div>

        {/* Allow Walk-ins */}
        <div className="flex items-center space-x-3">
          <input
            type="checkbox"
            id="allow_walk_ins"
            checked={formData.allow_walk_ins}
            onChange={(e) => setFormData({ ...formData, allow_walk_ins: e.target.checked })}
            className="w-5 h-5 bg-slate-800 border-slate-700 rounded focus:ring-2 focus:ring-sky-500"
          />
          <label htmlFor="allow_walk_ins" className="text-sm font-medium text-gray-300">
            Allow walk-in registration on tournament day
          </label>
        </div>

        {/* Advance Registration Required */}
        <div className="flex items-center space-x-3">
          <input
            type="checkbox"
            id="advance_registration_required"
            checked={formData.advance_registration_required}
            onChange={(e) => setFormData({ ...formData, advance_registration_required: e.target.checked })}
            className="w-5 h-5 bg-slate-800 border-slate-700 rounded focus:ring-2 focus:ring-sky-500"
          />
          <label htmlFor="advance_registration_required" className="text-sm font-medium text-gray-300">
            Require advance registration
          </label>
        </div>

        {/* Registration Deadline */}
        {formData.advance_registration_required && (
          <div>
            <label htmlFor="registration_deadline" className="block text-sm font-medium text-gray-300 mb-2">
              Registration Deadline
            </label>
            <input
              type="datetime-local"
              id="registration_deadline"
              value={formData.registration_deadline}
              onChange={(e) => setFormData({ ...formData, registration_deadline: e.target.value })}
              className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
          </div>
        )}

        {/* Entry Fee */}
        <div>
          <label htmlFor="entry_fee" className="block text-sm font-medium text-gray-300 mb-2">
            Entry Fee ($)
          </label>
          <input
            type="number"
            id="entry_fee"
            min="0"
            step="0.01"
            value={formData.entry_fee}
            onChange={(e) => setFormData({ ...formData, entry_fee: parseFloat(e.target.value) })}
            className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
          />
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
          onClick={handleNext}
          className="px-6 py-2 bg-sky-500 hover:bg-sky-400 text-white rounded-lg transition-colors"
        >
          Next
        </button>
      </div>
    </div>
  );
};

export default ParticipantsStep;
