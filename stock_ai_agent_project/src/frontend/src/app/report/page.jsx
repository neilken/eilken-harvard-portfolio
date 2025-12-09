'use client';

import { useState, use, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import ReportTable from '@/components/report/ReportTable';
import ReportSidebar from '@/components/report/ReportSidebar';
import DataService from "../../lib/DataService";

const MODEL = 'chatbot_final';

export default function ReportPage({ searchParams }) {
    const params = use(searchParams);
    const report_id = params.report_id;
    const chat_id = params.chat_id;
    const user_pref = params.user_pref ? JSON.parse(params.user_pref) : null;
    const router = useRouter();

    // Component States
    const [report, setReport] = useState(null);
    const [loading, setLoading] = useState(false);

    const fetchReport = async () => {
        try {
            setLoading(true);
            
            // If we have user_pref from URL, generate report
            if (chat_id && user_pref) {
                const response = await DataService.GenerateReport(MODEL, chat_id, user_pref);
                
                // Transform the response to match your ReportTable format
                const reportData = {
                    report_id: response.data.report?.report_id,
                    generated_date: response.data.report?.generated_at,
                    user_preferences: response.data.report?.user_preferences,
                    stocks: response.data.report?.recommendations || []
                };
                
                setReport(reportData);
            }
        } catch (error) {
            console.error('Error fetching report:', error);
            setReport(null);
        } finally {
            setLoading(false);
        }
    };

    // Setup Component
    useEffect(() => {
        if (chat_id && user_pref) {
            fetchReport();
        }
    }, [chat_id]);

    return (
        <div className="h-screen flex flex-col">
            <div className="flex h-[calc(100vh-64px)]">
                {/* Sidebar */}
                <div className="w-80 flex-shrink-0 bg-card border-r border-border">
                    <ReportSidebar report_id={report_id} />
                </div>

                {/* Main Report Area */}
                <div className="flex-1 flex flex-col h-full overflow-hidden">
                    {/* Header */}
                    <div className="flex-shrink-0 bg-gradient-to-r from-primary/10 via-primary/5 to-transparent border-b border-border">
                        <div className="p-8">
                            <h1 className="text-4xl font-bold gradient-text mb-2">
                                Stock Recommendations 📈
                            </h1>
                            <p className="text-muted-foreground text-lg">
                                Powered by AI-driven analysis • Maximize your portfolio potential
                            </p>
                            {report && (
                                <div className="mt-4 flex items-center gap-4 text-sm">
                                    <span className="text-foreground">
                                        Report Date: {new Date(report.generated_date).toLocaleDateString()}
                                    </span>
                                    <span className="text-muted-foreground">•</span>
                                    <span className="text-foreground">
                                        Total Recommendations: {report.stocks?.length || 0}
                                    </span>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Report Content */}
                    <div className="flex-1 overflow-hidden">
                        {loading ? (
                            <div className="flex items-center justify-center h-full">
                                <div className="text-center">
                                    <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
                                    <p className="mt-4 text-muted-foreground">Generating your personalized report...</p>
                                </div>
                            </div>
                        ) : report ? (
                            <ReportTable 
                                stocks={report.stocks || []} 
                                userPreferences={report.user_preferences}
                            />
                        ) : (
                            <div className="flex items-center justify-center h-full">
                                <div className="text-center">
                                    <p className="text-muted-foreground text-lg">No report data available</p>
                                    <p className="text-sm text-muted-foreground mt-2">
                                        Please generate a report from the chat first
                                    </p>
                                    <button
                                        onClick={() => router.push('/chat')}
                                        className="mt-4 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90"
                                    >
                                        Go to Chat
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}