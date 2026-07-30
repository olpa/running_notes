import template from "./account-tab.html?raw";
import type { User } from "../../contracts.js";
import { queryRequired, showStatus } from "../../dom.js";

export class AccountTab extends HTMLElement {
  private initialized = false;
  private email!: HTMLElement;
  private status!: HTMLElement;

  connectedCallback(): void {
    if (this.initialized) return;
    this.initialized = true;
    this.innerHTML = template;
    this.email = queryRequired<HTMLElement>(this, ".account-email");
    this.status = queryRequired<HTMLElement>(this, ".status");
    queryRequired<HTMLButtonElement>(this, ".logout").addEventListener("click", () => {
      this.dispatchEvent(new CustomEvent("logout-requested", { bubbles: true }));
    });
  }

  setUser(user: User | null): void {
    this.email.textContent = user ? formatSignedInIdentity(user) : "";
  }

  activate(): void {}
  deactivate(): void {}

  reset(): void {
    this.setUser(null);
    showStatus(this.status, "");
  }
}

function formatSignedInIdentity(user: User): string {
  if (user.is_guest) return `${user.email} (Guest)`;
  if (!user.auth_provider) return user.email;
  const provider = user.auth_provider.charAt(0).toUpperCase()
    + user.auth_provider.slice(1);
  return `${user.email} via ${provider}`;
}

customElements.define("rn-account-tab", AccountTab);
