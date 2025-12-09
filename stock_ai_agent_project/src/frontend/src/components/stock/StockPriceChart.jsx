'use client';

import { useState, useMemo } from 'react';
import dynamic from 'next/dynamic';
import { Loader2 } from 'lucide-react';

// Dynamically import Plot with no SSR
const Plot = dynamic(() => import('react-plotly.js'), {
    ssr: false,
    loading: () => (
        <div className="flex justify-center p-8">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
    )
});

export default function StockPriceChart({ priceData, symbol, timeRange }) {
    // Time range options
    const timeRanges = [
        { label: '1W', value: '1W', days: 7 },
        { label: '1M', value: '1M', days: 30 },
        { label: '3M', value: '3M', days: 90 },
        { label: '6M', value: '6M', days: 180 },
        { label: '1Y', value: '1Y', days: 365 },
        { label: 'YTD', value: 'YTD', days: null },
        { label: '3Y', value: '3Y', days: 1095 },
        { label: '5Y', value: '5Y', days: 1825 },
        { label: 'MAX', value: 'MAX', days: null }
    ];

    // Check if we have 5 years of data
    const has5YearsData = useMemo(() => {
        if (!priceData || priceData.length === 0) return false;
        
        const oldestDate = new Date(priceData[0].date);
        const newestDate = new Date(priceData[priceData.length - 1].date);
        const daysDiff = (newestDate - oldestDate) / (1000 * 60 * 60 * 24);
        
        return daysDiff >= 1825; // 5 years = 1825 days
    }, [priceData]);

    // Filter data based on time range
    const filteredData = useMemo(() => {
        if (!priceData || priceData.length === 0) return [];
        
        // First, sort data by date in ascending order (oldest to newest)
        const sortedData = [...priceData].sort((a, b) => 
            new Date(a.date) - new Date(b.date)
        );

        // Filter out days with no trading (zero values or null)
        const tradingDaysOnly = sortedData.filter(item => {
            return item.open > 0 && item.close > 0 && item.high > 0 && item.low > 0;
        });
        
        if (timeRange === 'MAX') {
            return tradingDaysOnly;
        }
        
        if (timeRange === 'YTD') {
            const currentYear = new Date().getFullYear();
            const startOfYear = new Date(currentYear, 0, 1);
            return tradingDaysOnly.filter(item => new Date(item.date) >= startOfYear);
        }
        
        const selectedRange = timeRanges.find(r => r.value === timeRange);
        if (!selectedRange || !selectedRange.days) {
            return tradingDaysOnly;
        }
        
        // Get the LAST N days (most recent data) - negative index gets from end
        return tradingDaysOnly.slice(-selectedRange.days);
    }, [priceData, timeRange]);

    // Prepare candlestick trace
    const trace = useMemo(() => ({
        x: filteredData.map(d => d.date),
        open: filteredData.map(d => d.open),
        high: filteredData.map(d => d.high),
        low: filteredData.map(d => d.low),
        close: filteredData.map(d => d.close),
        type: 'candlestick',
        name: symbol,
        increasing: { 
            line: { color: '#10b981' },
            fillcolor: '#10b981'
        },
        decreasing: { 
            line: { color: '#ef4444' },
            fillcolor: '#ef4444'
        },
        xaxis: 'x',
        yaxis: 'y',
    }), [filteredData, symbol]);

    // Layout configuration
    const layout = {
        dragmode: 'zoom',
        margin: {
            r: 10,
            t: 10,
            b: 80, // Increased from 40 to 80 for angled labels
            l: 60
        },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        showlegend: false,
        xaxis: {
            gridcolor: '#e5e7eb',
            linecolor: '#e5e7eb',
            zerolinecolor: '#e5e7eb',
            autorange: true,
            rangeslider: { visible: false },
            title: {
                text: 'Date',
                font: { size: 12 }
            },
            type: 'category', // Changed from 'date' to 'category' to remove gaps
            tickfont: { size: 9 },
            tickangle: -45,
            tickmode: 'auto',
            nticks: 15 // Limit number of ticks to prevent overcrowding
        },
        yaxis: {
            gridcolor: '#e5e7eb',
            linecolor: '#e5e7eb',
            zerolinecolor: '#e5e7eb',
            autorange: true,
            title: {
                text: 'Price ($)',
                font: { size: 12 }
            },
            type: 'linear',
            tickfont: { size: 10 }
        },
        hovermode: 'x unified',
        hoverlabel: {
            bgcolor: 'rgba(255, 255, 255, 0.95)',
            bordercolor: '#e5e7eb',
            font: { size: 12 }
        },
        height: 450 // Increased from 400 to accommodate angled labels
    };

    // Plotly config
    const config = {
        responsive: true,
        displayModeBar: true,
        displaylogo: false,
        modeBarButtonsToRemove: ['select2d', 'lasso2d'],
        toImageButtonOptions: {
            format: 'png',
            filename: `${symbol}_price_chart`,
            height: 800,
            width: 1200,
            scale: 2
        }
    };

    if (!filteredData || filteredData.length === 0) {
        return (
            <div className="text-center text-muted-foreground py-8">
                No price data available
            </div>
        );
    }

    return (
        <div className="w-full">
            <Plot
                data={[trace]}
                layout={layout}
                config={config}
                className="w-full"
                useResizeHandler={true}
                style={{ width: '100%' }}
            />
            {/* Hidden div to expose has5YearsData to parent */}
            <div data-has-5y-data={has5YearsData} style={{ display: 'none' }} />
        </div>
    );
}