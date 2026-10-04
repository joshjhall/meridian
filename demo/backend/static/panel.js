// Side panel (#11): Contents and source links navigate the ClaimsPro tab, never
// the panel. Inside one of our two hosts (the extension shell, or the docked
// mock page on this origin) the panel asks the host to navigate; anywhere else
// the link works as an ordinary link and no claim ID leaves the page.
const ancestor = location.ancestorOrigins?.[0] ?? "";
const host =
  ancestor === location.origin || ancestor.startsWith("chrome-extension://") ? ancestor : null;

document.addEventListener("click", (event) => {
  const link = event.target.closest("a[data-nav]");
  if (!link || !host || window.parent === window) return;
  event.preventDefault();
  const claimId = document.querySelector(".sheet")?.dataset.claim;
  window.parent.postMessage({ type: "navigate", claimId, anchor: link.dataset.nav }, host);
});

// "Needs attention" (#11): Correct opens an inline field on the card; Cancel puts
// the buttons back. Confirm and Save are htmx posts that replace the card with a
// done state (panel/_resolved.html), removed here once its bar has drained.
const card = (el) => el.closest(".item");

const showCorrect = (item, open) => {
  item.querySelector("[data-actions]").hidden = open;
  item.querySelector("[data-correct]").hidden = !open;
  if (open) item.querySelector("[data-correct-input]").select();
};

document.addEventListener("click", (event) => {
  const open = event.target.closest("[data-open-correct]");
  if (open) showCorrect(card(open), true);
  const cancel = event.target.closest("[data-cancel-correct]");
  if (cancel) showCorrect(card(cancel), false);
});

// Enter saves, Escape cancels, as in any inline edit.
document.addEventListener("keydown", (event) => {
  const input = event.target.closest?.("[data-correct-input]");
  if (!input) return;
  if (event.key === "Enter") {
    event.preventDefault();
    card(input).querySelector("[data-save-correct]").click();
  } else if (event.key === "Escape") {
    showCorrect(card(input), false);
  }
});

// Save sends the typed value as the log's note, a query parameter like the rest.
// An empty value isn't sent: the server would refuse it, so ask for one instead.
document.addEventListener("htmx:configRequest", (event) => {
  const save = event.detail.elt.closest?.("[data-save-correct]");
  if (!save) return;
  const input = card(save).querySelector("[data-correct-input]");
  const value = input.value.trim();
  if (!value) {
    event.preventDefault();
    input.focus();
    return;
  }
  const url = new URL(event.detail.path, location.origin);
  url.searchParams.set("note", value);
  event.detail.path = url.pathname + url.search;
});

// A resolved card goes when its bar ends; the count follows, and the section goes
// with its last card.
document.addEventListener("animationend", (event) => {
  if (!event.target.matches?.(".item__bar")) return;
  const done = event.target.closest("[data-resolved]");
  const section = done?.closest("#needs-attention");
  done?.remove();
  if (!section) return;
  const left = section.querySelectorAll(".item").length;
  if (left) section.querySelector(".count").textContent = String(left);
  else section.remove();
});
