import React, { useState } from 'react';
import { StepProps } from '../TournamentWizard';

const DivisionsStep: React.FC<StepProps> = ({
  data,
  onNext,
  onBack,
  isFirstStep,
  isLastStep
}) => {
  const [formData, setFormData] = useState({
    use_divisions: data.use_divisions !== undefined ? data.use_divisions : false,
    division_count: data.division_count || 1,
    division_method: data.division_method || 'skill-level',
    skill_level_ranges: data.skill_level_ranges || '',
  });

  const handleNext = () => {
    onNext(formData, true);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white mb-2">Divisions</h2>
        <p className="text-gray-400">Configure tournament divisions and brackets</p>
      </div>

      <div className="space-y-4">
        {/* Use Divisions */}
        <div className="flex items-center space-x-3">
          <input
            type="checkbox"
            id="use_divisions"
            checked={formData.use_divisions}
            onChange={(e) => setFormData({ ...formData, use_divisions: e.target.checked })}
            className="w-5 h-5 bg-slate-800 border-slate-700 rounded focus:ring-2 focus:ring-sky-500"
          />
          <label htmlFor="use_divisions" className="text-sm font-medium text-gray-300">
            Use multiple divisions
          </label>
        </div>

        {formData.use_divisions && (
          <>
            {/* Division Count */}
            <div>
              <label htmlFor="division_count" className="block text-sm font-medium text-gray-300 mb-2">
                Number of Divisions
              </label>
              <input
                type="number"
                id="division_count"
                min="1"
                max="10"
                value={formData.division_count}
                onChange={(e) => setFormData({ ...formData, division_count: parseInt(e.target.value) })}
                className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
            </div>

            {/* Division Method */}
            <div>
              <label htmlFor="division_method" className="block text-sm font-medium text-gray-300 mb-2">
                Division Method
              </label>
              <select
                id="division_method"
                value={formData.division_method}
                onChange={(e) => setFormData({ ...formData, division_method: e.target.value })}
                className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
              >
                <option value="skill-level">By Skill Level (FARGO)</option>
                <option value="age">By Age Group</option>
                <option value="gender">By Gender</option>
                <option value="manual">Manual Assignment</option>
              </select>
            </div>

            {/* Skill Level Ranges */}
            {formData.division_method === 'skill-level' && (
              <div>
                <label htmlFor="skill_level_ranges" className="block text-sm font-medium text-gray-300 mb-2">
                  Skill Level Ranges (one per line, e.g., "0-400", "401-600")
                </label>
                <textarea
                  id="skill_level_ranges"
                  rows={4}
                  value={formData.skill_level_ranges}
                  onChange={(e) => setFormData({ ...formData, skill_level_ranges: e.target.value })}
                  className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
                  placeholder="0-400&#10;401-600&#10;601-800&#10;801-1000"
                />
              </div>
            )}
          </>
        )}
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

export default DivisionsStep;
