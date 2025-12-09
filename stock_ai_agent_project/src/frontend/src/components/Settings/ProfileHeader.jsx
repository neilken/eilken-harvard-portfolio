import React from 'react';
import { Camera } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function ProfileHeader({ user, onEditPhoto }) {
  return (
    <div className="bg-gradient-to-r from-teal-500 to-teal-600 p-8 rounded-t-lg">
      <div className="flex items-center space-x-6">
        <div className="relative">
          <div className="w-24 h-24 rounded-full bg-white flex items-center justify-center text-3xl font-bold text-teal-600">
            {user.name.charAt(0)}
          </div>
          <Button 
            onClick={onEditPhoto}
            size="sm"
            className="absolute bottom-0 right-0 bg-white p-2 rounded-full shadow-lg hover:bg-gray-100"
          >
            <Camera className="w-4 h-4 text-teal-600" />
          </Button>
        </div>
        <div className="text-white">
          <h1 className="text-3xl font-bold">{user.name}</h1>
          <p className="text-teal-100">{user.email}</p>
          <p className="text-sm text-teal-200 mt-1">Member since {user.joinDate}</p>
        </div>
      </div>
    </div>
  );
}