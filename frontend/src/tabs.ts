import type { TabComponent, TabName } from "./contracts.js";

export interface Tabs {
  select(name: TabName): void;
}

export function createTabs(
  root: ParentNode,
  onNavigationRequested: (tab: TabName) => void,
): Tabs {
  const buttons = [...root.querySelectorAll<HTMLButtonElement>("[data-tab]")];
  const panels = [...root.querySelectorAll<TabComponent>("[data-panel]")];
  let activeName: string | null = null;

  function select(name: TabName): void {
    if (!panels.some((panel) => panel.dataset.panel === name)) return;

    panels.forEach((panel) => {
      const active = panel.dataset.panel === name;
      panel.hidden = !active;
      if (active) panel.activate();
      else if (panel.dataset.panel === activeName) panel.deactivate?.();
    });
    buttons.forEach((button) => {
      if (button.dataset.tab === name) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });
    activeName = name;
  }

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      const name = button.dataset.tab;
      if (isTabName(name)) onNavigationRequested(name);
    });
  });

  return { select };
}

function isTabName(value: string | undefined): value is TabName {
  return value === "record"
    || value === "messages"
    || value === "imap"
    || value === "account";
}
