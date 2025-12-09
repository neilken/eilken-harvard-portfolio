'use client';

import { useState, use, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import ChatInput from '@/components/chat/ChatInput';
import ChatHistory from '@/components/chat/ChatHistory';
import ChatHistorySidebar from '@/components/chat/ChatHistorySidebar';
import ChatMessage from '@/components/chat/ChatMessage';
import DataService from "../../lib/DataService";
import { uuid } from "../../lib/Common";

const MODEL = 'chatbot_final'; // Single model constant

export default function ChatPage({ searchParams }) {
    const params = use(searchParams);
    const chat_id = params.id;
    console.log(chat_id);

    // Component States
    const [chatId, setChatId] = useState(params.id);
    const [hasActiveChat, setHasActiveChat] = useState(false);
    const [chat, setChat] = useState(null);
    const [refreshKey, setRefreshKey] = useState(0);
    const [isTyping, setIsTyping] = useState(false);
    const [canGenerateReport, setCanGenerateReport] = useState(false);
    const router = useRouter();

    const fetchChat = async (id) => {
        try {
            setChat(null);
            const response = await DataService.GetChat(MODEL, id);
            setChat(response.data);
            console.log(chat);
        } catch (error) {
            console.error('Error fetching chat:', error);
            setChat(null);
        }
    };

    // Setup Component
    useEffect(() => {
        if (chat_id) {
            fetchChat(chat_id);
            setHasActiveChat(true);
        } else {
            setChat(null);
            setHasActiveChat(false);
        }
    }, [chat_id]);

    // Prevent body scroll when chat is active
    useEffect(() => {
        if (hasActiveChat) {
            // Prevent body scroll
            document.body.style.overflow = 'hidden';
            document.documentElement.style.overflow = 'hidden';
        } else {
            // Allow body scroll
            document.body.style.overflow = 'auto';
            document.documentElement.style.overflow = 'auto';
        }
        
        // Cleanup on unmount
        return () => {
            document.body.style.overflow = 'auto';
            document.documentElement.style.overflow = 'auto';
        };
    }, [hasActiveChat]);

    // Check if report can be generated based on completion status
    useEffect(() => {
        if (chat) {
            const hasConfirmed = chat.user_preferences?.confirmation === true;
            setCanGenerateReport(hasConfirmed);
        } else {
            setCanGenerateReport(false);
        }
    }, [chat]);

    // Scroll to top when navigating to/from chat
    useEffect(() => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }, [chat_id]);

    function tempChatMessage(message) {
        message["message_id"] = uuid();
        message["role"] = 'user';
        if (chat) {
            var temp_chat = { ...chat };
            temp_chat["messages"].push(message);
            return temp_chat;
        } else {
            var temp_chat = {
                "messages": [message]
            }
            return temp_chat;
        }
    }

    // Handlers
    const newChat = (message) => {
        console.log(message);
        const startChat = async (message) => {
            try {
                const welcomeMessage = "Welcome to Stock Busters. I'm your AI assistant, and I'm here to help you gather your financial requirements. To start, may I please know your name?";
                
                const tempChat = {
                    messages: [
                        { role: 'assistant', content: welcomeMessage },
                        { role: 'user', content: message.message }
                    ]
                };
                setChat(tempChat);
                setHasActiveChat(true);
                setIsTyping(true);

                const response = await DataService.StartChatWithLLM(MODEL, message);
                console.log(response.data);

                setIsTyping(false);

                const transformedChat = {
                    chat_id: response.data.chat_id,
                    messages: [
                        { role: 'assistant', content: welcomeMessage },
                        { role: 'user', content: message.message },
                        { role: 'assistant', content: response.data.message }
                    ],
                    user_preferences: response.data.user_preferences,
                    completed: response.data.completed
                };

                setChat(transformedChat);
                setChatId(response.data.chat_id);
                router.push('/chat?id=' + response.data.chat_id);
            } catch (error) {
                console.error('Error fetching chat:', error);
                setIsTyping(false);
                setChat(null);
                setChatId(null);
                setHasActiveChat(false);
                router.push('/chat')
            }
        };
        startChat(message);
    };

    const appendChat = (message) => {
        console.log(message);
        const continueChat = async (id, message) => {
            try {
                setIsTyping(true);
                setHasActiveChat(true);

                const response = await DataService.ContinueChatWithLLM(MODEL, id, message);
                console.log(response.data);

                setIsTyping(false);

                const updatedChat = {
                    ...chat,
                    messages: [
                        ...chat.messages,
                        { role: 'user', content: message.message },
                        { role: 'assistant', content: response.data.message }
                    ],
                    user_preferences: response.data.user_preferences,
                    completed: response.data.completed
                };

                setChat(updatedChat);
                forceRefresh();
            } catch (error) {
                console.error('Error fetching chat:', error);
                setIsTyping(false);
                setChat(null);
                setHasActiveChat(false);
            }
        };
        continueChat(chat_id, message);
    };

    const forceRefresh = () => {
        setRefreshKey(prevKey => prevKey + 1);
    };

    const handleGenerateReport = async () => {
    if (!canGenerateReport) return;
    
    try {
        // Use chat_id from params (URL) instead of chatId from state
        const currentChatId = chat_id;  // This comes from params at the top of your component
        
        console.log('Chat ID:', currentChatId);
        console.log('Generating report for chat:', currentChatId);
        console.log('User preferences:', chat?.user_preferences);
        
        if (!currentChatId) {
            alert('Chat ID is missing. Please refresh the page.');
            return;
        }
        
        // Show loading state
        setIsTyping(true);
        
        // Call the backend API to generate report
        const response = await DataService.GenerateReport(
            MODEL, 
            currentChatId,  // Use chat_id from URL params
            chat?.user_preferences
        );
        
        console.log('Report response:', response.data);
        
        // Hide loading state
        setIsTyping(false);
        
        // Navigate to report page with report data
        const queryParams = new URLSearchParams({
            chat_id: currentChatId,
            user_pref: JSON.stringify(chat?.user_preferences || {}),
            report_id: response.data.report?.report_id || ''
        });
        
        router.push(`/report?${queryParams.toString()}`);
    } catch (error) {
        console.error('Error generating report:', error);
        setIsTyping(false);
        alert('Failed to generate report. Please try again.');
    }
};
    return (
    <div className="fixed inset-0 flex flex-col pt-16"> {/* Added pt-16 for navbar height */}
        {!hasActiveChat ? (
            <div className="h-full overflow-y-auto">
                <section className="flex-shrink-0 min-h-[400px] flex items-center justify-center bg-gradient-to-br from-primary/10 via-primary/5 to-accent">
                    <div className="absolute inset-0 bg-gradient-to-r from-primary/10 via-primary/5 to-transparent" />
                    <div className="container mx-auto px-4 max-w-3xl relative z-10 pt-20">
                        <div className="text-center">
                            <h1 className="text-4xl md:text-6xl font-bold gradient-text mb-6">
                                AI SmartInvestor 🌟
                            </h1>
                            <div className="bg-card/80 backdrop-blur-lg rounded-xl shadow-lg p-6 border border-border">
                                <ChatInput 
                                    onSendMessage={newChat}
                                    placeholderText="Tell me your name to get started..."
                                />
                            </div>
                        </div>
                    </div>
                </section>

                <div className="flex-1 container mx-auto px-4 py-12">
                    <ChatHistory />
                </div>
            </div>
        ) : (
            <div className="flex h-full overflow-hidden">
                <div className="w-80 flex-shrink-0 bg-card border-r border-border overflow-y-auto">
                    <ChatHistorySidebar chat_id={chat_id} />
                </div>

                <div className="flex-1 flex flex-col overflow-hidden">
                    {/* Header with Generate Report Button - Now visible below navbar */}
                    <div className="flex-shrink-0 border-b border-border bg-card p-4 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <h2 className="text-foreground font-medium">
                                {chat?.title || 'Chat'}
                            </h2>
                        </div>
                        <button
                            onClick={handleGenerateReport}
                            disabled={!canGenerateReport}
                            className={`px-4 py-2 rounded-lg font-medium transition-all ${
                                canGenerateReport
                                    ? 'bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm hover:shadow-md cursor-pointer'
                                    : 'bg-muted text-muted-foreground cursor-not-allowed opacity-50'
                            }`}
                        >
                            Generate Report
                        </button>
                    </div>

                    <div className="flex-1 overflow-y-auto">
                        <ChatMessage
                            chat={chat}
                            key={refreshKey}
                            isTyping={isTyping}
                        />
                    </div>
                    
                    <div className="flex-shrink-0 border-t border-border bg-card">
                        <ChatInput onSendMessage={appendChat} chat={chat} />
                    </div>
                </div>
            </div>
        )}
    </div>
);
}