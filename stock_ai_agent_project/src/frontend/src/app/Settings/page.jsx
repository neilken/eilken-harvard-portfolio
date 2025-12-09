'use client'

import React, { useState, useEffect } from 'react';
import { User, Settings, Bell, Shield, Lock, Mail, Phone, Globe, LogOut, Trash2, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import ProfileHeader from '@/components/Settings/ProfileHeader';
import SettingsSection from '@/components/Settings/SettingsSection';
import FormField from '@/components/Settings/FormField';
import SelectField from '@/components/Settings/SelectField';
import CheckboxGroup from '@/components/Settings/Checkboxgroup';
import ToggleSwitch from '@/components/Settings/ToggleSwitch';
import SettingItem from '@/components/Settings/SettingItem';

export default function SettingsPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  
  const [user, setUser] = useState({
    name: '',
    email: '',
    phone: '',
    joinDate: ''
  });

  const [profile, setProfile] = useState({
    riskTolerance: 'moderate',
    investmentGoal: 'long-term',
    investmentHorizon: '10-years',
    preferredSectors: ['technology'] // Changed to array for multiple selection
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

  // Load settings from localStorage on mount
  useEffect(() => {
    const loadSettings = () => {
      try {
        // Load user settings from localStorage
        const savedUser = localStorage.getItem('user_profile');
        const savedInvestment = localStorage.getItem('investment_profile');
        const savedNotifications = localStorage.getItem('notifications');
        const savedPreferences = localStorage.getItem('preferences');

        if (savedUser) {
          setUser(JSON.parse(savedUser));
        } else {
          // Set default user info
          setUser({
            name: 'Investor',
            email: 'user@example.com',
            phone: '',
            joinDate: new Date().toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
          });
        }

        if (savedInvestment) {
          const parsed = JSON.parse(savedInvestment);
          // Ensure preferredSectors is always an array
          if (typeof parsed.preferredSectors === 'string') {
            parsed.preferredSectors = [parsed.preferredSectors];
          }
          setProfile(parsed);
        }
        
        if (savedNotifications) setNotifications(JSON.parse(savedNotifications));
        if (savedPreferences) setPreferences(JSON.parse(savedPreferences));

      } catch (error) {
        console.error('Error loading settings:', error);
      } finally {
        setLoading(false);
      }
    };

    loadSettings();
  }, []);

  // Save user profile
  const handleSaveProfile = async () => {
    try {
      setSaving(true);
      localStorage.setItem('user_profile', JSON.stringify(user));
      alert('Profile updated successfully!');
    } catch (error) {
      console.error('Error saving profile:', error);
      alert('Failed to save profile');
    } finally {
      setSaving(false);
    }
  };

  // Save investment profile
  const handleSaveInvestment = async () => {
    try {
      setSaving(true);
      localStorage.setItem('investment_profile', JSON.stringify(profile));
      alert('Investment profile saved successfully!');
    } catch (error) {
      console.error('Error saving investment profile:', error);
      alert('Failed to save investment profile');
    } finally {
      setSaving(false);
    }
  };

  // Save notifications
  useEffect(() => {
    localStorage.setItem('notifications', JSON.stringify(notifications));
  }, [notifications]);

  // Save preferences
  useEffect(() => {
    localStorage.setItem('preferences', JSON.stringify(preferences));
  }, [preferences]);

  // Handle logout
  const handleLogout = () => {
    if (confirm('Are you sure you want to log out?')) {
      localStorage.removeItem('userSessionId');
      window.location.href = '/';
    }
  };

  // Handle account deletion
  const handleDeleteAccount = () => {
    if (confirm('⚠️ WARNING: This will permanently delete your account and all data. This action cannot be undone. Are you sure?')) {
      if (confirm('Are you ABSOLUTELY sure? Type DELETE in the next prompt to confirm.')) {
        const confirmation = prompt('Type DELETE to confirm account deletion:');
        if (confirmation === 'DELETE') {
          localStorage.clear();
          alert('Account deleted successfully');
          window.location.href = '/';
        }
      }
    }
  };

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
    { value: 'consumer', label: 'Consumer Goods' },
    { value: 'industrials', label: 'Industrials' },
    { value: 'realestate', label: 'Real Estate' },
    { value: 'utilities', label: 'Utilities' }
  ];

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-teal-600 mx-auto mb-4" />
          <p className="text-gray-600">Loading settings...</p>
        </div>
      </div>
    );
  }

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
          <ProfileHeader 
            user={user} 
            onEditPhoto={() => alert('Photo upload coming soon!')} 
          />
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
                placeholder="Enter your full name"
              />
              <FormField
                label="Email Address"
                type="email"
                value={user.email}
                onChange={(e) => setUser({...user, email: e.target.value})}
                placeholder="your.email@example.com"
              />
              <FormField
                label="Phone Number"
                type="tel"
                value={user.phone}
                onChange={(e) => setUser({...user, phone: e.target.value})}
                placeholder="+1 (555) 123-4567"
              />
              <Button 
                className="w-full mt-4 bg-teal-500 hover:bg-teal-600"
                onClick={handleSaveProfile}
                disabled={saving}
              >
                {saving ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Saving...
                  </>
                ) : (
                  'Update Profile'
                )}
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
              
              {/* Checkboxes for Preferred Sectors */}
              <CheckboxGroup
                label="Preferred Sectors (Select all that apply)"
                selectedValues={profile.preferredSectors}
                onChange={(newSectors) => setProfile({...profile, preferredSectors: newSectors})}
                options={sectorOptions}
              />
              
              <Button 
                className="w-full mt-4 bg-teal-500 hover:bg-teal-600"
                onClick={handleSaveInvestment}
                disabled={saving}
              >
                {saving ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Saving...
                  </>
                ) : (
                  'Save Investment Profile'
                )}
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
                action={() => alert('Password change feature coming soon!')}
              />
              <SettingItem
                icon={Shield}
                title="Two-Factor Auth"
                description="Add extra security"
                action={() => alert('2FA feature coming soon!')}
              />
              <SettingItem
                icon={Phone}
                title="Login Activity"
                description="View recent logins"
                action={() => alert('Login activity feature coming soon!')}
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
                onClick={handleLogout}
              >
                <LogOut className="w-4 h-4 mr-2" />
                Log Out
              </Button>
              <Button 
                className="w-full bg-red-600 hover:bg-red-700 text-white"
                onClick={handleDeleteAccount}
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