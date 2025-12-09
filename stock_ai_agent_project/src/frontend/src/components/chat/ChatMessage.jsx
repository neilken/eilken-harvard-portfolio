'use client';

import { useState, useRef, useEffect } from 'react';
import { User, Bot, MessageSquare, Eye } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import DataService from "../../lib/DataService";

const MODEL = 'chatbot_final'; // Single model constant

export default function ChatMessage({ chat, isTyping }) {
    // Component States
    const chatHistoryRef = useRef(null);
    const messagesEndRef = useRef(null);

    // Auto-scroll to bottom when new messages are added
    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [chat?.messages, isTyping]);

    // Helper function to format time
    const formatTime = (timestamp) => {
        const date = new Date(timestamp);
        const now = new Date();
        const isToday = date.toDateString() === now.toDateString();
        
        if (isToday) {
            return date.toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit'
            });
        } else {
            return date.toLocaleString([], {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        }
    };

    // UI View
    return (
        <div className="flex flex-col h-full overflow-hidden">
            {chat && (
                <div className="flex items-center gap-3 p-4 border-b border-border bg-card">
                    <MessageSquare className="text-primary h-5 w-5" />
                    <h1 className="text-foreground font-medium">{chat.title || 'Chat'}</h1>
                </div>
            )}

            <div 
                ref={chatHistoryRef}
                className="flex-1 overflow-y-auto p-4"
            >
                <div className="space-y-4">
                    {chat?.messages.map((msg, index) => (
                        <div
                            key={index}
                            className={`chat-message ${msg.role === 'user' ? 'chat-message-user' : 'chat-message-assistant'}`}
                        >
                            <div className={`p-2 rounded-full ${msg.role === 'assistant' ? 'bg-primary/10' :
                                msg.role === 'cnn' ? 'bg-pink-500/10 dark:bg-pink-400/10' : 'bg-muted'
                                }`}>
                                {msg.role === 'assistant' && <Bot className="text-primary h-5 w-5" />}
                                {msg.role === 'cnn' && <Eye className="text-pink-600 dark:text-pink-400 h-5 w-5" />}
                                {msg.role === 'user' && <User className="text-muted-foreground h-5 w-5" />}
                            </div>

                            <div className={`rounded-2xl p-4 shadow-sm ${msg.role === 'user'
                                ? 'bg-primary text-primary-foreground'
                                : 'bg-card text-foreground border border-border'
                                }`}>
                                {msg.image && (
                                    <img src={msg.image} alt="Chat" className="max-w-md rounded-lg mb-2" />
                                )}
                                {msg.image_path && (
                                    <img
                                        src={DataService.GetChatMessageImage(MODEL, msg.image_path)}
                                        alt="Chat"
                                        className="max-w-md rounded-lg mb-2"
                                    />
                                )}

                                <div className={`prose ${msg.role === 'user' ? 'prose-invert' : 'dark:prose-invert'} max-w-none`}>
                                    <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
                                        {msg.content}
                                    </ReactMarkdown>
                                </div>

                                {msg.results && (
                                    <div className="mt-2 text-sm">
                                        {msg.results.prediction_label}&nbsp;
                                        ({msg.results.accuracy}%)
                                    </div>
                                )}

                                <div className="mt-2 text-xs opacity-60">
                                    {msg.timestamp ? formatTime(msg.timestamp) : formatTime(new Date())}
                                </div>
                            </div>
                        </div>
                    ))}

                    {isTyping && (
                        <div className="flex justify-center p-4">
                            <div className="flex gap-2">
                                {[...Array(3)].map((_, i) => (
                                    <div
                                        key={i}
                                        className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce"
                                        style={{ animationDelay: `${i * 0.2}s` }}
                                    />
                                ))}
                            </div>
                        </div>
                    )}
                    
                    {/* Invisible element at the bottom to scroll to */}
                    <div ref={messagesEndRef} />
                </div>
            </div>
        </div>
    );
}