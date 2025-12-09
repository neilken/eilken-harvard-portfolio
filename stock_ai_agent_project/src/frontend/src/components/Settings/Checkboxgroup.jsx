import React from 'react';

export default function CheckboxGroup({ label, selectedValues = [], onChange, options }) {
  const handleCheckboxChange = (value) => {
    let newValues;
    if (selectedValues.includes(value)) {
      // Remove if already selected
      newValues = selectedValues.filter(v => v !== value);
    } else {
      // Add if not selected
      newValues = [...selectedValues, value];
    }
    onChange(newValues);
  };

  return (
    <div className="mb-4">
      <label className="block text-sm font-medium text-gray-700 mb-3">
        {label}
      </label>
      <div className="space-y-2">
        {options.map((option) => (
          <label 
            key={option.value} 
            className="flex items-center p-2 hover:bg-gray-50 rounded cursor-pointer"
          >
            <input
              type="checkbox"
              checked={selectedValues.includes(option.value)}
              onChange={() => handleCheckboxChange(option.value)}
              className="w-4 h-4 text-teal-600 border-gray-300 rounded focus:ring-teal-500"
            />
            <span className="ml-3 text-sm text-gray-700">
              {option.label}
            </span>
          </label>
        ))}
      </div>
    </div>
  );
}