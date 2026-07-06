// Observer log detail의 streaming 텍스트 표시 컴포넌트입니다.
import React, { useState, useEffect, useRef } from "react";

const streamedTextCache = new Set();

/**
 * 스트리밍 텍스트 애니메이션 컴포넌트
 */
export default function StreamingText({
  text,
  speed = 8,
  className = "",
  scrollClassName = "max-w-full overflow-x-auto",
  active = true,
  onProgress,
  onComplete,
}) {
  const [displayedText, setDisplayedText] = useState("");
  const [currentIndex, setCurrentIndex] = useState(0);
  const onCompleteRef = useRef(onComplete);

  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  useEffect(() => {
    if (!active) {
      setDisplayedText("");
      setCurrentIndex(0);
      return;
    }

    if (streamedTextCache.has(text)) {
      setDisplayedText(text);
      setCurrentIndex(text.length);
      return;
    }

    setDisplayedText("");
    setCurrentIndex(0);
  }, [active, text]);

  useEffect(() => {
    if (!active) return undefined;

    if (currentIndex < text.length) {
      const timer = setTimeout(() => {
        setDisplayedText((prev) => prev + text[currentIndex]);
        setCurrentIndex((prev) => prev + 1);
      }, speed);

      return () => clearTimeout(timer);
    }

    return undefined;
  }, [active, currentIndex, text, speed]);

  useEffect(() => {
    if (!active || !text || currentIndex < text.length) return;

    streamedTextCache.add(text);
    onCompleteRef.current?.();
  }, [active, currentIndex, text]);

  useEffect(() => {
    if (displayedText) {
      onProgress?.();
    }
  }, [displayedText, onProgress]);

  return (
    <span className={`block whitespace-pre break-normal ${scrollClassName} ${className}`}>
      {displayedText}
      {active && currentIndex < text.length && (
        <span className="ml-0.5 inline-block h-4 w-2 animate-pulse bg-muted-foreground" />
      )}
    </span>
  );
}
