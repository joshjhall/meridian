# Decisions log

Append-only. Add new entries at the end; do not edit or remove prior entries.

1. **(W1 Mon)** The week-2 workshop will open on a working demo rather than a deck. Laura: "show, don't tell."
2. **(W1 Tue)** Discovery prototypes use read-only ClaimsPro REST access plus the reference extract; no writes to client systems during discovery.
3. **(W1 Tue)** The 5,000-claim Snowflake extract and analytics memo provided by Michael's team (masked on policyholder fields) are the shared working dataset for discovery.
4. **(W1 Thu)** No client PII in LLM prompts during discovery, per Michael's data-handling guidance.
5. **(W1 Thu)** Both approved LLM providers are acceptable for prototyping; production provider choice is deferred to delivery.
6. **(W1 Fri)** Laura sends a Friday end-of-week email to Carlos, Sandra, and Michael for the remainder of the engagement.
7. **(W1 Fri)** The demo is all Python: FastAPI serves the JSON API and the server-rendered pages (Jinja2 + HTMX), LangGraph runs the pipeline, and D3 (from a CDN) draws the charts. The Chrome extension is a thin MV3 shell that embeds the backend's `/panel` page. Why: Meridian's ML platform is Databricks with MLflow, which can trace and log LangGraph graphs, so the demo pipeline matches the production path Michael's team would take; LangGraph's Python library is its primary implementation; and one language gives one schema (the Pydantic models) instead of a hand-mirrored TypeScript copy. Replaces the React/Vite/TypeScript frontend first set in issue #1.
