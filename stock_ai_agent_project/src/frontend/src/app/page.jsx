'use client';

import Link from 'next/link';
import { List, BarChart, Grid3x3, Bot, Image, Mic, Mic2, MapPin, SettingsIcon, ViewIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function Home() {
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
            href: '/Settings',
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
                        Break through market complexity with AI-powered insights.Stock Busters helps you identify winning opportunities, bust through investment barriers, and take control of your portfolio with confidence.

                    </p>
                          
                </div>
            </section>

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
        </div>
    );
}