// Admin pipeline monitor (#6): moves claim cards between lanes as SSE frames
// arrive from the replay runner (#5). The server renders each card; this file
// only places it, sliding the card from its old spot (FLIP, Web Animations).
// Not View Transitions: the replay moves cards many times a second, and a page
// mid-transition is a snapshot that swallows clicks, so the controls went dead. Speed and pause belong to the server's replay, shared by every
// viewer, so the controls post to it and the page follows its `control` frames.

(() => {
  const road = document.getElementById("road");
  if (!road) return;

  const live = document.getElementById("live");
  const routed = document.getElementById("count-routed");
  const exceptions = document.getElementById("count-exceptions");
  const speed = document.getElementById("speed");
  const pause = document.getElementById("pause");
  const restart = document.getElementById("restart");
  const simNow = document.getElementById("sim-now");
  const trace = document.getElementById("trace");
  const RETRY_MS = 5000; // matches the feed's Retry-After when it is over the viewer cap
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  let source = null;

  const lane = (stage) => road.querySelector(`[data-lane="${stage}"] [data-cards]`);

  // Lanes in pipeline order; exception is last, a claim can stop there from any stage.
  const ORDER = [...road.querySelectorAll("[data-lane]")].map((s) => s.dataset.lane);
  // A card never steps back: a frame older than the card's stage is stale (a
  // held frame released late, or one delivered out of order) and is dropped.
  // Without this, cards stuck in an earlier lane, usually "prioritizing".
  const stale = (old, stage) => old && ORDER.indexOf(stage) < ORDER.indexOf(old.dataset.stage);

  const setLive = (state, text) => {
    live.dataset.state = state;
    live.textContent = text;
  };

  const tick = (el, value) => {
    if (el.textContent === String(value)) return;
    el.textContent = value;
    el.classList.remove("tick");
    void el.offsetWidth; // restart the animation
    el.classList.add("tick");
  };

  const recount = () => {
    for (const section of road.querySelectorAll("[data-lane]")) {
      section.querySelector("[data-count]").textContent = section.querySelectorAll(".claim").length;
    }
  };

  // Frames for a lane under the pointer wait here, newest per claim, and apply
  // when the pointer leaves. Cards shuffling under the cursor made it flicker
  // between hand and arrow and moved click targets mid-click.
  const held = new Map();
  let hovered = null;

  const place = (data) => {
    const { claim_id, stage, html } = data;
    const target = lane(stage);
    const old = document.getElementById(`card-${claim_id}`);
    if (stale(old, stage)) return;
    const fromLane = old?.closest("[data-lane]");
    if (hovered && (target?.closest("[data-lane]") === hovered || fromLane === hovered)) {
      held.set(claim_id, data);
      return;
    }
    // html is our own server-rendered (autoescaped) card, like any htmx swap.
    const template = document.createElement("template");
    template.innerHTML = html.trim();
    const card = template.content.firstElementChild;
    // An unknown stage leaves the card where it was rather than dropping it.
    if (!card || !target) return;
    // Same lane: swap the card where it stands, so nothing below it reflows.
    if (old && old.parentElement === target) {
      old.replaceWith(card);
      window.htmx?.process(card);
      return;
    }
    const from = old?.getBoundingClientRect();
    old?.remove();
    // Demo claims stay at the top of a lane so they're easy to follow; the lead
    // demo claim (data-lead) stays above them, so it is always the first card.
    const lead = target.querySelector("[data-lead]");
    if (card.dataset.lead !== undefined) target.prepend(card);
    else if (card.classList.contains("claim--pinned")) {
      if (lead) lead.after(card);
      else target.prepend(card);
    } else target.append(card);
    window.htmx?.process(card);
    recount();
    if (!from || reduceMotion.matches || document.hidden) return;
    const to = card.getBoundingClientRect();
    const dx = from.left - to.left;
    const dy = from.top - to.top;
    if (!dx && !dy) return;
    card.animate([{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "none" }], {
      duration: 450,
      easing: "cubic-bezier(0.3, 0.7, 0.2, 1)",
    });
  };

  const unplace = (data) => {
    const old = document.getElementById(`card-${data.claim_id}`);
    if (hovered && old?.closest("[data-lane]") === hovered) {
      held.set(data.claim_id, { ...data, removed: true });
      return;
    }
    old?.remove();
    recount();
  };

  const release = () => {
    hovered = null;
    const pending = [...held.values()];
    held.clear();
    for (const data of pending) (data.removed ? unplace : place)(data);
  };

  for (const section of road.querySelectorAll("[data-lane]")) {
    section.addEventListener("pointerenter", () => {
      hovered = section;
    });
    section.addEventListener("pointerleave", release);
  }

  const counters = ({ counters: c }) => {
    tick(routed, c.routed);
    tick(exceptions, c.exceptions);
  };

  const control = (status) => {
    simNow.textContent = status.sim_now.replace("T", " ").slice(0, 16);
    simNow.dateTime = status.sim_now;
    if (speed) {
      // Show the nearest named speed, so a value set elsewhere never blanks the select.
      const nearest = [...speed.options].reduce((a, b) =>
        Math.abs(b.value - status.speed) < Math.abs(a.value - status.speed) ? b : a,
      );
      speed.value = nearest.value;
    }
    if (pause) pause.textContent = status.paused ? "Resume feed" : "Pause feed";
    if (status.paused) setLive("paused", "Paused");
    else if (source?.readyState === EventSource.OPEN) setLive("live", "Live");
  };

  // Controls render only in the admin view; the header is the board's CSRF guard.
  const post = (path, body) =>
    fetch(`${path}?view=admin`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Meridian-Board": "1" },
      body: JSON.stringify(body),
    });

  const clear = () => {
    held.clear();
    for (const cards of road.querySelectorAll("[data-cards]")) cards.replaceChildren();
    recount();
    tick(routed, 0);
    tick(exceptions, 0);
  };

  const connect = () => {
    clear();
    source = new EventSource(new URL(road.dataset.eventsUrl, window.location.origin));
    source.onopen = () => setLive("live", "Live");
    source.onerror = () => {
      setLive("connecting", "Reconnecting");
      // The browser retries a dropped stream itself, but a refusal (503 over the
      // viewer cap) closes the source for good, so try again from here.
      if (source.readyState === EventSource.CLOSED) setTimeout(connect, RETRY_MS);
    };
    source.addEventListener("claim", (e) => {
      const data = JSON.parse(e.data);
      place(data);
      counters(data);
    });
    source.addEventListener("remove", (e) => {
      const data = JSON.parse(e.data);
      unplace(data);
      counters(data);
    });
    source.addEventListener("control", (e) => control(JSON.parse(e.data)));
    source.addEventListener("reset", clear);
  };

  speed?.addEventListener("change", () => post("/api/replay", { speed: Number(speed.value) }));
  pause?.addEventListener("click", () =>
    post("/api/replay", { paused: pause.textContent.startsWith("Pause") }),
  );
  restart?.addEventListener("click", () => post("/api/replay/restart", {}));

  // Cards load their trace with hx-get into the dialog; open it once it arrives.
  document.body.addEventListener("htmx:afterSwap", (e) => {
    if (e.detail.target.id === "trace-body" && !trace.open) trace.showModal();
  });

  // Demo cards load their audit record (#9) the same way, into the side drawer.
  const audit = document.getElementById("audit");
  document.body.addEventListener("htmx:afterSwap", (e) => {
    if (e.detail.target.id === "audit-body" && !audit.open) audit.showModal();
  });

  connect();
})();
