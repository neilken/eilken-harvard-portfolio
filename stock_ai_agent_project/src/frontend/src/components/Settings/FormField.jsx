import React from 'react';
import { Input } from '@/components/ui/input';

export default function FormField({ label, value, onChange, type = "text", placeholder }) {
  return (
    <div className="mb-4">
      <label className="block text-sm font-medium text-gray-700 mb-2">
        {label}
      </label>
      <Input
        type={type}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className="w-full"
      />
    </div>
  );
}