// src/features/timeline/components/TipTreeFilter.jsx
import React, { useEffect, useMemo, useState } from "react";
import { ChevronRightIcon, ChevronDownIcon } from "@heroicons/react/20/solid";
import { buildTipGroupTree } from "../utils/tipTreeUtils";

function getAllPpidKeys(tree) {
  const ppids = [];
  Object.values(tree).forEach((lineNode) => {
    Object.values(lineNode.children).forEach((processNode) => {
      Object.values(processNode.children).forEach((stepNode) => {
        Object.values(stepNode.children).forEach((ppidNode) => {
          ppids.push(ppidNode.key);
        });
      });
    });
  });
  return ppids;
}

function getPwqPpidKeys(tree) {
  const pwqPpids = [];
  Object.values(tree).forEach((lineNode) => {
    Object.values(lineNode.children).forEach((processNode) => {
      Object.values(processNode.children).forEach((stepNode) => {
        Object.values(stepNode.children).forEach((ppidNode) => {
          // ppid name이 pwq로 시작하는지 확인
          if (ppidNode.name.toLowerCase().startsWith("pwq")) {
            pwqPpids.push(ppidNode.key);
          }
        });
      });
    });
  });
  return pwqPpids;
}

/**
 * TIP 그룹 필터 트리
 * - isAllSelected / selectedPpids / excludePwq 세 상태를 조합해 필터링 로직을 표현
 * - 부모 노드 선택 시 하위 PPID 전체를 토글
 * - PWQ 제외 옵션이 활성화되면 선택된 집합에서 PWQ만 제거
 */
export default function TipTreeFilter({
  tipLogs,
  onFilterChange,
  selectedTipGroups,
  inDrawer = false,
}) {
  const [expandedNodes, setExpandedNodes] = useState(new Set(["LINE01"]));
  const [excludePwq, setExcludePwq] = useState(false);

  // 트리 구조 생성
  const tree = useMemo(() => buildTipGroupTree(tipLogs), [tipLogs]);

  // 초기 선택 상태를 selectedTipGroups 기반으로 설정
  const [selectedPpids, setSelectedPpids] = useState(() => {
    if (selectedTipGroups.includes("__ALL__")) {
      return new Set();
    }
    return new Set(selectedTipGroups);
  });

  const [isAllSelected, setIsAllSelected] = useState(() => {
    return selectedTipGroups.includes("__ALL__");
  });

  // selectedTipGroups prop이 변경될 때 내부 상태 업데이트
  useEffect(() => {
    if (selectedTipGroups.includes("__ALL__")) {
      setIsAllSelected(true);
      setSelectedPpids(new Set());
      setExcludePwq(false);
    } else {
      setIsAllSelected(false);
      setSelectedPpids(new Set(selectedTipGroups));
      // PWQ 항목이 선택되어 있는지 확인
      const pwqKeys = getPwqPpidKeys(tree);
      const hasPwqSelected = pwqKeys.some((key) =>
        selectedTipGroups.includes(key)
      );
      setExcludePwq(!hasPwqSelected && selectedTipGroups.length > 0);
    }
  }, [selectedTipGroups, tree]);

  // PWQ 미포함 체크박스 핸들러
  const handleExcludePwqChange = (checked) => {
    setExcludePwq(checked);

    const allPpidKeys = getAllPpidKeys(tree);
    const pwqPpidKeys = getPwqPpidKeys(tree);
    const newSelectedPpids = new Set(selectedPpids);
    let newIsAllSelected = isAllSelected;

    if (checked) {
      // PWQ 미포함 체크됨: PWQ 항목들을 제거
      if (isAllSelected) {
        // 전체 선택 상태에서는 전체 선택 해제하고 PWQ만 제외
        newIsAllSelected = false;
        allPpidKeys.forEach((key) => {
          if (!pwqPpidKeys.includes(key)) {
            newSelectedPpids.add(key);
          }
        });
      } else {
        // 개별 선택 상태에서는 PWQ 항목만 제거
        pwqPpidKeys.forEach((key) => newSelectedPpids.delete(key));
      }
    } else {
      // PWQ 미포함 해제됨: PWQ 항목들을 추가
      if (newSelectedPpids.size === 0) {
        // 아무것도 선택되지 않았으면 전체 선택
        newIsAllSelected = true;
        newSelectedPpids.clear();
      } else {
        // PWQ 항목들 추가
        pwqPpidKeys.forEach((key) => newSelectedPpids.add(key));
        // 모든 항목이 선택되었는지 확인
        if (newSelectedPpids.size === allPpidKeys.length) {
          newIsAllSelected = true;
          newSelectedPpids.clear();
        }
      }
    }

    setSelectedPpids(newSelectedPpids);
    setIsAllSelected(newIsAllSelected);

    // 부모 컴포넌트에 알림
    if (newIsAllSelected) {
      onFilterChange(["__ALL__"]);
    } else if (newSelectedPpids.size === 0) {
      onFilterChange([]);
    } else {
      onFilterChange(Array.from(newSelectedPpids));
    }
  };

  // 노드 확장/축소
  const toggleExpand = (nodeKey) => {
    const newExpanded = new Set(expandedNodes);
    if (newExpanded.has(nodeKey)) {
      newExpanded.delete(nodeKey);
    } else {
      newExpanded.add(nodeKey);
    }
    setExpandedNodes(newExpanded);
  };

  // 노드 선택 처리
  const handleNodeSelect = (node, checked) => {
    const newSelectedPpids = new Set(selectedPpids);
    let newIsAllSelected = isAllSelected;
    let newExcludePwq = excludePwq;

    if (isAllSelected && !checked) {
      newIsAllSelected = false;
      getAllPpidKeys(tree).forEach((key) => newSelectedPpids.add(key));
    }

    // 노드 타입에 따라 처리
    if (node.level === "ppid") {
      if (checked && !isAllSelected) {
        newSelectedPpids.add(node.key);
        // PWQ 항목이 선택되면 excludePwq 해제
        if (node.name.toLowerCase().startsWith("pwq")) {
          newExcludePwq = false;
        }
      } else {
        newSelectedPpids.delete(node.key);
      }
    } else {
      // 상위 노드 선택 시 하위 ppid들 처리
      const ppidsToToggle = [];

      if (node.level === "line") {
        Object.values(node.children).forEach((processNode) => {
          Object.values(processNode.children).forEach((stepNode) => {
            Object.values(stepNode.children).forEach((ppidNode) => {
              ppidsToToggle.push(ppidNode.key);
            });
          });
        });
      } else if (node.level === "process") {
        Object.values(node.children).forEach((stepNode) => {
          Object.values(stepNode.children).forEach((ppidNode) => {
            ppidsToToggle.push(ppidNode.key);
          });
        });
      } else if (node.level === "step") {
        Object.values(node.children).forEach((ppidNode) => {
          ppidsToToggle.push(ppidNode.key);
        });
      }

      if (checked && !isAllSelected) {
        ppidsToToggle.forEach((key) => newSelectedPpids.add(key));
        // PWQ 항목이 포함되면 excludePwq 해제
        const hasPwq = ppidsToToggle.some((key) => {
          const ppidNodes = [];
          Object.values(tree).forEach((lineNode) => {
            Object.values(lineNode.children).forEach((processNode) => {
              Object.values(processNode.children).forEach((stepNode) => {
                Object.values(stepNode.children).forEach((ppidNode) => {
                  if (ppidNode.key === key) {
                    ppidNodes.push(ppidNode);
                  }
                });
              });
            });
          });
          return ppidNodes.some((node) =>
            node.name.toLowerCase().startsWith("pwq")
          );
        });
        if (hasPwq) {
          newExcludePwq = false;
        }
      } else {
        ppidsToToggle.forEach((key) => newSelectedPpids.delete(key));
      }
    }

    // 모든 ppid가 선택되었는지 확인
    if (newSelectedPpids.size === getAllPpidKeys(tree).length) {
      newIsAllSelected = true;
      newSelectedPpids.clear();
      newExcludePwq = false;
    }

    setSelectedPpids(newSelectedPpids);
    setIsAllSelected(newIsAllSelected);
    setExcludePwq(newExcludePwq);

    // 부모 컴포넌트에 알림
    if (newIsAllSelected) {
      onFilterChange(["__ALL__"]);
    } else if (newSelectedPpids.size === 0) {
      onFilterChange([]);
    } else {
      onFilterChange(Array.from(newSelectedPpids));
    }
  };

  // 노드의 선택 상태 확인
  const getNodeCheckState = (node) => {
    if (isAllSelected) {
      // 전체 선택 상태에서 PWQ 제외가 체크되어 있고 PWQ 노드인 경우
      if (
        excludePwq &&
        node.level === "ppid" &&
        node.name.toLowerCase().startsWith("pwq")
      ) {
        return { checked: false, indeterminate: false };
      }
      return { checked: true, indeterminate: false };
    }

    let childPpids = [];

    if (node.level === "ppid") {
      return { checked: selectedPpids.has(node.key), indeterminate: false };
    } else if (node.level === "line") {
      Object.values(node.children).forEach((processNode) => {
        Object.values(processNode.children).forEach((stepNode) => {
          Object.values(stepNode.children).forEach((ppidNode) => {
            childPpids.push(ppidNode.key);
          });
        });
      });
    } else if (node.level === "process") {
      Object.values(node.children).forEach((stepNode) => {
        Object.values(stepNode.children).forEach((ppidNode) => {
          childPpids.push(ppidNode.key);
        });
      });
    } else if (node.level === "step") {
      Object.values(node.children).forEach((ppidNode) => {
        childPpids.push(ppidNode.key);
      });
    }

    const selectedCount = childPpids.filter((key) =>
      selectedPpids.has(key)
    ).length;

    return {
      checked: selectedCount === childPpids.length,
      indeterminate: selectedCount > 0 && selectedCount < childPpids.length,
    };
  };

  // 전체 선택/해제
  const handleSelectAll = () => {
    if (isAllSelected) {
      setSelectedPpids(new Set());
      setIsAllSelected(false);
      onFilterChange([]);
    } else {
      setSelectedPpids(new Set());
      setIsAllSelected(true);
      onFilterChange(["__ALL__"]);
    }
    setExcludePwq(false);
  };

  // 레벨별 스타일
  const getLevelStyle = (level) => {
    const styles = {
      line: {
        color: "text-primary",
        indent: 0,
        icon: "📍",
      },
      process: {
        color: "text-primary",
        indent: 10,
        icon: "⚙️",
      },
      step: {
        color: "text-primary",
        indent: 20,
        icon: "📋",
      },
      ppid: {
        color: "text-primary",
        indent: 30,
        icon: "🔧",
      },
    };
    return styles[level] || { color: "", indent: 0, icon: "" };
  };

  // 트리 노드 렌더링
  const renderTreeNode = (node) => {
    const hasChildren = Object.keys(node.children || {}).length > 0;
    const isExpanded = expandedNodes.has(node.key);
    const checkState = getNodeCheckState(node);
    const levelStyle = getLevelStyle(node.level);

    return (
      <div key={node.key} className="select-none">
        <div
          className="flex items-center gap-1 rounded px-2 py-1.5 hover:bg-muted"
          style={{ paddingLeft: `${levelStyle.indent + 8}px` }}
        >
          {hasChildren ? (
            <button
              onClick={() => toggleExpand(node.key)}
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
              onChange={(e) => handleNodeSelect(node, e.target.checked)}
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
            {Object.values(node.children).map((child) => renderTreeNode(child))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div
      className={inDrawer ? "" : "border border-border bg-card rounded-lg mb-2"}
    >
      <div className="flex items-center justify-between mb-3">
        {!inDrawer && (
          <h4 className="text-sm font-semibold text-foreground">
            TIP 그룹 필터
          </h4>
        )}
        <div className="flex items-center justify-between w-full">
          {/* 왼쪽: 전체 선택 */}
          <button
            onClick={handleSelectAll}
            className="text-xs text-primary hover:underline"
          >
            {isAllSelected ? "전체 해제" : "전체 선택"}
          </button>

          {/* 오른쪽: PWQ 미포함 */}
          <label className="flex items-center gap-1 cursor-pointer">
            <input
              type="checkbox"
              checked={excludePwq}
              onChange={(e) => handleExcludePwqChange(e.target.checked)}
              className="rounded text-primary"
            />
            <span className="text-xs text-muted-foreground">
              PWQ 필터
            </span>
          </label>
        </div>
      </div>

      <div className="max-h-96 overflow-y-auto ml-0">
        {Object.values(tree).map((lineNode) => renderTreeNode(lineNode))}
      </div>
    </div>
  );
}
