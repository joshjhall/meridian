// Admin queues board (#7): drag a claim to another adjuster. The server renders
// every status chip and blocks any move it shouldn't send; this file mirrors the
// review-lane rule on dragover so a blocked drop is refused before it's sent.

(() => {
  const notice = document.getElementById("transfer-notice");
  if (!notice) return;

  const view = document.body.dataset.viewer || "admin";
  const faultToggle = document.getElementById("fault-toggle");
  const reviewRoles = new Set(["senior", "lead"]);
  let dragged = null;

  // Keep in step with queues.block_reason (and the pipeline's assign.match).
  const blockReason = (claim, queue) => {
    if (claim.closest("[data-queue]") === queue) return "Already in this queue.";
    if (claim.dataset.needsReview !== "true") return null;
    const tier = claim.dataset.reviewTier;
    const name = queue.dataset.name;
    const reason = claim.dataset.reviewReason;
    const why = reason.charAt(0).toUpperCase() + reason.slice(1);
    if (!queue.dataset.tiers.split(" ").includes(tier)) {
      return `${why}: ${name} has no ${tier} review lane.`;
    }
    if (tier === "T3" && !reviewRoles.has(queue.dataset.role)) {
      return `${why}: ${tier} needs a senior or lead reviewer; ${name} is not.`;
    }
    return null;
  };

  // Every POST carries this header; the server refuses any without it (CSRF guard).
  const post = (url) => fetch(url, { method: "POST", headers: { "X-Meridian-Board": "1" } });

  const blocked = (reason) => {
    const alert = document.createElement("div");
    alert.className = "alert";
    alert.dataset.variant = "destructive";
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
    notice.replaceChildren();
    const id = claim.dataset.claim;
    const params = new URLSearchParams({ to: queue.dataset.queue, view });
    const res = await post(`/admin/queues/claims/${encodeURIComponent(id)}/transfer?${params}`);
    const html = await res.text();
    if (res.status === 409) {
      // Our own server-rendered (autoescaped) partial with the reason.
      notice.innerHTML = html;
      return;
    }
    if (!res.ok) {
      // Anything else (a JSON 404, a proxy page) is shown as text, never as markup.
      blocked(`The move could not be sent (HTTP ${res.status}).`);
      return;
    }
    claim.dataset.inFlight = "true";
    claim.dataset.from = move(claim, queue).dataset.queue;
    const status = claim.querySelector("[data-status]");
    status.innerHTML = html;
    window.htmx.process(status);
  });

  // How long a settled write's badge stays on the card before it goes.
  const BADGE_MS = 4000;

  const fadeOut = (chip) => {
    setTimeout(() => {
      // A later move may have replaced the chip; only clear the one we timed.
      if (chip.isConnected) chip.replaceChildren();
    }, BADGE_MS);
  };

  // When a write settles: unlock the claim, and put a failed move back where
  // ClaimsPro still has it. The chip swaps itself out, so scan the moves in flight.
  document.addEventListener("htmx:afterSettle", () => {
    for (const claim of document.querySelectorAll("[data-in-flight]")) {
      const chip = claim.querySelector("[data-write-status]");
      const state = chip?.dataset.writeStatus;
      if (state !== "confirmed" && state !== "failed") continue;
      delete claim.dataset.inFlight;
      if (state === "failed") {
        const origin = document.querySelector(`[data-queue="${claim.dataset.from}"]`);
        if (origin) move(claim, origin);
        // The badge on the card is brief; the full message stays in the notice.
        const failure = chip.querySelector("[data-failure]");
        if (failure) {
          const copy = failure.cloneNode(true);
          copy.hidden = false;
          notice.replaceChildren(copy);
        }
      }
      fadeOut(chip);
    }
  });

  faultToggle?.addEventListener("change", async () => {
    const params = new URLSearchParams({ on: String(faultToggle.checked), view });
    const res = await post(`/admin/queues/faults?${params}`);
    if (res.ok) faultToggle.checked = (await res.json()).on;
    else faultToggle.checked = !faultToggle.checked;
  });
})();
