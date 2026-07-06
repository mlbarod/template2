// Observer log detail의 streaming 텍스트 표시 컴포넌트입니다.
import React, { useState, useEffect } from "react";

const streamedTextCache = new Set();

/**
 * 스트리밍 텍스트 애니메이션 컴포넌트
 */
export default function StreamingText({ text, speed = 8 }) {
  const [displayedText, setDisplayedText] = useState("");
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    if (streamedTextCache.has(text)) {
      setDisplayedText(text);
      setCurrentIndex(text.length);
      return;
    }

    setDisplayedText("");
    setCurrentIndex(0);
  }, [text]);

  useEffect(() => {
    if (currentIndex < text.length) {
      const timer = setTimeout(() => {
        setDisplayedText((prev) => prev + text[currentIndex]);
        setCurrentIndex((prev) => prev + 1);
      }, speed);

      return () => clearTimeout(timer);
    }
    if (text) {
      streamedTextCache.add(text);
    }
  }, [currentIndex, text, speed]);

  return (
    <span className="block max-w-full overflow-x-auto whitespace-pre break-normal">
      {displayedText}
      {currentIndex < text.length && (
        <span className="ml-0.5 inline-block h-4 w-2 animate-pulse bg-muted-foreground" />
      )}
    </span>
  );
}
