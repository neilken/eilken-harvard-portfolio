'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { FileText, Plus, Loader2 } from 'lucide-react';
import DataService from "../../lib/DataService";

const MODEL = 'chatbot_final';

export default function ReportSidebar({ report_id }) {
    // Component States
    const [reports, setReports] = useState([]);
    const [loading, setLoading] = useState(true);
    const [mounted, setMounted] = useState(false);
    const router = useRouter();

    // Ensure component is mounted before rendering dynamic content
    useEffect(() => {
        setMounted(true);
    }, []);

    // Setup Component
    useEffect(() => {
        if (!mounted) return;

        const fetchData = async () => {
            try {
                setLoading(true);
                const response = await DataService.GetReports(MODEL, 20);
                setReports(response.data || []);
            } catch (error) {
                console.error('Error fetching reports:', error);
                setReports([]);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [mounted]);

    const handleReportClick = (report) => {
        // Navigate to report page with necessary params
        const params = new URLSearchParams({
            report_id: report.report_id,
            chat_id: report.chat_id
        });
        
        // Add user preferences if available
        if (report.user_preferences) {
            params.append('user_pref', JSON.stringify(report.user_preferences));
        }
        
        router.push(`/report?${params.toString()}`);
    };

    const formatRelativeTime = (dateString) => {
        if (!dateString) return 'Unknown date';
        
        try {
            const date = new Date(dateString);
            const now = new Date();
            const diffMs = now - date;
            const diffMins = Math.floor(diffMs / 60000);
            const diffHours = Math.floor(diffMs / 3600000);
            const diffDays = Math.floor(diffMs / 86400000);

            if (diffMins < 1) return 'Just now';
            if (diffMins < 60) return `${diffMins} min${diffMins > 1 ? 's' : ''} ago`;
            if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
            if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
            
            return date.toLocaleDateString();
        } catch (error) {
            return 'Invalid date';
        }
    };

    // Show loading state initially to avoid hydration mismatch
    if (!mounted) {
        return (
            <div className="flex flex-col h-full bg-card border-r border-border">
                <div className="flex items-center justify-between p-4 bg-gradient-to-r from-primary/10 to-transparent border-b border-border">
                    <h2 className="text-foreground text-lg font-semibold flex items-center gap-2">
                        <FileText className="text-primary w-5 h-5" />
                        Reports History
                    </h2>
                </div>
                <div className="flex-1" />
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full bg-card border-r border-border">
            {/* Header */}
            <div className="flex items-center justify-between p-4 bg-gradient-to-r from-primary/10 to-transparent border-b border-border">
                <h2 className="text-foreground text-lg font-semibold flex items-center gap-2">
                    <FileText className="text-primary w-5 h-5" />
                    Reports History
                </h2>
                <button
                    onClick={() => router.push('/chat')}
                    className="flex items-center gap-1.5 px-3 py-2 bg-primary text-primary-foreground hover:bg-primary/90
                        rounded-lg transition-colors text-sm font-medium shadow-sm hover:shadow"
                    title="Generate new report"
                >
                    <Plus className="w-4 h-4" />
                    New
                </button>
            </div>

            {/* Reports List */}
            <div className="flex-1 overflow-y-auto p-3 space-y-2">
                {loading ? (
                    <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                        <Loader2 className="w-8 h-8 animate-spin mb-2" />
                        <p className="text-sm">Loading reports...</p>
                    </div>
                ) : reports.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-8 px-4 text-center">
                        <FileText className="w-12 h-12 text-muted-foreground/40 mb-3" />
                        <p className="text-muted-foreground text-sm mb-1">No reports yet</p>
                        <p className="text-muted-foreground text-xs">
                            Start a chat to generate your first report
                        </p>
                    </div>
                ) : (
                    reports.map((report) => (
                        <div
                            key={report.report_id}
                            onClick={() => handleReportClick(report)}
                            className={`group relative p-3 rounded-lg border cursor-pointer transition-all
                                hover:shadow-md hover:border-primary/50
                                ${report_id === report.report_id 
                                    ? 'bg-primary/5 border-primary shadow-sm' 
                                    : 'bg-card border-border hover:bg-accent/50'
                                }`}
                        >
                            <div className="flex flex-col gap-2">
                                {/* Title and Stock Count */}
                                <div className="flex items-start justify-between gap-2">
                                    <h3 className="text-foreground text-sm font-medium line-clamp-2 flex-1 leading-snug">
                                        {report.title || report.summary?.investment_horizon || 'Stock Recommendations'}
                                    </h3>
                                    {(report.stock_count || report.summary?.total_recommendations) && (
                                        <span className="flex-shrink-0 text-xs bg-primary/10 text-primary px-2 py-0.5 rounded-full font-medium">
                                            {report.stock_count || report.summary?.total_recommendations} stocks
                                        </span>
                                    )}
                                </div>

                                {/* Date */}
                                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                    <span className="font-medium">
                                        {formatRelativeTime(report.generated_date || report.generated_at)}
                                    </span>
                                    {report.summary?.investment_horizon && (
                                        <>
                                            <span>•</span>
                                            <span className="text-primary">
                                                {report.summary.investment_horizon}
                                            </span>
                                        </>
                                    )}
                                </div>

                                {/* View Chat Link */}
                                {report.chat_id && (
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            router.push(`/chat?id=${report.chat_id}`);
                                        }}
                                        className="text-xs text-primary hover:text-primary/80 hover:underline 
                                            text-left font-medium transition-colors"
                                    >
                                        View source chat →
                                    </button>
                                )}
                            </div>

                            {/* Active Indicator */}
                            {report_id === report.report_id && (
                                <div className="absolute left-0 top-0 bottom-0 w-1 bg-primary rounded-l-lg" />
                            )}
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}