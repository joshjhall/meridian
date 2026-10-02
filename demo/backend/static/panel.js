// Side panel (#11): Contents and source links navigate the ClaimsPro tab, never
// the panel. Inside a frame (the extension shell or the docked fallback) the
// panel asks its host to navigate; opened on its own, the link works as a link.
document.addEventListener("click", (event) => {
  const link = event.target.closest("a[data-nav]");
  if (!link || window.parent === window) return;
  event.preventDefault();
  const claimId = document.querySelector(".sheet")?.dataset.claim;
  window.parent.postMessage({ type: "navigate", claimId, anchor: link.dataset.nav }, "*");
});
