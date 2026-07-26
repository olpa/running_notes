import template from "./account-tab.html?raw";
import { showStatus } from "../../dom.js";

export class AccountTab extends HTMLElement {
  connectedCallback() {
    if (this.initialized) return;
    this.initialized = true;
    this.innerHTML = template;
    this.email = this.querySelector(".account-email");
    this.status = this.querySelector(".status");
    this.querySelector(".logout").addEventListener("click", () => {
      this.dispatchEvent(new CustomEvent("logout-requested", { bubbles: true }));
    });
  }

  setUser(user) {
    this.email.textContent = user?.email || "";
  }

  activate() {}
  deactivate() {}

  reset() {
    this.setUser(null);
    showStatus(this.status, "");
  }
}

customElements.define("rn-account-tab", AccountTab);
