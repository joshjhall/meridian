import { useSearchParams } from "react-router";

// Placeholder: the side panel is #11.
export default function Panel() {
  const [params] = useSearchParams();
  return (
    <main>
      <h1>Side panel</h1>
      <p>Claim: {params.get("claim") ?? "none selected"}</p>
    </main>
  );
}
