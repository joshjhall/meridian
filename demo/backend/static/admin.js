// Admin pipeline monitor (#6): moves claim cards between lanes as SSE frames
// arrive from the replay runner (#5). The server renders each card; this file
// only places it, animating the move with a View Transition where the browser
// supports one. Speed and pause belong to the server's replay, shared by every
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
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  let source = null;
  // Bumped on every clear, so a move queued behind a View Transition from
  // before a reset can't put a stale card back on the board.
  let generation = 0;

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
    const queuedIn = generation;
    if (document.startViewTransition && !reduceMotion.matches && !document.hidden) {
      document.startViewTransition(() => {
        if (queuedIn === generation) place(data);
      });
    } else {
      place(data);
    }
  };

  const unplace = ({ claim_id }) => {
    document.getElementById(`card-${claim_id}`)?.remove();
    recount();
  };

  const counters = ({ counters: c }) => {
    tick(routed, c.routed);
    tick(exceptions, c.exceptions);
  };

  const control = (status) => {
    simNow.textContent = status.sim_now.replace("T", " ").slice(0, 16);
    simNow.dateTime = status.sim_now;
    if (speed) speed.value = String(status.speed);
    if (pause) pause.textContent = status.paused ? "Resume feed" : "Pause feed";
    if (status.paused) setLive("paused", "Paused");
    else if (source?.readyState === EventSource.OPEN) setLive("live", "Live");
  };

  const post = (path, body) =>
    fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

  const clear = () => {
    generation += 1;
    for (const cards of road.querySelectorAll("[data-cards]")) cards.replaceChildren();
    recount();
    tick(routed, 0);
    tick(exceptions, 0);
  };

  const connect = () => {
    clear();
    source = new EventSource(new URL(road.dataset.eventsUrl, window.location.origin));
    source.onopen = () => setLive("live", "Live");
    source.onerror = () => setLive("connecting", "Reconnecting");
    source.addEventListener("claim", (e) => {
      const data = JSON.parse(e.data);
      move(data);
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

  connect();
})();
