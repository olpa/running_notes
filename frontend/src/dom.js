export function showStatus(element, message, state = "") {
  element.textContent = message;
  element.className = `status ${state}`.trim();
}

export async function copyText(value, statusElement, button) {
  try {
    await navigator.clipboard.writeText(value);
    showCopied(button);
    showStatus(statusElement, "Copied", "success");
  } catch (error) {
    showStatus(statusElement, `Copy failed: ${error.message}`, "error");
  }
}

function showCopied(button) {
  if (!button) return;
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
