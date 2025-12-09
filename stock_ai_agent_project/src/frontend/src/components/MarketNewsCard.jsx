'use client';

import { useState, useEffect } from 'react';
import { Newspaper, ExternalLink, TrendingUp, Clock, Loader2, RefreshCw } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

export default function MarketNewsCard() {
  const [news, setNews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [apiUsed, setApiUsed] = useState('');

  const fetchNews = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Try API 1: Financial Modeling Prep (No API key needed)
      try {
        console.log('Trying Financial Modeling Prep API...');
        const response1 = await fetch(
          'https://financialmodelingprep.com/api/v3/stock_news?limit=6'
        );
        
        if (response1.ok) {
          const data = await response1.json();
          console.log('FMP Response:', data);
          
          if (Array.isArray(data) && data.length > 0) {
            setNews(data.slice(0, 6));
            setApiUsed('Financial Modeling Prep');
            setLoading(false);
            return;
          }
        }
      } catch (err) {
        console.error('FMP API failed:', err);
      }
      
      // Try API 2: Finnhub Public News (No key needed for general market)
      try {
        console.log('Trying Finnhub API...');
        const response2 = await fetch(
          'https://finnhub.io/api/v1/news?category=general&token=demo'
        );
        
        if (response2.ok) {
          const data = await response2.json();
          console.log('Finnhub Response:', data);
          
          if (Array.isArray(data) && data.length > 0) {
            // Transform to match our format
            const transformedNews = data.slice(0, 6).map(item => ({
              title: item.headline,
              text: item.summary,
              url: item.url,
              image: item.image,
              publishedDate: new Date(item.datetime * 1000).toISOString(),
              site: item.source,
              symbol: item.related || ''
            }));
            setNews(transformedNews);
            setApiUsed('Finnhub');
            setLoading(false);
            return;
          }
        }
      } catch (err) {
        console.error('Finnhub API failed:', err);
      }
      
      // Try API 3: Benzinga (Via FMP endpoint)
      try {
        console.log('Trying Benzinga via FMP...');
        const response3 = await fetch(
          'https://financialmodelingprep.com/api/v4/general_news?page=0'
        );
        
        if (response3.ok) {
          const data = await response3.json();
          console.log('Benzinga Response:', data);
          
          if (Array.isArray(data) && data.length > 0) {
            setNews(data.slice(0, 6));
            setApiUsed('Benzinga');
            setLoading(false);
            return;
          }
        }
      } catch (err) {
        console.error('Benzinga API failed:', err);
      }
      
      // If all APIs fail
      throw new Error('All news APIs are currently unavailable. Please try again later.');
      
    } catch (err) {
      console.error('Error fetching news:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNews();
    
    // Refresh news every 30 minutes
    const interval = setInterval(fetchNews, 30 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const formatTimeAgo = (dateString) => {
    try {
      const now = new Date();
      const publishDate = new Date(dateString);
      const diffMs = now - publishDate;
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMins / 60);
      const diffDays = Math.floor(diffHours / 24);

      if (diffMins < 1) return 'Just now';
      if (diffMins < 60) return `${diffMins}m ago`;
      if (diffHours < 24) return `${diffHours}h ago`;
      return `${diffDays}d ago`;
    } catch {
      return 'Recently';
    }
  };

  if (loading) {
    return (
      <Card className="p-6 bg-gradient-to-br from-teal-50 to-cyan-50 border-teal-200">
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-8 h-8 animate-spin text-teal-600" />
          <span className="ml-3 text-gray-600">Loading market news...</span>
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="p-6 bg-gradient-to-br from-teal-50 to-cyan-50 border-teal-200">
        <div className="text-center py-8">
          <Newspaper className="w-12 h-12 text-gray-400 mx-auto mb-3" />
          <p className="text-gray-600 mb-2">Unable to load news at this time</p>
          <p className="text-sm text-gray-500 mb-4">{error}</p>
          <Button
            onClick={fetchNews}
            variant="outline"
            className="border-teal-400 text-teal-600 hover:bg-teal-50"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Try Again
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-6 bg-gradient-to-br from-teal-50 to-cyan-50 border-teal-200">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-teal-600 rounded-lg">
            <TrendingUp className="w-6 h-6 text-white" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Market News</h2>
            <p className="text-sm text-gray-600">
              {apiUsed ? `Latest from ${apiUsed}` : 'Latest financial updates'}
            </p>
          </div>
        </div>
        <button
          onClick={fetchNews}
          className="p-2 hover:bg-white/50 rounded-lg transition-colors"
          title="Refresh news"
        >
          <RefreshCw className="w-4 h-4 text-gray-600" />
        </button>
      </div>

      <div className="space-y-4">
        {news.map((item, index) => (
          <a
            key={index}
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="block group"
          >
            <div className="p-4 bg-white rounded-lg border border-gray-200 hover:border-teal-400 hover:shadow-md transition-all duration-200">
              <div className="flex gap-4">
                {/* Thumbnail if available */}
                {item.image && (
                  <div className="flex-shrink-0 w-24 h-24 rounded-lg overflow-hidden bg-gray-100">
                    <img 
                      src={item.image} 
                      alt={item.title || 'News image'}
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        e.target.style.display = 'none';
                      }}
                    />
                  </div>
                )}
                
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-gray-900 group-hover:text-teal-600 transition-colors line-clamp-2 mb-2">
                    {item.title || item.headline || 'Untitled'}
                  </h3>
                  <p className="text-sm text-gray-600 line-clamp-2 mb-3">
                    {item.text || item.summary || ''}
                  </p>
                  <div className="flex items-center gap-4 text-xs text-gray-500">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatTimeAgo(item.publishedDate || item.datetime)}
                    </span>
                    {item.site && (
                      <span className="font-medium">{item.site}</span>
                    )}
                  </div>
                  
                  {/* Show stock symbol if available */}
                  {item.symbol && (
                    <div className="flex gap-2 mt-2">
                      <span className="px-2 py-1 bg-teal-100 text-teal-700 text-xs rounded-full font-medium">
                        ${item.symbol}
                      </span>
                    </div>
                  )}
                </div>
                
                <ExternalLink className="w-4 h-4 text-gray-400 group-hover:text-teal-600 transition-colors flex-shrink-0" />
              </div>
            </div>
          </a>
        ))}
      </div>

      {news.length === 0 && (
        <div className="text-center py-8">
          <Newspaper className="w-12 h-12 text-gray-400 mx-auto mb-3" />
          <p className="text-gray-600">No news available at the moment</p>
          <p className="text-sm text-gray-500 mt-2">
            Open browser console (F12) to see debug logs
          </p>
        </div>
      )}
    </Card>
  );
}