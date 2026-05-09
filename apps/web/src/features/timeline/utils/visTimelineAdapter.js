import { DataSet } from "vis-data";

export async function loadVisTimelineConstructor() {
  const { Timeline } = await import("vis-timeline/standalone");
  return Timeline;
}

export function createVisTimeline({
  Timeline,
  container,
  items,
  groups,
  options,
}) {
  const dataset = new DataSet(items ?? []);
  const timeline = new Timeline(container, dataset, groups, options);

  return { timeline, dataset };
}

export function replaceTimelineItems(timeline, dataset, items) {
  if (!timeline || !dataset) return;

  dataset.clear();
  dataset.add(items);
  timeline.setItems(dataset);
}

export function setTimelineGroups(timeline, groups) {
  if (!timeline || !groups) return;

  const updatedGroups = groups.map((group) => ({
    ...group,
    visible: group.visible !== false,
  }));
  timeline.setGroups(updatedGroups);
}

export function redrawTimelineWithRange(timeline, range) {
  if (!timeline) return;

  timeline.redraw();
  if (range) {
    timeline.setWindow(range.start, range.end, { animation: false });
  }
}

export function applyTimelineSelection(timeline, selectedRow) {
  if (!timeline) return null;

  if (selectedRow && timeline.itemsData.get(selectedRow)) {
    const currentWindow = timeline.getWindow();
    timeline.setSelection([selectedRow]);
    timeline.setWindow(currentWindow.start, currentWindow.end, {
      animation: false,
    });
    return currentWindow;
  }

  timeline.setSelection([]);
  return null;
}
