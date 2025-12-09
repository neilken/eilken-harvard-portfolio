import { BASE_API_URL, uuid } from "./Common";
import axios from 'axios';

console.log("BASE_API_URL:", BASE_API_URL);

// Create an axios instance with base configuration
const api = axios.create({
    baseURL: BASE_API_URL
});

// Add request interceptor to include session ID in headers
api.interceptors.request.use((config) => {
    // Check if we're in a browser environment (has localStorage)
    if (typeof window !== 'undefined' && window.localStorage) {
        var sessionId = localStorage.getItem('userSessionId');
        if (sessionId) {
            config.headers['X-Session-ID'] = sessionId;
        } else {
            sessionId = uuid(); // Use custom uuid from Common.js
            localStorage.setItem('userSessionId', sessionId);
            config.headers['X-Session-ID'] = sessionId;
        }
    }
    return config;
}, (error) => {
    return Promise.reject(error);
});

const DataService = {
    Init: function () {
        // Any application initialization logic comes here
    },
    
    // Chat-related methods
    GetChats: async function (model, limit) {
        return await api.get("/" + model + "/chats?limit=" + limit);
    },
    
    GetChat: async function (model, chat_id) {
        return await api.get("/" + model + "/chats/" + chat_id);
    },
    
    StartChatWithLLM: async function (model, message) {
        // Wrap the message in an object if it's a string
        const payload = typeof message === 'string' ? { message: message } : message;
        return await api.post("/" + model + "/chats", payload);
    },
    
    ContinueChatWithLLM: async function (model, chat_id, message) {
        // Wrap the message in an object if it's a string
        const payload = typeof message === 'string' ? { message: message } : message;
        return await api.post("/" + model + "/chats/" + chat_id, payload);
    },
    
    GetChatMessageImage: function (model, image_path) {
        if (!image_path) return '';
        if (image_path.startsWith('http')) return image_path;
        return BASE_API_URL + "/" + model + "/images/" + image_path;
    },

    // Stock-related methods (added for deployment compatibility)
    GetStockDetails: async function (ticker) {
        try {
            const response = await api.get("/details/" + ticker);
            return response;
        } catch (error) {
            console.error('Error fetching stock details:', error);
            throw error;
        }
    },

    GetStockData: async function (symbol, days = 90) {
        try {
            const response = await api.get("/details/" + symbol);
            // Transform the response to match expected format
            return {
                data: response.data?.stocks_data || [],
            };
        } catch (error) {
            console.error('Error fetching stock data:', error);
            throw error;
        }
    },

    GetStockMetrics: async function (symbol) {
        try {
            const response = await api.get("/details/" + symbol);
            // Extract metrics from the response
            const stocksData = response.data?.stocks_data || {};
            return {
                data: {
                    price: stocksData.current_price || 0,
                    change: stocksData.change || 0,
                    changePercent: stocksData.change_percent || 0,
                    marketCap: stocksData.market_cap || 0,
                    volume: stocksData.volume || 0,
                    pe: stocksData.pe_ratio || 0,
                    beta: stocksData.beta || 0,
                    low52Week: stocksData.low_52_week || 0,
                    high52Week: stocksData.high_52_week || 0,
                    dividend: stocksData.dividend_yield || 0,
                },
            };
        } catch (error) {
            console.error('Error fetching stock metrics:', error);
            throw error;
        }
    },

    GetMovingAverages: async function (symbol) {
        try {
            const response = await api.get("/details/" + symbol);
            // Extract moving averages from quant_model or calculate them
            const quantData = response.data?.quant_model || {};
            return {
                data: {
                    sma20: quantData.sma20 || 0,
                    sma50: quantData.sma50 || 0,
                    ema12: quantData.ema12 || 0,
                    ema26: quantData.ema26 || 0,
                },
            };
        } catch (error) {
            console.error('Error fetching moving averages:', error);
            throw error;
        }
    },

    GetTechnicalIndicators: async function (symbol) {
        try {
            const response = await api.get("/details/" + symbol);
            // Extract technical indicators from quant_model
            const quantData = response.data?.quant_model || {};
            return {
                data: {
                    rsi: quantData.rsi || 50,
                    macd: quantData.macd || 0,
                    signal: quantData.macd_signal || 0,
                    bollingerUpper: quantData.bollinger_upper || 0,
                    bollingerMiddle: quantData.bollinger_middle || 0,
                    bollingerLower: quantData.bollinger_lower || 0,
                },
            };
        } catch (error) {
            console.error('Error fetching technical indicators:', error);
            throw error;
        }
    },

    GetStockList: function () {
        // Return a static list of stocks - you may want to fetch this from an API
        return [
            { symbol: 'AAPL', name: 'Apple Inc.', sector: 'Technology' },
            { symbol: 'GOOGL', name: 'Alphabet Inc.', sector: 'Technology' },
            { symbol: 'MSFT', name: 'Microsoft Corporation', sector: 'Technology' },
            { symbol: 'AMZN', name: 'Amazon.com Inc.', sector: 'Consumer Cyclical' },
            { symbol: 'TSLA', name: 'Tesla Inc.', sector: 'Consumer Cyclical' },
            { symbol: 'META', name: 'Meta Platforms Inc.', sector: 'Technology' },
            { symbol: 'NVDA', name: 'NVIDIA Corporation', sector: 'Technology' },
            { symbol: 'JPM', name: 'JPMorgan Chase & Co.', sector: 'Financial Services' },
            { symbol: 'V', name: 'Visa Inc.', sector: 'Financial Services' },
            { symbol: 'JNJ', name: 'Johnson & Johnson', sector: 'Healthcare' },
        ];
    },

    // Report-related methods (added for deployment compatibility)
    GetReports: async function (model, limit = 20) {
        try {
            const response = await api.get("/" + model + "/reports?limit=" + limit);
            return response;
        } catch (error) {
            console.error('Error fetching reports:', error);
            throw error;
        }
    },

    GenerateReport: async function (model, chat_id, user_preferences) {
        try {
            const response = await api.post("/" + model + "/chats/" + chat_id + "/report", {
                user_pref: user_preferences,
            });
            return response;
        } catch (error) {
            console.error('Error generating report:', error);
            throw error;
        }
    },
}

export default DataService;
