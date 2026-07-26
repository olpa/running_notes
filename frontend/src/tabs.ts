import type { TabComponent } from "./contracts.js";

export interface Tabs {
  select(name: string): void;
}

export function createTabs(root: ParentNode): Tabs {
  const buttons = [...root.querySelectorAll<HTMLButtonElement>("[data-tab]")];
  const panels = [...root.querySelectorAll<TabComponent>("[data-panel]")];
  let activeName: string | null = null;

  function select(name: string): void {
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
      if (name) select(name);
    });
  });

  return { select };
}
