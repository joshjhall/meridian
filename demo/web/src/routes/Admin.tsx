import { Stage } from "../types";

// Placeholder: the pipeline monitor is #6.
export default function Admin() {
  return (
    <main>
      <h1>Admin monitor</h1>
      <p>Stages: {Object.values(Stage).join(" → ")}</p>
    </main>
  );
}
