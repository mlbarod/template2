import React from "react";
import { ChevronDownIcon, ChevronRightIcon } from "@heroicons/react/20/solid";
import { getTipTreeLevelStyle } from "./tipTreeFilterUtils";

export default function TipTreeNode({
  node,
  expandedNodes,
  onToggleExpand,
  onNodeSelect,
  getNodeCheckState,
}) {
  const hasChildren = Object.keys(node.children || {}).length > 0;
  const isExpanded = expandedNodes.has(node.key);
  const checkState = getNodeCheckState(node);
  const levelStyle = getTipTreeLevelStyle(node.level);

  return (
    <div key={node.key} className="select-none">
      <div
        className="flex items-center gap-1 rounded px-2 py-1.5 hover:bg-muted"
        style={{ paddingLeft: `${levelStyle.indent + 8}px` }}
      >
        {hasChildren ? (
          <button
            onClick={() => onToggleExpand(node.key)}
            className="rounded p-0.5 hover:bg-muted"
          >
            {isExpanded ? (
              <ChevronDownIcon className="w-4 h-4" />
            ) : (
              <ChevronRightIcon className="w-4 h-4" />
            )}
          </button>
        ) : (
          <div className="w-5" />
        )}

        <label className="flex items-center gap-2 flex-1 cursor-pointer">
          <input
            type="checkbox"
            checked={checkState.checked}
            ref={(input) => {
              if (input) {
                input.indeterminate = checkState.indeterminate;
              }
            }}
            onChange={(event) => onNodeSelect(node, event.target.checked)}
            className="rounded text-primary"
          />
          <span
            className={`text-sm ${levelStyle.color} flex items-center gap-1`}
          >
            <span>{levelStyle.icon}</span>
            <span>{node.name}</span>
            <span className="text-xs text-muted-foreground ml-1">
              ({node.count})
            </span>
          </span>
        </label>
      </div>

      {hasChildren && isExpanded && (
        <div className="ml-2 border-l-2 border-border">
          {Object.values(node.children).map((child) => (
            <TipTreeNode
              key={child.key}
              node={child}
              expandedNodes={expandedNodes}
              onToggleExpand={onToggleExpand}
              onNodeSelect={onNodeSelect}
              getNodeCheckState={getNodeCheckState}
            />
          ))}
        </div>
      )}
    </div>
  );
}
