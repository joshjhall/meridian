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
