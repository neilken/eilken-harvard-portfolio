import React from 'react';
import { ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';

export default function SettingItem({ icon: Icon, title, description, action, rightElement }) {
  return (
    <>
      <div className="flex items-center justify-between py-3">
        <div className="flex items-center flex-1">
          <Icon className="w-5 h-5 text-gray-600 mr-3" />
          <div>
            <p className="font-medium text-gray-900">{title}</p>
            {description && (
              <p className="text-sm text-gray-600">{description}</p>
            )}
          </div>
        </div>
        <div className="flex items-center">
          {rightElement || (
            action && (
              <Button 
                variant="ghost"
                size="sm"
                onClick={action}
                className="text-teal-600 hover:text-teal-700"
              >
                <ChevronRight className="w-5 h-5" />
              </Button>
            )
          )}
        </div>
      </div>
      <Separator />
    </>
  );
}