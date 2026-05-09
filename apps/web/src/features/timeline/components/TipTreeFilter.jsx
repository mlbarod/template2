// src/features/timeline/components/TipTreeFilter.jsx
import React, { useEffect, useMemo, useState } from "react";
import TipTreeNode from "./filters/TipTreeNode";
import { buildTipGroupTree } from "../utils/tipTreeUtils";
import {
  TIP_FILTER_ALL,
  buildFilterValue,
  getAllPpidKeys,
  getNodePpidKeys,
  getPwqPpidKeys,
  hasPwqPpid,
} from "./filters/tipTreeFilterUtils";

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
    if (selectedTipGroups.includes(TIP_FILTER_ALL)) {
      return new Set();
    }
    return new Set(selectedTipGroups);
  });

  const [isAllSelected, setIsAllSelected] = useState(() => {
    return selectedTipGroups.includes(TIP_FILTER_ALL);
  });

  // selectedTipGroups prop이 변경될 때 내부 상태 업데이트
  useEffect(() => {
    if (selectedTipGroups.includes(TIP_FILTER_ALL)) {
      setIsAllSelected(true);
      setSelectedPpids(new Set());
      setExcludePwq(false);
    } else {
      setIsAllSelected(false);
      setSelectedPpids(new Set(selectedTipGroups));
      const hasPwqSelected = hasPwqPpid(tree, selectedTipGroups);
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

    onFilterChange(buildFilterValue(newIsAllSelected, newSelectedPpids));
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
      const ppidsToToggle = getNodePpidKeys(node);

      if (checked && !isAllSelected) {
        ppidsToToggle.forEach((key) => newSelectedPpids.add(key));
        if (hasPwqPpid(tree, ppidsToToggle)) {
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

    onFilterChange(buildFilterValue(newIsAllSelected, newSelectedPpids));
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

    if (node.level === "ppid") {
      return { checked: selectedPpids.has(node.key), indeterminate: false };
    }

    const childPpids = getNodePpidKeys(node);
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
      onFilterChange([TIP_FILTER_ALL]);
    }
    setExcludePwq(false);
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
        {Object.values(tree).map((lineNode) => (
          <TipTreeNode
            key={lineNode.key}
            node={lineNode}
            expandedNodes={expandedNodes}
            onToggleExpand={toggleExpand}
            onNodeSelect={handleNodeSelect}
            getNodeCheckState={getNodeCheckState}
          />
        ))}
      </div>
    </div>
  );
}
