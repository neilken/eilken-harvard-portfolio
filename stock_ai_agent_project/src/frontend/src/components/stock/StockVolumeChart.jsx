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

export default function StockVolumeChart({ volumeData, symbol, timeRange }) {
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
        if (!volumeData || volumeData.length === 0) return false;
        
        const oldestDate = new Date(volumeData[0].date);
        const newestDate = new Date(volumeData[volumeData.length - 1].date);
        const daysDiff = (newestDate - oldestDate) / (1000 * 60 * 60 * 24);
        
        return daysDiff >= 1825; // 5 years = 1825 days
    }, [volumeData]);

    // Filter data based on time range
    const filteredData = useMemo(() => {
        if (!volumeData || volumeData.length === 0) return [];
        
        // First, sort data by date in ascending order (oldest to newest)
        const sortedData = [...volumeData].sort((a, b) => 
            new Date(a.date) - new Date(b.date)
        );

        // Filter out days with no trading (zero or null volume)
        const tradingDaysOnly = sortedData.filter(item => {
            return item.volume > 0;
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
    }, [volumeData, timeRange]);

    // Prepare bar trace
    const trace = useMemo(() => ({
        x: filteredData.map(d => d.date),
        y: filteredData.map(d => d.volume),
        type: 'bar',
        name: 'Volume',
        marker: {
            color: '#8b5cf6',
            line: {
                color: '#7c3aed',
                width: 0.5
            }
        },
        hovertemplate: '<b>Date:</b> %{x}<br><b>Volume:</b> %{y:,.0f}<extra></extra>'
    }), [filteredData]);

    // Layout configuration
    const layout = {
        dragmode: 'zoom',
        margin: {
            r: 10,
            t: 10,
            b: 80, // Increased from 40 to 80 for angled labels
            l: 80
        },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        showlegend: false,
        xaxis: {
            gridcolor: '#e5e7eb',
            linecolor: '#e5e7eb',
            zerolinecolor: '#e5e7eb',
            autorange: true,
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
                text: 'Volume',
                font: { size: 12 }
            },
            type: 'linear',
            tickfont: { size: 10 },
            tickformat: ',.0f'
        },
        hovermode: 'x unified',
        hoverlabel: {
            bgcolor: 'rgba(255, 255, 255, 0.95)',
            bordercolor: '#e5e7eb',
            font: { size: 12 }
        },
        height: 450, // Increased from 400 to accommodate angled labels
        bargap: 0.1
    };

    // Plotly config
    const config = {
        responsive: true,
        displayModeBar: true,
        displaylogo: false,
        modeBarButtonsToRemove: ['select2d', 'lasso2d'],
        toImageButtonOptions: {
            format: 'png',
            filename: `${symbol}_volume_chart`,
            height: 800,
            width: 1200,
            scale: 2
        }
    };

    if (!filteredData || filteredData.length === 0) {
        return (
            <div className="text-center text-muted-foreground py-8">
                No volume data available
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
        </div>
    );
}