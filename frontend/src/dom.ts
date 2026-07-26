export type StatusState = "" | "busy" | "success" | "error";

export function showStatus(
  element: HTMLElement,
  message: string,
  state: StatusState = "",
): void {
  element.textContent = message;
  element.className = `status ${state}`.trim();
}

export async function copyText(
  value: string,
  statusElement: HTMLElement,
  button: HTMLButtonElement,
): Promise<void> {
  try {
    await navigator.clipboard.writeText(value);
    showCopied(button);
    showStatus(statusElement, "Copied", "success");
  } catch (error) {
    showStatus(statusElement, `Copy failed: ${errorMessage(error)}`, "error");
  }
}

function showCopied(button: HTMLButtonElement): void {
  const originalText = button.dataset.originalText || button.textContent;
  button.dataset.originalText = originalText;
  window.clearTimeout(Number(button.dataset.resetTimer || 0));
  button.textContent = "Copied";
  button.classList.add("copied");
  button.disabled = true;
  button.dataset.resetTimer = String(window.setTimeout(() => {
    button.textContent = originalText;
    button.classList.remove("copied");
    button.disabled = false;
  }, 1200));
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function queryRequired<T extends Element>(
  root: ParentNode,
  selector: string,
): T {
  const element = root.querySelector<T>(selector);
  if (!element) throw new Error(`Missing required element: ${selector}`);
  return element;
}
