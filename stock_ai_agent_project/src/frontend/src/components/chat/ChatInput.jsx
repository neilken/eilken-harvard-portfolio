'use client';

import { useState, useRef, useEffect } from 'react';
import { Send } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';

export default function ChatInput({ onSendMessage, placeholderText }) {
    // Component States
    const [message, setMessage] = useState('');
    const textAreaRef = useRef(null);

    const adjustTextAreaHeight = () => {
        const textarea = textAreaRef.current;
        if (textarea) {
            textarea.style.height = 'auto';
            textarea.style.height = `${textarea.scrollHeight}px`;
        }
    };

    // Setup Component
    useEffect(() => {
        adjustTextAreaHeight();
    }, [message]);

    // Auto-focus the textarea when component mounts
    useEffect(() => {
        if (textAreaRef.current) {
            textAreaRef.current.focus();
        }
    }, []); // Empty dependency array means this runs once on mount

    // Handlers
    const handleMessageChange = (e) => {
        setMessage(e.target.value);
    };
    
    const handleKeyPress = (e) => {
        if (e.key === 'Enter') {
            if (e.shiftKey) {
                // Shift + Enter: add new line
                return;
            } else {
                // Enter only: submit
                e.preventDefault();
                handleSubmit();
            }
        }
    };
    
    const handleSubmit = () => {
        if (message.trim()) {
            console.log('Submitting message:', message);
            const newMessage = {
                message: message.trim()
            };

            // Send the message
            onSendMessage(newMessage);

            // Reset
            setMessage('');
            if (textAreaRef.current) {
                textAreaRef.current.style.height = 'auto';
                // Keep focus after sending
                textAreaRef.current.focus();
            }
        }
    };

    // UI View
    return (
        <div className="bg-card/80 backdrop-blur-lg rounded-xl shadow-lg p-6 border border-border">
            <div className="relative mb-4">
                <Textarea
                    ref={textAreaRef}
                    className="w-full min-h-[56px] max-h-[400px] pr-12 resize-none"
                    placeholder={placeholderText || "How can AI SmartInvestor help you today?"}
                    value={message}
                    onChange={handleMessageChange}
                    onKeyDown={handleKeyPress}
                    rows={1}
                    autoFocus  // Add this HTML attribute as well
                />
                <Button
                    size="icon"
                    className={`absolute right-2 bottom-2 rounded-full transition-all
                              ${message.trim()
                            ? 'bg-primary text-primary-foreground hover:shadow-lg'
                            : 'opacity-50 cursor-not-allowed'}`}
                    onClick={handleSubmit}
                    disabled={!message.trim()}
                >
                    <Send className="w-5 h-5" />
                </Button>
            </div>

            <div className="flex justify-end items-center border-t border-border pt-4">
                <span className="text-sm text-muted-foreground">
                    Use shift + return for new line
                </span>
            </div>
        </div>
    );
}