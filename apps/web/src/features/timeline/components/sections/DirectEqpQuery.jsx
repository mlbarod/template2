import React from "react";

export default function DirectEqpQuery({
  inputEqpId,
  isLoading,
  onInputChange,
  onKeyPress,
  onSubmit,
}) {
  return (
    <div className="flex gap-2">
      <input
        type="text"
        value={inputEqpId}
        onChange={onInputChange}
        onKeyPress={onKeyPress}
        placeholder="EQP ID 입력..."
        disabled={isLoading}
        autoFocus
        className="flex-1 h-8 rounded-lg border border-border bg-card px-3 py-1.5 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background disabled:opacity-50"
      />
      <button
        onClick={onSubmit}
        disabled={isLoading || !inputEqpId.trim()}
        className="h-8 whitespace-nowrap rounded-lg bg-primary px-4 py-1.5 text-xs text-primary-foreground hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50"
      >
        {isLoading ? "조회중" : "조회"}
      </button>
    </div>
  );
}
