// Follow the claim in the active tab and show its panel. The panel asks, by
// postMessage, to navigate the ClaimsPro tab when a Contents link is clicked.
const BACKEND = "http://localhost:8000";
const CLAIM_URL = /^http:\/\/localhost:8000\/claimspro\/(IS-CLM-\d{10})/;
const frame = document.getElementById("panel");
let shown = null;

async function follow() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const claimId = tab?.url?.match(CLAIM_URL)?.[1] ?? null;
  if (claimId === shown) return;
  shown = claimId;
  frame.src = claimId ? `${BACKEND}/panel?claim=${claimId}` : `${BACKEND}/panel`;
}

chrome.tabs.onActivated.addListener(follow);
chrome.tabs.onUpdated.addListener((_id, change) => change.url && follow());
follow();

window.addEventListener("message", async (event) => {
  if (event.origin !== BACKEND || event.data?.type !== "navigate") return;
  const { claimId, anchor } = event.data;
  if (!/^IS-CLM-\d{10}$/.test(claimId ?? "")) return;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab) chrome.tabs.update(tab.id, { url: `${BACKEND}/claimspro/${claimId}#${anchor}` });
});
