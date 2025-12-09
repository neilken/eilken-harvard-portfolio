'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Bot, SettingsIcon, ViewIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import MarketNewsCard from '@/components/MarketNewsCard';

export default function Home() {
    const [showMarketNews, setShowMarketNews] = useState(false);
    const [mounted, setMounted] = useState(false);

    // Check if user has Market News enabled in settings
    useEffect(() => {
        setMounted(true);
        try {
            const notifications = localStorage.getItem('notifications');
            if (notifications) {
                const parsed = JSON.parse(notifications);
                setShowMarketNews(parsed.marketNews === true);
            }
        } catch (error) {
            console.error('Error loading notification settings:', error);
        }
    }, []);

    const features = [
        {
            name: 'AI SmartInvestor',
            description: 'Smart investing, made simple. Your personal AI investment guide.',
            icon: Bot,
            href: '/chat',
            color: 'text-indigo-600 dark:text-indigo-400'
        },
        {
            name: 'Settings & Preferences',
            description: 'Personalize your AI SmartInvestor experience. Update your profile, set your risk tolerance and investment goals, and manage app preferences.',
            icon: SettingsIcon,
            href: '/Settings',  // Changed from '/Settings' to '/settings' (lowercase)
            color: 'text-green-600 dark:text-green-400'
        },
        {
            name: 'About Us',
            description: 'Learn more about our vision to make investing accessible for everyone.',
            icon: ViewIcon,
            href: '/about',
            color: 'text-red-600 dark:text-red-400'
        },
    ];

    // Don't render anything until mounted to prevent hydration issues
    if (!mounted) {
        return null;
    }

    return (
        <div className="min-h-screen bg-background">
            {/* Hero Section */}
            <section className="relative py-20 px-4 sm:px-6 lg:px-8">
                <div className="max-w-7xl mx-auto text-center">
                    <h1 className="text-5xl sm:text-6xl font-bold tracking-tight mb-6">
                        Welcome to{' '}
                        <span className="text-primary">Stock Busters</span>
                    </h1>
                    <p className="text-xl text-muted-foreground max-w-2xl mx-auto mb-8">
                        Break through market complexity with AI-powered insights. Stock Busters helps you identify winning opportunities, bust through investment barriers, and take control of your portfolio with confidence.
                    </p>
                </div>
            </section>

            {/* Market News Section - Shows only if enabled in settings */}
            {showMarketNews && (
                <section className="py-8 px-4 sm:px-6 lg:px-8">
                    <div className="max-w-7xl mx-auto">
                        <MarketNewsCard />
                    </div>
                </section>
            )}

            {/* Features Section */}
            <section className="py-16 px-4 sm:px-6 lg:px-8">
                <div className="max-w-7xl mx-auto">
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {features.map((feature) => {
                            const Icon = feature.icon;
                            return (
                                <Link key={feature.name} href={feature.href}>
                                    <div className="group h-full bg-card border rounded-lg p-6 hover:shadow-lg transition-all duration-200 hover:border-primary/50 cursor-pointer">
                                        <div className="flex items-start gap-4">
                                            <div className={`flex-shrink-0 ${feature.color}`}>
                                                <Icon className="h-8 w-8" />
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <h3 className="text-xl font-semibold mb-2 group-hover:text-primary transition-colors">
                                                    {feature.name}
                                                </h3>
                                                <p className="text-muted-foreground text-sm leading-relaxed">
                                                    {feature.description}
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                </Link>
                            );
                        })}
                    </div>
                </div>
            </section>

            {/* Call to Action for Market News */}
            {!showMarketNews && (
                <section className="py-8 px-4 sm:px-6 lg:px-8">
                    <div className="max-w-7xl mx-auto">
                        <div className="bg-gradient-to-r from-teal-50 to-cyan-50 border border-teal-200 rounded-lg p-6 text-center">
                            <h3 className="text-lg font-semibold text-gray-900 mb-2">
                                Want to see market news on your home page?
                            </h3>
                            <p className="text-gray-600 mb-4">
                                Enable Market News in your notification settings to stay updated with the latest financial updates.
                            </p>
                            <Link href="/settings">
                                <Button className="bg-teal-600 hover:bg-teal-700">
                                    Go to Settings
                                </Button>
                            </Link>
                        </div>
                    </div>
                </section>
            )}
        </div>
    );
}