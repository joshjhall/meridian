import { useEffect, useState } from "react";
import { useParams } from "react-router";

import type { Claim } from "../types";

// Placeholder: the mock ClaimsPro screen is #10.
export default function ClaimsPro() {
  const { claimId } = useParams();
  const [claim, setClaim] = useState<Claim | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setClaim(null);
    setError(null);
    fetch(`/api/claims/${claimId}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setClaim)
      .catch((e: Error) => setError(e.message));
  }, [claimId]);

  return (
    <main>
      <h1>ClaimsPro — {claimId}</h1>
      {error && <p role="alert">Could not load claim: {error}</p>}
      {claim && (
        <p>
          {claim.claim_type} · {claim.state} · ${claim.claim_amount_usd.toLocaleString()} · SLA due{" "}
          {claim.sla_due_at}
        </p>
      )}
    </main>
  );
}
