export function createTabs(root) {
  const buttons = [...root.querySelectorAll("[data-tab]")];
  const panels = [...root.querySelectorAll("[data-panel]")];
  let activeName = null;

  function select(name) {
    if (!panels.some((panel) => panel.dataset.panel === name)) return;

    panels.forEach((panel) => {
      const active = panel.dataset.panel === name;
      panel.hidden = !active;
      if (active) panel.activate?.();
      else if (panel.dataset.panel === activeName) panel.deactivate?.();
    });
    buttons.forEach((button) => {
      if (button.dataset.tab === name) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });
    activeName = name;
  }

  buttons.forEach((button) => {
    button.addEventListener("click", () => select(button.dataset.tab));
  });

  return { select };
}
