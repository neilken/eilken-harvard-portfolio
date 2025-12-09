'use client';

import { useState, useEffect, useMemo } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { ArrowLeft, TrendingUp, Building2, Sparkles, AlertCircle } from 'lucide-react';

// Import your uploaded components  
import StockPriceChart from '@/components/stock/StockPriceChart';
import StockVolumeChart from '@/components/stock/StockVolumeChart';

import DataService from "../../lib/DataService";

export default function StockDetailPage() {
    const router = useRouter();
    const searchParams = useSearchParams();

    const symbol = searchParams.get("symbol");
    const shortTerm = searchParams.get("short_term") === "true";
    const longTerm = searchParams.get("long_term") === "true";

    const [stockData, setStockData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [timeRange, setTimeRange] = useState("1M");
    const [showMore, setShowMore] = useState(false);
    const [imageError, setImageError] = useState(false);

    /* ---------------- FETCH DATA ---------------- */
    const fetchStockDetail = async () => {
        try {
            setLoading(true);
            setError(null);

            const res = await DataService.GetStockDetails(symbol);
            setStockData(res.data);

        } catch (err) {
            const message = err.response?.data?.message || "Failed to load details";
            setError(message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (!symbol) return setError("No stock symbol provided.");
        fetchStockDetail();
    }, [symbol]);

    /* ---------------- LOADING ---------------- */
    if (loading) {
        return (
            <div className="flex items-center justify-center h-screen">
                <div className="text-center">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
                    <p className="mt-4 text-muted-foreground">Loading data...</p>
                </div>
            </div>
        );
    }

    /* ---------------- ERROR ---------------- */
    if (error) {
        return (
            <div className="flex items-center justify-center h-screen p-6">
                <div className="bg-card border border-destructive rounded-lg p-8 max-w-md w-full">
                    <AlertCircle className="w-16 h-16 text-destructive mx-auto mb-4" />
                    <h2 className="text-2xl font-bold text-center mb-2">Error</h2>
                    <p className="text-muted-foreground text-center mb-6">{error}</p>

                    <button
                        onClick={() => router.back()}
                        className="w-full px-6 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90"
                    >
                        Go Back
                    </button>
                </div>
            </div>
        );
    }

    if (!stockData) return null;

    /* ---------------- EXTRACT DATA ---------------- */
    const company = stockData.company_profile || {};
    const quant = stockData.quant_model || {};
    const raw = stockData.stocks_data || {};

    /* ---------------- PRICE/VOLUME TRANSFORM ---------------- */
    const transformData = () => {
        if (!raw?.date?.length) return { priceData: [], volumeData: [] };

        const priceData = raw.date.map((d, i) => ({
            date: new Date(d).toISOString().split("T")[0],
            open: raw.open?.[i] ?? 0,
            high: raw.high?.[i] ?? 0,
            low: raw.low?.[i] ?? 0,
            close: raw.close?.[i] ?? 0,
        }));

        const volumeData = raw.date.map((d, i) => ({
            date: new Date(d).toISOString().split("T")[0],
            volume: raw.volume?.[i] ?? 0,
        }));

        return { priceData, volumeData };
    };

    const { priceData, volumeData } = transformData();

    /* ---------------- AI SCORE ---------------- */
    const aiScore = shortTerm
        ? quant.Technical_Score
        : longTerm
            ? quant.Fundamental_Score
            : quant.Hybrid_Score;

    const aiScoreLabel = shortTerm
        ? "AI Score (Technical)"
        : longTerm
            ? "AI Score (Fundamental)"
            : "AI Score (Hybrid)";

    /* ---------------- AI REASONING (with fallbacks) ---------------- */
    const aiReasoning =
        quant.rag_reasoning ||
        quant.reasoning ||
        quant.regression_reasoning ||
        quant.llm_reasoning ||
        quant.analysis ||
        "";

    /* ---------------- COMPANY DESCRIPTION (SHOW MORE/LESS) ---------------- */
    const shortDescription = company.description
        ? company.description.slice(0, 300) + "..."
        : "";

    /* ---------------- MAIN RETURN ---------------- */
    return (
        <div className="min-h-screen bg-background">

            {/* HEADER */}
            <div className="bg-gradient-to-r from-primary/10 via-primary/5 to-transparent border-b">
                <div className="container mx-auto px-6 py-8">
                    <button
                        onClick={() => router.back()}
                        className="flex items-center gap-2 text-muted-foreground hover:text-foreground mb-4"
                    >
                        <ArrowLeft className="w-4 h-4" />
                        Back to Report
                    </button>

                    <div className="flex items-center gap-4 mb-4">
                        <h1 className="text-4xl font-bold gradient-text">
                            {company.name || symbol} - {company.companyName} 
                        </h1>
                        
                        {/* Company Logo */}
                        {company.image && !imageError ? (
                            <div className="flex-shrink-0 w-16 h-16 bg-white rounded-lg border-2 border-primary/20 p-2 flex items-center justify-center">
                                <img 
                                    src={company.image} 
                                    alt={`${symbol} logo`}
                                    className="w-full h-full object-contain"
                                    onError={() => setImageError(true)}
                                />
                            </div>
                        ) : (
                            <div className="flex-shrink-0 w-16 h-16 bg-primary rounded-lg flex items-center justify-center text-primary-foreground font-bold text-xl">
                                {symbol?.substring(0, 2)}
                            </div>
                        )}
                    </div>

                    <div className="flex items-center gap-3">
                        <span className="text-2xl font-bold">{symbol}</span>
                        {quant.signal && (
                            <span className="px-3 py-1 rounded-full bg-primary/10 text-primary text-sm">
                                {quant.signal}
                            </span>
                        )}
                        {company.name && (
                            <span className="text-muted-foreground">• {company.name}</span>
                        )}
                    </div>
                </div>
            </div>

            {/* MAIN LAYOUT */}
            <div className="container mx-auto px-6 py-8">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

                    {/* LEFT COLUMN */}
                    <div className="space-y-6">

                        {/* COMPANY INFORMATION */}
                        <div className="bg-card p-6 rounded-xl border shadow-sm">
                            <h2 className="flex items-center gap-2 text-xl font-semibold mb-4">
                                <Building2 className="w-5 h-5 text-primary" />
                                Company Information
                            </h2>

                            <div className="space-y-2 text-sm">
                                {company.sector && <p><b>Sector:</b> {company.sector}</p>}
                                {company.industry && <p><b>Industry:</b> {company.industry}</p>}
                                {company.exchange && <p><b>Exchange:</b> {company.exchange}</p>}
                            </div>

                            {company.description && (
                                <div className="mt-4 border-t pt-4">
                                    <p className="text-sm text-muted-foreground leading-relaxed">
                                        {showMore ? company.description : shortDescription}
                                    </p>

                                    <button
                                        onClick={() => setShowMore(!showMore)}
                                        className="text-primary text-sm font-medium mt-2 hover:underline"
                                    >
                                        {showMore ? "Show Less ▲" : "Show More ▼"}
                                    </button>
                                </div>
                            )}
                        </div>

                        {/* KEY METRICS */}
                        <div className="bg-card p-6 rounded-xl border shadow-sm">
                            <h2 className="flex items-center gap-2 text-xl font-semibold mb-4">
                                <TrendingUp className="w-5 h-5 text-primary" />
                                Key Metrics
                            </h2>

                            <div className="grid grid-cols-2 gap-4">
                                {aiScore !== undefined && (
                                    <Metric label={aiScoreLabel} value={aiScore} />
                                )}

                                {(quant.sharpe_1m_annual || quant.sharpe) && (
                                    <Metric
                                        label="Sharpe Ratio"
                                        value={quant.sharpe_1m_annual || quant.sharpe}
                                    />
                                )}

                                {quant.cagr !== undefined && (
                                    <Metric
                                        label="CAGR"
                                        value={`${quant.cagr.toFixed(2)}%`}
                                        positive
                                    />
                                )}

                                {quant.max_drawdown !== undefined && (
                                    <Metric
                                        label="Max Drawdown"
                                        value={`${quant.max_drawdown.toFixed(2)}%`}
                                        negative
                                    />
                                )}
                            </div>
                        </div>

                        {/* AI ANALYSIS */}
                        {aiReasoning && (
                            <div className="bg-card p-6 rounded-xl border shadow-sm">
                                <h2 className="flex items-center gap-2 text-xl font-semibold mb-4">
                                    <Sparkles className="w-5 h-5 text-primary" />
                                    AI-Generated Analysis
                                </h2>

                                <div className="space-y-3">
                                    {aiReasoning
                                        .split(/\n|\.(?=\s+[A-Z])/)
                                        .filter(line => line.trim())
                                        .map((sent, i) => (
                                            <div key={i} className="flex gap-3">
                                                <div className="w-2 h-2 bg-primary rounded-full mt-2 flex-shrink-0" />
                                                <p className="text-sm leading-relaxed">
                                                    {sent.trim().endsWith(".")
                                                        ? sent.trim()
                                                        : sent.trim() + "."}
                                                </p>
                                            </div>
                                        ))}
                                </div>
                            </div>
                        )}
                    </div>

                    {/* RIGHT COLUMN */}
                    <div className="lg:col-span-2 space-y-6">

                        {/* TIME RANGE SELECTOR */}
                        <TimeSelector timeRange={timeRange} setTimeRange={setTimeRange} priceData={priceData} />

                        {/* PRICE CHART */}
                        {priceData.length > 0 && (
                            <ChartCard title="Stock Price Trend">
                                <StockPriceChart
                                    priceData={priceData}
                                    symbol={symbol}
                                    timeRange={timeRange}
                                />
                            </ChartCard>
                        )}

                        {/* VOLUME CHART */}
                        {volumeData.length > 0 && (
                            <ChartCard title="Trading Volume Analysis">
                                <StockVolumeChart
                                    volumeData={volumeData}
                                    symbol={symbol}
                                    timeRange={timeRange}
                                />
                            </ChartCard>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}

/* ---------------- SMALL COMPONENTS ---------------- */

const Metric = ({ label, value, positive, negative }) => (
    <div className="bg-muted/50 rounded-lg p-3">
        <p className="text-xs text-muted-foreground mb-1">{label}</p>
        <p
            className={`text-lg font-bold ${
                positive ? "text-green-600" :
                negative ? "text-red-600" :
                "text-foreground"
            }`}
        >
            {typeof value === "number" ? value.toFixed(2) : value}
        </p>
    </div>
);

const TimeSelector = ({ timeRange, setTimeRange, priceData }) => {
    const ranges = ["1W", "1M", "3M", "6M", "1Y", "YTD", "3Y", "5Y", "MAX"];

    // Check if we have 5 years of data
    const has5YearsData = useMemo(() => {
        if (!priceData || priceData.length === 0) return false;
        
        const oldestDate = new Date(priceData[0].date);
        const newestDate = new Date(priceData[priceData.length - 1].date);
        const daysDiff = (newestDate - oldestDate) / (1000 * 60 * 60 * 24);
        
        return daysDiff >= 1825; // 5 years = 1825 days
    }, [priceData]);

    return (
        <div className="bg-card p-4 rounded-xl border shadow-sm">
            <div className="flex items-center justify-between flex-wrap gap-4">
                <div className="flex gap-2 flex-wrap">
                    {ranges.map((r) => {
                        const isDisabled = r === '5Y' && !has5YearsData;
                        
                        return (
                            <button
                                key={r}
                                onClick={() => !isDisabled && setTimeRange(r)}
                                disabled={isDisabled}
                                className={`px-4 py-2 rounded-lg text-sm transition-all ${
                                    timeRange === r
                                        ? "bg-primary text-primary-foreground shadow-sm"
                                        : isDisabled
                                        ? "bg-muted text-muted-foreground/40 cursor-not-allowed"
                                        : "bg-muted text-muted-foreground hover:bg-muted/80"
                                }`}
                                title={isDisabled ? "Insufficient data for 5Y view" : ""}
                            >
                                {r}
                            </button>
                        );
                    })}
                </div>

                <span className="text-sm text-muted-foreground">
                    Time Range: {timeRange}
                </span>
            </div>
        </div>
    );
};

const ChartCard = ({ title, children }) => (
    <div className="bg-card p-6 rounded-xl border shadow-sm">
        <h2 className="text-xl font-semibold mb-4">{title}</h2>
        {children}
    </div>
);


export const dynamic = 'force-dynamic';