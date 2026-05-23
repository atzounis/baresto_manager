function floorFieldCsrfToken() {
  const input = document.querySelector("[name=csrfmiddlewaretoken]");
  if (input?.value) return input.value;
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

document.addEventListener("alpine:init", () => {
  Alpine.data("floorField", () => ({
    open: false,
    floors: [],
    selectedId: "",
    newName: "",
    loading: false,
    error: "",
    csrfToken: "",
    floorApiUrl: "/floors/",
    i18n: {},

    init() {
      const dataEl = document.getElementById("floor-field-config");
      if (dataEl) {
        try {
          const cfg = JSON.parse(dataEl.textContent);
          this.floors = cfg.floors || [];
          this.selectedId = cfg.selectedId || "";
          this.csrfToken = cfg.csrfToken || floorFieldCsrfToken();
          this.floorApiUrl = cfg.floorApiUrl || "/floors/";
          this.i18n = cfg.i18n || {};
        } catch (e) {
          console.error("floorField config parse error", e);
        }
      } else {
        this.csrfToken = floorFieldCsrfToken();
      }
      this.$nextTick(() => this.refreshSelect(this.selectedId));
    },

    openModal() {
      this.open = true;
      this.newName = "";
      this.error = "";
      if (!this.csrfToken) this.csrfToken = floorFieldCsrfToken();
      document.body.classList.add("overflow-hidden");
      this.$nextTick(() => this.$refs.nameInput?.focus());
    },

    closeModal() {
      this.open = false;
      this.newName = "";
      this.error = "";
      document.body.classList.remove("overflow-hidden");
    },

    refreshSelect(selectedId) {
      const sel = document.getElementById("id_floor");
      if (!sel) return;
      const id = selectedId != null && selectedId !== "" ? String(selectedId) : sel.value;
      const prev = sel.value;
      sel.innerHTML = "";
      this.floors.forEach((f) => {
        const opt = document.createElement("option");
        opt.value = f.id;
        opt.textContent = f.label || f.name;
        sel.appendChild(opt);
      });
      if (id && [...sel.options].some((o) => o.value === id)) {
        sel.value = id;
      } else if (sel.options.length) {
        sel.value = sel.options[0].value;
      }
      const chosen = sel.value || prev;
      window.dispatchEvent(
        new CustomEvent("floors-updated", { detail: { floors: this.floors, selectedId: chosen } }),
      );
    },

    async addFloor() {
      const name = this.newName.trim();
      if (!name) return;
      this.loading = true;
      this.error = "";
      const csrf = this.csrfToken || floorFieldCsrfToken();
      try {
        const res = await fetch(this.floorApiUrl, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrf,
          },
          body: JSON.stringify({ name }),
        });
        let data = {};
        const text = await res.text();
        try {
          data = text ? JSON.parse(text) : {};
        } catch {
          if (!res.ok) throw new Error(this.i18n.saveFailed || "Save failed");
        }
        if (!res.ok) {
          throw new Error(data.detail || this.i18n.saveFailed || "Save failed");
        }
        const idx = this.floors.findIndex((f) => f.id === data.floor.id);
        if (idx >= 0) this.floors[idx] = data.floor;
        else this.floors.push(data.floor);
        this.floors.sort((a, b) => a.label.localeCompare(b.label));
        this.refreshSelect(data.floor.id);
        this.closeModal();
      } catch (err) {
        this.error = err.message || String(err);
      } finally {
        this.loading = false;
      }
    },
  }));
});
