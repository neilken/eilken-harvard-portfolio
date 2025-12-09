import React from 'react';
import { Card } from '@/components/ui/card';

export default function SettingsSection({ title, icon: Icon, children }) {
  return (
    <Card className="mb-4 overflow-hidden">
      <div className="bg-gray-50 px-6 py-4 border-b border-gray-200">
        <div className="flex items-center">
          <Icon className="w-5 h-5 text-teal-600 mr-3" />
          <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
        </div>
      </div>
      <div className="p-6">
        {children}
      </div>
    </Card>
  );
}