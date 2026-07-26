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
    this.email.textContent = user?.email || "";
  }

  activate(): void {}
  deactivate(): void {}

  reset(): void {
    this.setUser(null);
    showStatus(this.status, "");
  }
}

customElements.define("rn-account-tab", AccountTab);
