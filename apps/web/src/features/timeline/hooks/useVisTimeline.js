// src/features/timeline/hooks/useVisTimeline.js (일부 수정)
import { useEffect, useRef } from "react";
import { useTimelineSelectionStore } from "../store/useTimelineSelectionStore";
import { useTimelineStore } from "../store/useTimelineStore";
import {
  applyTimelineSelection,
  createVisTimeline,
  loadVisTimelineConstructor,
  redrawTimelineWithRange,
  replaceTimelineItems,
  setTimelineGroups,
} from "../utils/visTimelineAdapter";

/**
 * vis-timeline 라이프사이클을 래핑하는 훅.
 * - 한 번 만든 Timeline/DataSet 인스턴스를 재사용
 * - 다른 타임라인들과 범위를 동기화
 * - 전역 선택 상태와 연결
 */
export function useVisTimeline({ containerRef, groups, items, options }) {
  const tlRef = useRef(null);
  const currentRangeRef = useRef(null);
  const previousHeightRef = useRef(null); // 이전 높이를 저장
  const datasetRef = useRef(null); // DataSet 인스턴스 재사용을 위한 ref
  const itemsRef = useRef(items);
  const groupsRef = useRef(groups);
  const optionsRef = useRef(options);

  const { setSelectedRow, selectedRow } = useTimelineSelectionStore();
  const { register, unregister, syncRange } = useTimelineStore();

  // 1. 컴포넌트 마운트 시 한 번만 인스턴스 생성
  useEffect(() => {
    let mounted = true;
    (async () => {
      const Timeline = await loadVisTimelineConstructor();
      if (!mounted || !containerRef.current) return;

      const { timeline, dataset } = createVisTimeline({
        Timeline,
        container: containerRef.current,
        items: itemsRef.current,
        groups: groupsRef.current,
        options: optionsRef.current,
      });
      datasetRef.current = dataset;
      tlRef.current = timeline;

      register(tlRef.current);

      tlRef.current.on("rangechange", ({ start, end }) => {
        currentRangeRef.current = { start, end };
        syncRange(tlRef.current, start, end);
      });

      tlRef.current.on("select", ({ items }) => {
        const currentSelected =
          useTimelineSelectionStore.getState().selectedRow;
        if (items && items.length > 0) {
          if (String(currentSelected) === String(items[0])) {
            setSelectedRow(null, "timeline");
            tlRef.current.setSelection([]);
          } else {
            setSelectedRow(items[0], "timeline");
          }
        } else {
          setSelectedRow(null, "timeline");
        }
      });
    })();

    return () => {
      mounted = false;
      if (tlRef.current) {
        unregister(tlRef.current);
        tlRef.current.destroy();
      }
      datasetRef.current = null;
    };
  }, [containerRef, register, unregister, syncRange, setSelectedRow]);

  // 2. 아이템 배열이 바뀌면 데이터셋 업데이트
  useEffect(() => {
    itemsRef.current = items;
    replaceTimelineItems(tlRef.current, datasetRef.current, items);
  }, [items]);

  // 3. 그룹 정보 변경 시 갱신
  useEffect(() => {
    groupsRef.current = groups;
    setTimelineGroups(tlRef.current, groups);
  }, [groups]);

  // 4. 옵션 변경 시 업데이트 (특히 높이)
  useEffect(() => {
    optionsRef.current = options;
    if (tlRef.current && options) {
      const heightChanged = previousHeightRef.current !== options.height;

      tlRef.current.setOptions(options);

      if (heightChanged) {
        previousHeightRef.current = options.height;

        setTimeout(() => {
          redrawTimelineWithRange(tlRef.current, currentRangeRef.current);
        }, 100);
      }
    }
  }, [options]);

  // 5. 외부에서 선택된 행을 타임라인에 반영
  useEffect(() => {
    const selectedRange = applyTimelineSelection(tlRef.current, selectedRow);
    if (selectedRange) {
      currentRangeRef.current = selectedRange;
    }
  }, [selectedRow]);

  return tlRef;
}
