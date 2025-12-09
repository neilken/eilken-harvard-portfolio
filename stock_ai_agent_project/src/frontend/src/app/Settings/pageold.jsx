'use client'

import React, { useState } from 'react';
import { User, Settings, Bell, Shield, Lock, Mail, Phone, Globe, LogOut, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import ProfileHeader from '@/components/Settings/ProfileHeader';
import SettingsSection from '@/components/Settings/SettingsSection';
import FormField from '@/components/Settings/FormField';
import SelectField from '@/components/Settings/SelectField';
import ToggleSwitch from '@/components/Settings/ToggleSwitch';
import SettingItem from '@/components/Settings/SettingItem';

export default function SettingsPage() {
  const [user, setUser] = useState({
    name: 'John Investor',
    email: 'john.investor@example.com',
    phone: '+1 (555) 123-4567',
    joinDate: 'January 2024'
  });

  const [profile, setProfile] = useState({
    riskTolerance: 'moderate',
    investmentGoal: 'long-term',
    investmentHorizon: '10-years',
    preferredSectors: 'technology'
  });

  const [notifications, setNotifications] = useState({
    priceAlerts: true,
    marketNews: true,
    portfolioUpdates: false,
    emailDigest: true
  });

  const [preferences, setPreferences] = useState({
    language: 'english',
    currency: 'usd',
    timezone: 'est'
  });

  const riskOptions = [
    { value: 'conservative', label: 'Conservative - Minimize risk' },
    { value: 'moderate', label: 'Moderate - Balanced approach' },
    { value: 'aggressive', label: 'Aggressive - Maximum growth' }
  ];

  const goalOptions = [
    { value: 'short-term', label: 'Short-term Growth (1-3 years)' },
    { value: 'long-term', label: 'Long-term Wealth (10+ years)' },
    { value: 'retirement', label: 'Retirement Planning' },
    { value: 'income', label: 'Income Generation' }
  ];

  const horizonOptions = [
    { value: '1-year', label: '1 Year' },
    { value: '3-years', label: '3 Years' },
    { value: '5-years', label: '5 Years' },
    { value: '10-years', label: '10+ Years' }
  ];

  const sectorOptions = [
    { value: 'technology', label: 'Technology' },
    { value: 'healthcare', label: 'Healthcare' },
    { value: 'finance', label: 'Finance' },
    { value: 'energy', label: 'Energy' },
    { value: 'diversified', label: 'Diversified' }
  ];

  return (
    <div className="min-h-screen bg-gray-100 pt-20 pb-12 px-4">
      <div className="container mx-auto max-w-7xl">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl md:text-4xl font-bold text-teal-600">
            Settings & Profile
          </h1>
          <p className="text-gray-600 mt-2">
            Manage your account preferences and investment profile
          </p>
        </div>

        {/* Profile Header Card */}
        <Card className="mb-6 overflow-hidden">
          <ProfileHeader user={user} onEditPhoto={() => alert('Edit photo clicked')} />
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Profile & Investment Settings */}
          <div className="lg:col-span-2 space-y-6">
            {/* Personal Information */}
            <SettingsSection title="Personal Information" icon={User}>
              <FormField
                label="Full Name"
                value={user.name}
                onChange={(e) => setUser({...user, name: e.target.value})}
              />
              <FormField
                label="Email Address"
                type="email"
                value={user.email}
                onChange={(e) => setUser({...user, email: e.target.value})}
              />
              <FormField
                label="Phone Number"
                type="tel"
                value={user.phone}
                onChange={(e) => setUser({...user, phone: e.target.value})}
              />
              <Button className="w-full mt-4 bg-teal-500 hover:bg-teal-600">
                Update Profile
              </Button>
            </SettingsSection>

            {/* Investment Profile */}
            <SettingsSection title="Investment Profile" icon={Settings}>
              <SelectField
                label="Risk Tolerance"
                value={profile.riskTolerance}
                onChange={(e) => setProfile({...profile, riskTolerance: e.target.value})}
                options={riskOptions}
              />
              <SelectField
                label="Investment Goal"
                value={profile.investmentGoal}
                onChange={(e) => setProfile({...profile, investmentGoal: e.target.value})}
                options={goalOptions}
              />
              <SelectField
                label="Investment Horizon"
                value={profile.investmentHorizon}
                onChange={(e) => setProfile({...profile, investmentHorizon: e.target.value})}
                options={horizonOptions}
              />
              <SelectField
                label="Preferred Sectors"
                value={profile.preferredSectors}
                onChange={(e) => setProfile({...profile, preferredSectors: e.target.value})}
                options={sectorOptions}
              />
              <Button className="w-full mt-4 bg-teal-500 hover:bg-teal-600">
                Save Investment Profile
              </Button>
            </SettingsSection>

            {/* Notifications */}
            <SettingsSection title="Notifications" icon={Bell}>
              <SettingItem
                icon={Bell}
                title="Price Alerts"
                description="Get notified when stocks hit your target price"
                rightElement={
                  <ToggleSwitch
                    enabled={notifications.priceAlerts}
                    onChange={() => setNotifications({...notifications, priceAlerts: !notifications.priceAlerts})}
                  />
                }
              />
              <SettingItem
                icon={Globe}
                title="Market News"
                description="Receive breaking market news and updates"
                rightElement={
                  <ToggleSwitch
                    enabled={notifications.marketNews}
                    onChange={() => setNotifications({...notifications, marketNews: !notifications.marketNews})}
                  />
                }
              />
              <SettingItem
                icon={Mail}
                title="Portfolio Updates"
                description="Daily summary of your portfolio performance"
                rightElement={
                  <ToggleSwitch
                    enabled={notifications.portfolioUpdates}
                    onChange={() => setNotifications({...notifications, portfolioUpdates: !notifications.portfolioUpdates})}
                  />
                }
              />
              <SettingItem
                icon={Mail}
                title="Email Digest"
                description="Weekly email with insights and recommendations"
                rightElement={
                  <ToggleSwitch
                    enabled={notifications.emailDigest}
                    onChange={() => setNotifications({...notifications, emailDigest: !notifications.emailDigest})}
                  />
                }
              />
            </SettingsSection>
          </div>

          {/* Right Column - Quick Actions & Security */}
          <div className="space-y-6">
            {/* Security & Privacy */}
            <SettingsSection title="Security" icon={Shield}>
              <SettingItem
                icon={Lock}
                title="Change Password"
                description="Update your password"
                action={() => alert('Change password clicked')}
              />
              <SettingItem
                icon={Shield}
                title="Two-Factor Auth"
                description="Add extra security"
                action={() => alert('2FA clicked')}
              />
              <SettingItem
                icon={Phone}
                title="Login Activity"
                description="View recent logins"
                action={() => alert('Login activity clicked')}
              />
            </SettingsSection>

            {/* App Preferences */}
            <SettingsSection title="Preferences" icon={Globe}>
              <SelectField
                label="Language"
                value={preferences.language}
                onChange={(e) => setPreferences({...preferences, language: e.target.value})}
                options={[
                  { value: 'english', label: 'English' },
                  { value: 'spanish', label: 'Spanish' },
                  { value: 'french', label: 'French' }
                ]}
              />
              <SelectField
                label="Currency"
                value={preferences.currency}
                onChange={(e) => setPreferences({...preferences, currency: e.target.value})}
                options={[
                  { value: 'usd', label: 'USD ($)' },
                  { value: 'eur', label: 'EUR (€)' },
                  { value: 'gbp', label: 'GBP (£)' }
                ]}
              />
            </SettingsSection>

            {/* Danger Zone */}
            <Card className="bg-red-50 border-red-200 p-6">
              <h3 className="text-lg font-semibold text-red-900 mb-4">Danger Zone</h3>
              <Button 
                variant="outline" 
                className="w-full mb-3 border-red-300 text-red-700 hover:bg-red-50"
              >
                <LogOut className="w-4 h-4 mr-2" />
                Log Out
              </Button>
              <Button 
                className="w-full bg-red-600 hover:bg-red-700 text-white"
              >
                <Trash2 className="w-4 h-4 mr-2" />
                Delete Account
              </Button>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}