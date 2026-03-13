import React, { useState, useEffect, useRef } from 'react';

// TypingEffect types text character-by-character.
const TypingEffect = ({ fullText, isStreaming }) => {
    const [displayedText, setDisplayedText] = useState('');
    const typedLengthRef = useRef(0);
    const intervalRef = useRef(null);
    const fullTextRef = useRef(fullText); // Always current - avoids stale closure

    // Keep ref synced on every render
    fullTextRef.current = fullText;

    useEffect(() => {
        // New text arrived - start interval if not already running
        if (typedLengthRef.current < fullText.length && !intervalRef.current) {
            intervalRef.current = setInterval(() => {
                const current = fullTextRef.current; // Always reads latest text
                if (typedLengthRef.current < current.length) {
                    typedLengthRef.current = Math.min(typedLengthRef.current + 4, current.length);
                    setDisplayedText(current.slice(0, typedLengthRef.current));
                } else {
                    // Fully caught up - stop interval
                    clearInterval(intervalRef.current);
                    intervalRef.current = null;
                }
            }, 16); // ~60 fps
        }

        return () => { }; // Don't clear interval on re-render - let it keep running
    }, [fullText]);

    // Auto-scroll as text types out
    useEffect(() => {
        const el = document.querySelector('.chat-messages');
        if (el) el.scrollTop = el.scrollHeight;
    }, [displayedText]);

    // Cursor blinks while streaming OR still typing
    const isCursorVisible = isStreaming || (intervalRef.current !== null);

    return (
        <span style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {displayedText}
            {isCursorVisible && <span style={{ opacity: 0.7 }}>▋</span>}
        </span>
    );
};

export default TypingEffect;
