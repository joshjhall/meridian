// Admin pipeline monitor (#6): moves claim cards between lanes as SSE frames
// arrive. The server renders each card; this file only places it, animating the
// move with a View Transition where the browser supports one.

(() => {
  const road = document.getElementById("road");
  if (!road) return;

  const live = document.getElementById("live");
  const routed = document.getElementById("count-routed");
  const exceptions = document.getElementById("count-exceptions");
  const speed = document.getElementById("speed");
  const pause = document.getElementById("pause");
  const trace = document.getElementById("trace");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  let source = null;

  const lane = (stage) => road.querySelector(`[data-lane="${stage}"] [data-cards]`);

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

  const place = ({ claim_id, stage, html }) => {
    // html is our own server-rendered (autoescaped) card, like any htmx swap.
    const template = document.createElement("template");
    template.innerHTML = html.trim();
    const card = template.content.firstElementChild;
    const target = lane(stage);
    // An unknown stage leaves the card where it was rather than dropping it.
    if (!card || !target) return;
    // Same name before and after the move, so the browser animates it across lanes.
    card.style.viewTransitionName = `claim-${claim_id}`;
    document.getElementById(`card-${claim_id}`)?.remove();
    // Demo claims stay at the top of a lane so they're easy to follow.
    if (card.classList.contains("claim--pinned")) target.prepend(card);
    else target.append(card);
    window.htmx?.process(card);
    recount();
  };

  const move = (data) => {
    if (document.startViewTransition && !reduceMotion.matches && !document.hidden) {
      document.startViewTransition(() => place(data));
    } else {
      place(data);
    }
  };

  const clear = () => {
    for (const cards of road.querySelectorAll("[data-cards]")) cards.replaceChildren();
    recount();
    tick(routed, 0);
    tick(exceptions, 0);
  };

  const connect = () => {
    const url = new URL(road.dataset.eventsUrl, window.location.origin);
    if (speed) url.searchParams.set("speed", speed.value);
    clear();
    source = new EventSource(url);
    source.onopen = () => setLive("live", "Live");
    source.onerror = () => setLive("connecting", "Reconnecting");
    source.addEventListener("claim", (e) => {
      const data = JSON.parse(e.data);
      move(data);
      tick(routed, data.counters.routed);
      tick(exceptions, data.counters.exceptions);
    });
    source.addEventListener("reset", clear);
  };

  const disconnect = () => {
    source?.close();
    source = null;
  };

  // A paused feed stays paused; connect() reads the new speed on restart.
  speed?.addEventListener("change", () => {
    if (!source) return;
    disconnect();
    connect();
  });

  pause?.addEventListener("click", () => {
    if (source) {
      disconnect();
      setLive("paused", "Paused");
      pause.textContent = "Restart feed";
    } else {
      connect();
      pause.textContent = "Pause feed";
    }
  });

  // Cards load their trace with hx-get into the dialog; open it once it arrives.
  document.body.addEventListener("htmx:afterSwap", (e) => {
    if (e.detail.target.id === "trace-body" && !trace.open) trace.showModal();
  });

  connect();
})();
