import React, { useState } from 'react';
import { StepProps } from '../TournamentWizard';

const RulesStep: React.FC<StepProps> = ({
  data,
  onNext,
  onBack,
  isFirstStep,
  isLastStep
}) => {
  const [formData, setFormData] = useState({
    points_structure: data.points_structure || {
      '1': 3600,
      '2': 2880,
      '3': 2400,
      '4': 2040,
      '5': 1680,
    },
    race_to: data.race_to || 7,
    break_rules: data.break_rules || 'alternate',
    handicap_system: data.handicap_system || 'none',
    custom_rules: data.custom_rules || '',
  });

  const handleNext = () => {
    onNext(formData, true);
  };

  const handlePointsChange = (placement: string, value: number) => {
    setFormData({
      ...formData,
      points_structure: {
        ...formData.points_structure,
        [placement]: value
      }
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white mb-2">Rules & Settings</h2>
        <p className="text-gray-400">Configure tournament rules and point structure</p>
      </div>

      <div className="space-y-4">
        {/* Race To */}
        <div>
          <label htmlFor="race_to" className="block text-sm font-medium text-gray-300 mb-2">
            Race To (games per match)
          </label>
          <input
            type="number"
            id="race_to"
            min="1"
            max="21"
            value={formData.race_to}
            onChange={(e) => setFormData({ ...formData, race_to: parseInt(e.target.value) })}
            className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
          />
        </div>

        {/* Break Rules */}
        <div>
          <label htmlFor="break_rules" className="block text-sm font-medium text-gray-300 mb-2">
            Break Rules
          </label>
          <select
            id="break_rules"
            value={formData.break_rules}
            onChange={(e) => setFormData({ ...formData, break_rules: e.target.value })}
            className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
          >
            <option value="alternate">Alternate Breaks</option>
            <option value="winner">Winner Breaks</option>
            <option value="loser">Loser Breaks</option>
            <option value="rack-winner">Rack Winner Breaks</option>
          </select>
        </div>

        {/* Handicap System */}
        <div>
          <label htmlFor="handicap_system" className="block text-sm font-medium text-gray-300 mb-2">
            Handicap System
          </label>
          <select
            id="handicap_system"
            value={formData.handicap_system}
            onChange={(e) => setFormData({ ...formData, handicap_system: e.target.value })}
            className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
          >
            <option value="none">No Handicap</option>
            <option value="fargo">FARGO-based</option>
            <option value="skill-level">Skill Level</option>
          </select>
        </div>

        {/* Points Structure */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Points Structure
          </label>
          <div className="space-y-2">
            {Object.entries(formData.points_structure).map(([placement, points]) => (
              <div key={placement} className="flex items-center space-x-3">
                <span className="text-gray-400 w-20">Place {placement}:</span>
                <input
                  type="number"
                  min="0"
                  step="1"
                  value={points}
                  onChange={(e) => handlePointsChange(placement, parseFloat(e.target.value))}
                  className="flex-1 px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
                />
                <span className="text-gray-400 text-sm">points</span>
              </div>
            ))}
          </div>
        </div>

        {/* Custom Rules */}
        <div>
          <label htmlFor="custom_rules" className="block text-sm font-medium text-gray-300 mb-2">
            Custom Rules & Notes
          </label>
          <textarea
            id="custom_rules"
            rows={4}
            value={formData.custom_rules}
            onChange={(e) => setFormData({ ...formData, custom_rules: e.target.value })}
            className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
            placeholder="Enter any additional rules or notes..."
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

export default RulesStep;
