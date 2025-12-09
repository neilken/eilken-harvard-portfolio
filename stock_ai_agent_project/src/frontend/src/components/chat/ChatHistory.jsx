'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowRight, History } from 'lucide-react';
import DataService from "../../lib/DataService";
import { formatRelativeTime } from "../../lib/Common";

const MODEL = 'chatbot_final';

export default function ChatHistory() {
    const [chatHistory, setChatHistory] = useState([]);
    const [displayLimit, setDisplayLimit] = useState(6); // Show 6 initially
    const router = useRouter();

    useEffect(() => {
    const fetchData = async () => {
        try {
            const response = await DataService.GetChats(MODEL, 100);
            const chats = response.data.chats || [];
            // Reverse the array to show newest first
            setChatHistory(chats.reverse());
        } catch (error) {
            console.error('Error fetching chats:', error);
            setChatHistory([]);
        }
    };

    fetchData();
}, []);

    const handleViewAll = () => {
        if (displayLimit >= chatHistory.length) {
            // If showing all, reset to 6
            setDisplayLimit(6);
        } else {
            // Show all chats
            setDisplayLimit(chatHistory.length);
        }
    };

    const displayedChats = chatHistory.slice(0, displayLimit);
    const hasMore = chatHistory.length > displayLimit;

    return (
        <div className="max-w-4xl mx-auto w-full relative z-10">
            <div className="flex items-center justify-between mb-6">
                <h2 className="flex items-center gap-3 text-foreground text-xl font-semibold">
                    <History className="text-primary h-6 w-6" />
                    Your recent chats
                </h2>
                {chatHistory.length > 6 && (
                    <button 
                        onClick={handleViewAll}
                        className="flex items-center gap-2 px-4 py-2 text-muted-foreground hover:bg-accent rounded-lg transition-colors"
                    >
                        {hasMore ? 'View all' : 'Show less'}
                        <ArrowRight className={`w-4 h-4 transition-transform ${!hasMore ? 'rotate-180' : ''}`} />
                    </button>
                )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {displayedChats.length === 0 ? (
                    <div className="col-span-full text-center text-muted-foreground py-8">
                        No chat history yet. Start a new conversation!
                    </div>
                ) : (
                    displayedChats.map((chat) => (
                        <Link
                            key={chat.chat_id}
                            href={`/chat?id=${chat.chat_id}`}
                            className="block relative z-10"
                        >
                            <div
                                className="bg-card p-6 rounded-xl shadow-sm hover:shadow-md transition-shadow cursor-pointer border border-border"
                            >
                                <h3 className="text-foreground font-medium mb-2 line-clamp-2">
                                    {chat.title || 'Untitled Chat'}
                                </h3>
                                <span className="text-sm text-muted-foreground">
                                    {chat.message_count} messages
                                </span>
                            </div>
                        </Link>
                    ))
                )}
            </div>
        </div>
    );
}