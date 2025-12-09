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

    // Check if report can be generated based on chat messages
    // Check if report can be generated based on completion status
useEffect(() => {
    if (chat) {
        // Enable report generation when chat is completed or user has confirmed preferences
        //const isCompleted = chat.completed === true;
        const hasConfirmed = chat.user_preferences?.confirmation === true;
        
        //setCanGenerateReport(isCompleted || hasConfirmed);
        setCanGenerateReport(hasConfirmed);
    } else {
        setCanGenerateReport(false);
    }
}, [chat]);

// Add this useEffect after your other useEffects
useEffect(() => {
    // Scroll to top when navigating to/from chat
    window.scrollTo({ top: 0, behavior: 'smooth' });
}, [chat_id]);

    function tempChatMessage(message) {
        // Set temp values
        message["message_id"] = uuid();
        message["role"] = 'user';
        if (chat) {
            // Append message
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
    // Start a new chat and submit to LLM
    const startChat = async (message) => {
        try {
            // Show welcome message and user's message immediately
            const welcomeMessage = "Welcome to Stock Busters. I'm your AI assistant, and I'm here to help you gather your financial requirements. To start, may I please know your name?";
            
            const tempChat = {
                messages: [
                    { role: 'assistant', content: welcomeMessage },
                    { role: 'user', content: message.message }
                ]
            };
            setChat(tempChat);
            setHasActiveChat(true);
            
            // Show typing indicator
            setIsTyping(true);

            // Submit chat
            const response = await DataService.StartChatWithLLM(MODEL, message);
            console.log(response.data);

            // Hide typing indicator
            setIsTyping(false);

            // Transform the response to match expected format
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
    // Append message and submit to LLM

    const continueChat = async (id, message) => {
        try {
            // Show typing indicator
            setIsTyping(true);
            setHasActiveChat(true);

            // Submit chat
            const response = await DataService.ContinueChatWithLLM(MODEL, id, message);
            console.log(response.data);

            // Hide typing indicator and add response
            setIsTyping(false);

            // Append new messages to existing chat
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
    // Force re-render by updating the key
    const forceRefresh = () => {
        setRefreshKey(prevKey => prevKey + 1);
    };

    const handleGenerateReport = () => {
    if (!canGenerateReport) return;
    
    console.log('Generating report for chat:', chatId);
    console.log('User preferences:', chat?.user_preferences);
    
    // Navigate to the report page with chat_id and user preferences
    const queryParams = new URLSearchParams({
        chat_id: chatId,
        // Pass user preferences as JSON string
        preferences: JSON.stringify(chat?.user_preferences || {})
    });
    
    router.push(`/report?${queryParams.toString()}`);
};

    return (
    <div className="h-screen flex flex-col overflow-hidden"> {/* Added overflow-hidden */}
        {!hasActiveChat ? (
            <div className="h-full overflow-y-auto"> {/* Wrap non-active chat in scrollable container */}
                {/* Hero Section */}
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

                {/* Chat History Section */}
                <div className="flex-1 container mx-auto px-4 py-12">
                    <ChatHistory />
                </div>
            </div>
        ) : (
            <div className="flex h-full overflow-hidden"> {/* Changed from h-[calc(100vh-64px)] to h-full */}
                {/* Sidebar */}
                <div className="w-80 flex-shrink-0 bg-card border-r border-border overflow-y-auto">
                    <ChatHistorySidebar chat_id={chat_id} />
                </div>

                {/* Main Chat Area */}
                <div className="flex-1 flex flex-col overflow-hidden"> {/* Added overflow-hidden */}
                    {/* Header with Generate Report Button - This stays fixed at top */}
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

                    {/* Chat Messages - This scrolls independently */}
                    <div className="flex-1 overflow-y-auto">
                        <ChatMessage
                            chat={chat}
                            key={refreshKey}
                            isTyping={isTyping}
                        />
                    </div>
                    
                    {/* Input area - Fixed at bottom */}
                    <div className="flex-shrink-0 border-t border-border bg-card">
                        <ChatInput onSendMessage={appendChat} chat={chat} />
                    </div>
                </div>
            </div>
        )}
    </div>
);}