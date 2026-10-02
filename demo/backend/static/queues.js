// Admin queues board (#7): drag a claim to another adjuster. The server renders
// every status chip and blocks any move it shouldn't send; this file mirrors the
// regulated-claim rule on dragover so a blocked drop is refused before it's sent.

(() => {
  const notice = document.getElementById("transfer-notice");
  if (!notice) return;

  const view = document.body.dataset.viewer || "admin";
  const faultToggle = document.getElementById("fault-toggle");
  const reviewRoles = new Set(["senior", "lead"]);
  let dragged = null;

  // Keep in step with queues.block_reason.
  const blockReason = (claim, queue) => {
    if (claim.closest("[data-queue]") === queue) return "Already in this queue.";
    if (claim.dataset.regulated !== "true") return null;
    const tier = claim.dataset.reviewTier;
    const name = queue.dataset.name;
    if (!queue.dataset.tiers.split(" ").includes(tier)) {
      return `Regulated claim needs human review: ${name} has no ${tier} review lane.`;
    }
    if (tier === "T3" && !reviewRoles.has(queue.dataset.role)) {
      return `Regulated ${tier} claim needs a senior or lead reviewer; ${name} is not.`;
    }
    return null;
  };

  const showNotice = (html) => {
    notice.innerHTML = html;
  };

  const blocked = (reason) => {
    const alert = document.createElement("div");
    alert.className = "alert-destructive";
    alert.setAttribute("role", "alert");
    const title = document.createElement("h4");
    title.textContent = "Move blocked";
    const body = document.createElement("section");
    body.textContent = reason;
    alert.append(title, body);
    notice.replaceChildren(alert);
  };

  const bumpLoad = (queue, delta) => {
    const load = queue.querySelector("[data-load]");
    load.textContent = String(Math.max(0, Number(load.textContent) + delta));
  };

  const move = (claim, queue) => {
    const from = claim.closest("[data-queue]");
    queue.querySelector("[data-claims]").prepend(claim);
    bumpLoad(from, -1);
    bumpLoad(queue, 1);
    return from;
  };

  document.addEventListener("dragstart", (e) => {
    const claim = e.target.closest?.("[data-claim]");
    if (!claim || claim.dataset.inFlight) return;
    dragged = claim;
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", claim.dataset.claim);
  });

  const unring = (queue) => queue.classList.remove("ring-2", "ring-primary", "ring-destructive");

  // A refused drop never fires "drop", so say why on release instead.
  document.addEventListener("dragend", (e) => {
    const claim = dragged;
    dragged = null;
    for (const q of document.querySelectorAll("[data-queue].ring-2")) unring(q);
    if (!claim || e.dataTransfer.dropEffect !== "none") return;
    const queue = document.elementFromPoint(e.clientX, e.clientY)?.closest("[data-queue]");
    const reason = queue && queue !== claim.closest("[data-queue]") && blockReason(claim, queue);
    if (reason) blocked(reason);
  });

  document.addEventListener("dragover", (e) => {
    const queue = e.target.closest?.("[data-queue]");
    if (!dragged || !queue) return;
    const ok = blockReason(dragged, queue) === null;
    queue.classList.add("ring-2", ok ? "ring-primary" : "ring-destructive");
    if (ok) e.preventDefault();
    e.dataTransfer.dropEffect = ok ? "move" : "none";
  });

  document.addEventListener("dragleave", (e) => {
    const queue = e.target.closest?.("[data-queue]");
    if (queue && !queue.contains(e.relatedTarget)) unring(queue);
  });

  document.addEventListener("drop", async (e) => {
    const queue = e.target.closest?.("[data-queue]");
    const claim = dragged;
    if (!queue || !claim || blockReason(claim, queue)) return;
    e.preventDefault();
    showNotice("");
    const id = claim.dataset.claim;
    const params = new URLSearchParams({ to: queue.dataset.queue, view });
    const res = await fetch(`/admin/queues/claims/${id}/transfer?${params}`, { method: "POST" });
    const html = await res.text();
    if (!res.ok) {
      showNotice(html);
      return;
    }
    claim.dataset.inFlight = "true";
    claim.dataset.from = move(claim, queue).dataset.queue;
    const status = claim.querySelector("[data-status]");
    status.innerHTML = html;
    window.htmx.process(status);
  });

  // When a write settles: unlock the claim, and put a failed move back where
  // ClaimsPro still has it. The chip swaps itself out, so scan the moves in flight.
  document.addEventListener("htmx:afterSettle", () => {
    for (const claim of document.querySelectorAll("[data-in-flight]")) {
      const state = claim.querySelector("[data-write-status]")?.dataset.writeStatus;
      if (state !== "confirmed" && state !== "failed") continue;
      delete claim.dataset.inFlight;
      const origin = document.querySelector(`[data-queue="${claim.dataset.from}"]`);
      if (state === "failed" && origin) move(claim, origin);
    }
  });

  faultToggle?.addEventListener("change", async () => {
    const params = new URLSearchParams({ on: String(faultToggle.checked), view });
    const res = await fetch(`/admin/queues/faults?${params}`, { method: "POST" });
    if (res.ok) faultToggle.checked = (await res.json()).on;
    else faultToggle.checked = !faultToggle.checked;
  });
})();
