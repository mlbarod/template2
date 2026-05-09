export const TIP_FILTER_ALL = "__ALL__";

export function getNodePpidKeys(node) {
  if (!node) return [];
  if (node.level === "ppid") return [node.key];

  return Object.values(node.children || {}).flatMap((child) =>
    getNodePpidKeys(child)
  );
}

export function getAllPpidKeys(tree) {
  return Object.values(tree).flatMap((lineNode) => getNodePpidKeys(lineNode));
}

export function getPwqPpidKeys(tree) {
  return Object.values(tree).flatMap((lineNode) =>
    getPwqPpidNodes(lineNode).map((node) => node.key)
  );
}

export function hasPwqPpid(tree, ppidKeys) {
  const keySet = new Set(ppidKeys);
  return Object.values(tree).some((lineNode) =>
    getPwqPpidNodes(lineNode).some((node) => keySet.has(node.key))
  );
}

export function buildFilterValue(isAllSelected, selectedPpids) {
  if (isAllSelected) return [TIP_FILTER_ALL];
  if (selectedPpids.size === 0) return [];
  return Array.from(selectedPpids);
}

export function getTipTreeLevelStyle(level) {
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
}

function getPwqPpidNodes(node) {
  if (!node) return [];
  if (node.level === "ppid") {
    return node.name.toLowerCase().startsWith("pwq") ? [node] : [];
  }

  return Object.values(node.children || {}).flatMap((child) =>
    getPwqPpidNodes(child)
  );
}
