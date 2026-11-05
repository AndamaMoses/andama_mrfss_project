/* Dawa Ledger — specimen interactions only.
   This file is not part of the production design system. */

(() => {
  "use strict";

  /* ---------------------------------------------------------------------
     Index scroll-spy
     --------------------------------------------------------------------- */
  const navLinks = Array.from(document.querySelectorAll("#kitNav a"));
  const sections = navLinks
    .map((link) => document.querySelector(link.getAttribute("href")))
    .filter(Boolean);

  const setActive = (id) => {
    navLinks.forEach((link) => {
      link.classList.toggle("is-active", link.getAttribute("href") === `#${id}`);
    });
  };

  const spy = () => {
    const offset = window.scrollY + 140;
    let current = sections[0];
    for (const section of sections) {
      if (section.offsetTop <= offset) current = section;
    }
    if (current) setActive(current.id);
  };

  window.addEventListener("scroll", spy, { passive: true });
  spy();

  /* ---------------------------------------------------------------------
     Tabs
     --------------------------------------------------------------------- */
  document.querySelectorAll(".ds-tabs").forEach((tabs) => {
    const buttons = Array.from(tabs.querySelectorAll(".ds-tab"));
    buttons.forEach((button) => {
      button.addEventListener("click", () => {
        buttons.forEach((item) => {
          const active = item === button;
          item.classList.toggle("is-active", active);
          item.setAttribute("aria-selected", String(active));
        });
        buttons.forEach((item) => {
          const panel = document.getElementById(item.dataset.tab);
          if (panel) panel.hidden = item !== button;
        });
      });
    });
  });

  /* ---------------------------------------------------------------------
     Dialog
     --------------------------------------------------------------------- */
  const dialog = document.getElementById("demoDialog");
  if (dialog) {
    document.querySelectorAll("[data-open-dialog]").forEach((button) => {
      button.addEventListener("click", () => dialog.showModal());
    });
    document.querySelectorAll("[data-close-dialog]").forEach((button) => {
      button.addEventListener("click", () => dialog.close());
    });
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
  }

  /* ---------------------------------------------------------------------
     Drawer
     --------------------------------------------------------------------- */
  const drawer = document.getElementById("demoDrawer");
  const backdrop = document.querySelector("[data-drawer-backdrop]");

  const setDrawer = (open) => {
    if (!drawer || !backdrop) return;
    drawer.classList.toggle("is-open", open);
    backdrop.classList.toggle("is-open", open);
    drawer.setAttribute("aria-hidden", String(!open));
    document.body.style.overflow = open ? "hidden" : "";
    if (open) {
      const close = drawer.querySelector("[data-close-drawer]");
      if (close) close.focus();
    }
  };

  document.querySelectorAll("[data-open-drawer]").forEach((button) => {
    button.addEventListener("click", () => setDrawer(true));
  });
  document.querySelectorAll("[data-close-drawer]").forEach((button) => {
    button.addEventListener("click", () => setDrawer(false));
  });
  if (backdrop) backdrop.addEventListener("click", () => setDrawer(false));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setDrawer(false);
  });

  /* ---------------------------------------------------------------------
     Toast
     --------------------------------------------------------------------- */
  const toastWrap = document.getElementById("toastWrap");

  const showToast = (title, body) => {
    if (!toastWrap) return;
    const toast = document.createElement("div");
    toast.className = "ds-toast";
    toast.setAttribute("role", "status");
    toast.innerHTML = `
      <svg aria-hidden="true"><use href="#i-check"></use></svg>
      <div>
        <div class="ds-toast__title"></div>
        <div class="ds-toast__body"></div>
      </div>
      <button class="ds-toast__close" type="button" aria-label="Dismiss">×</button>`;
    toast.querySelector(".ds-toast__title").textContent = title;
    toast.querySelector(".ds-toast__body").textContent = body;
    const remove = () => toast.remove();
    toast.querySelector(".ds-toast__close").addEventListener("click", remove);
    toastWrap.appendChild(toast);
    window.setTimeout(remove, 6000);
  };

  document.querySelectorAll("[data-toast]").forEach((button) => {
    button.addEventListener("click", () => {
      showToast("Payment recorded", "Sale #0184 · UGX 12,500 · MTN MoMo");
    });
  });

  /* ---------------------------------------------------------------------
     Menu: close when clicking outside
     --------------------------------------------------------------------- */
  document.addEventListener("click", (event) => {
    document.querySelectorAll("details.ds-menu-wrap[open]").forEach((menu) => {
      if (!menu.contains(event.target)) menu.open = false;
    });
  });

  /* ---------------------------------------------------------------------
     Copy token snippet
     --------------------------------------------------------------------- */
  document.querySelectorAll("[data-copy]").forEach((button) => {
    button.addEventListener("click", async () => {
      const code = button.parentElement.querySelector("code");
      if (!code) return;
      try {
        await navigator.clipboard.writeText(code.innerText);
        const previous = button.textContent;
        button.textContent = "Copied";
        window.setTimeout(() => {
          button.textContent = previous;
        }, 1600);
      } catch {
        button.textContent = "Select";
      }
    });
  });
})();
