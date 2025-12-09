'use client';

import { useState } from 'react';
import { ChevronUp, ChevronDown, Info } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';
import DataService from '../../lib/DataService'; // Correct path to DataService
import { useRouter } from 'next/navigation'; // For Next.js routing - adjust if using React Router

export default function ReportTable({ stocks, userPreferences }) {
    // Component States
    const [currentPage, setCurrentPage] = useState(1);
    const [itemsPerPage, setItemsPerPage] = useState(10);
    const [sortConfig, setSortConfig] = useState({ key: 'ai_score', direction: 'desc' }); // Sort by ai_score by default
    const [loadingDetails, setLoadingDetails] = useState(null); // Track which stock is loading
    
    const router = useRouter(); // For Next.js - use useNavigate() for React Router

    // Sorting logic
    const sortedStocks = [...stocks].sort((a, b) => {
        if (!sortConfig.key) return 0;

        const aValue = a[sortConfig.key];
        const bValue = b[sortConfig.key];

        if (aValue < bValue) {
            return sortConfig.direction === 'asc' ? -1 : 1;
        }
        if (aValue > bValue) {
            return sortConfig.direction === 'asc' ? 1 : -1;
        }
        return 0;
    });

    // Pagination logic
    const totalPages = Math.ceil(sortedStocks.length / itemsPerPage);
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    const currentStocks = sortedStocks.slice(startIndex, endIndex);

    // Handlers
    const handleSort = (key) => {
        setSortConfig((prev) => ({
            key,
            direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc',
        }));
    };

    const handleItemsPerPageChange = (value) => {
        setItemsPerPage(Number(value));
        setCurrentPage(1);
    };

    const handleMoreDetails = async (stock) => {
        try {
            setLoadingDetails(stock.symbol);
            
            // Build query parameters
            const params = new URLSearchParams({
                symbol: stock.symbol
            });
            
            // Add user preferences if available
            if (userPreferences) {
                if (userPreferences.short_term) params.append('short_term', 'true');
                if (userPreferences.long_term) params.append('long_term', 'true');
            }
            
            // Navigate to the stock details page with preferences
            router.push(`/stock-detail?${params.toString()}`);
            
        } catch (error) {
            console.error('Error navigating to stock details:', error);
            alert(`Failed to navigate to details for ${stock.symbol}. Please try again.`);
        } finally {
            setLoadingDetails(null);
        }
    };

    const getSortIcon = (key) => {
        if (sortConfig.key !== key) return null;
        return sortConfig.direction === 'asc' ? (
            <ChevronUp className="w-4 h-4" />
        ) : (
            <ChevronDown className="w-4 h-4" />
        );
    };

    const getSignalColor = (signal) => {
        const signalLower = signal?.toLowerCase() || '';
        if (signalLower.includes('buy') || signalLower.includes('strong buy')) {
            return 'text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-950';
        }
        if (signalLower.includes('sell') || signalLower.includes('strong sell')) {
            return 'text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950';
        }
        return 'text-yellow-600 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-950';
    };

    return (
        <div className="flex flex-col h-full">
            {/* Table */}
            <ScrollArea className="flex-1">
                <div className="p-6">
                    <div className="border border-border rounded-lg overflow-hidden bg-card">
                        <table className="w-full">
                            <thead className="bg-muted">
                                <tr>
                                    <th
                                        className="px-6 py-4 text-left text-sm font-semibold text-foreground cursor-pointer hover:bg-muted/80"
                                        onClick={() => handleSort('symbol')}
                                    >
                                        <div className="flex items-center gap-2">
                                            Symbol
                                            {getSortIcon('symbol')}
                                        </div>
                                    </th>
                                    <th
                                        className="px-6 py-4 text-left text-sm font-semibold text-foreground cursor-pointer hover:bg-muted/80"
                                        onClick={() => handleSort('sector')}
                                    >
                                        <div className="flex items-center gap-2">
                                            Sector
                                            {getSortIcon('sector')}
                                        </div>
                                    </th>
                                    <th
                                        className="px-6 py-4 text-left text-sm font-semibold text-foreground cursor-pointer hover:bg-muted/80"
                                        onClick={() => handleSort('signal')}
                                    >
                                        <div className="flex items-center gap-2">
                                            Signal
                                            {getSortIcon('signal')}
                                        </div>
                                    </th>
                                    <th
                                        className="px-6 py-4 text-left text-sm font-semibold text-foreground cursor-pointer hover:bg-muted/80"
                                        onClick={() => handleSort('ai_score')}
                                    >
                                        <div className="flex items-center gap-2">
                                            AI Score
                                            {getSortIcon('ai_score')}
                                        </div>
                                    </th>
                                    <th
                                        className="px-6 py-4 text-left text-sm font-semibold text-foreground cursor-pointer hover:bg-muted/80"
                                        onClick={() => handleSort('sharpe')}
                                    >
                                        <div className="flex items-center gap-2">
                                            Sharpe
                                            {getSortIcon('sharpe')}
                                        </div>
                                    </th>
                                    <th
                                        className="px-6 py-4 text-left text-sm font-semibold text-foreground cursor-pointer hover:bg-muted/80"
                                        onClick={() => handleSort('cagr')}
                                    >
                                        <div className="flex items-center gap-2">
                                            CAGR
                                            {getSortIcon('cagr')}
                                        </div>
                                    </th>
                                    <th
                                        className="px-6 py-4 text-left text-sm font-semibold text-foreground cursor-pointer hover:bg-muted/80"
                                        onClick={() => handleSort('max_drawdown')}
                                    >
                                        <div className="flex items-center gap-2">
                                            Max Drawdown
                                            {getSortIcon('max_drawdown')}
                                        </div>
                                    </th>
                                    <th className="px-6 py-4 text-left text-sm font-semibold text-foreground">
                                        Action
                                    </th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-border">
                                {currentStocks.map((stock, index) => (
                                    <tr
                                        key={index}
                                        className="hover:bg-muted/50 transition-colors"
                                    >
                                        <td className="px-6 py-4 text-sm font-medium text-foreground">
                                            {stock.symbol}
                                        </td>
                                        <td className="px-6 py-4 text-sm text-muted-foreground">
                                            {stock.sector}
                                        </td>
                                        <td className="px-6 py-4 text-sm">
                                            <span
                                                className={`px-3 py-1 rounded-full font-medium ${getSignalColor(
                                                    stock.signal
                                                )}`}
                                            >
                                                {stock.signal}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 text-sm text-foreground">
                                            {stock.ai_score?.toFixed(2)}
                                        </td>
                                        <td className="px-6 py-4 text-sm text-foreground">
                                            {stock.sharpe?.toFixed(2)}
                                        </td>
                                        <td className="px-6 py-4 text-sm text-foreground">
                                            {stock.cagr?.toFixed(2)}%
                                        </td>
                                        <td className="px-6 py-4 text-sm text-foreground">
                                            {stock.max_drawdown?.toFixed(2)}%
                                        </td>
                                        <td className="px-6 py-4 text-sm">
                                            <button
                                                onClick={() => handleMoreDetails(stock)}
                                                disabled={loadingDetails === stock.symbol}
                                                className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                            >
                                                {loadingDetails === stock.symbol ? (
                                                    <>
                                                        <div className="w-4 h-4 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin" />
                                                        Loading...
                                                    </>
                                                ) : (
                                                    <>
                                                        <Info className="w-4 h-4" />
                                                        More Details
                                                    </>
                                                )}
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </ScrollArea>

            {/* Pagination Controls */}
            <div className="flex-shrink-0 border-t border-border bg-card p-4">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <span className="text-sm text-muted-foreground">
                            Show rows per page:
                        </span>
                        <select
                            value={itemsPerPage}
                            onChange={(e) => handleItemsPerPageChange(e.target.value)}
                            className="px-3 py-2 bg-background border border-border rounded-lg text-sm text-foreground focus:ring-2 focus:ring-ring focus:border-transparent"
                        >
                            <option value="5">5</option>
                            <option value="10">10</option>
                            <option value="25">25</option>
                            <option value="50">50</option>
                            <option value="100">100</option>
                        </select>
                    </div>

                    <div className="flex items-center gap-4">
                        <span className="text-sm text-muted-foreground">
                            Page {currentPage} of {totalPages} ({sortedStocks.length} total)
                        </span>
                        <div className="flex gap-2">
                            <button
                                onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
                                disabled={currentPage === 1}
                                className="px-4 py-2 bg-background border border-border rounded-lg text-sm text-foreground hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                            >
                                Previous
                            </button>
                            <button
                                onClick={() =>
                                    setCurrentPage((prev) => Math.min(totalPages, prev + 1))
                                }
                                disabled={currentPage === totalPages}
                                className="px-4 py-2 bg-background border border-border rounded-lg text-sm text-foreground hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                            >
                                Next
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}