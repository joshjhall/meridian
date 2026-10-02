// Mirror of demo/backend/models.py (the source of truth). Keep field-for-field
// in sync; demo/backend/tests/test_types_parity.py enforces it.
//
// Skill, Tier and Stage are enums: iterate them (Object.values) rather than
// listing members, so adding a tier means editing models.py and this file only.

export const SLA_HOURS = 24;

export enum Skill {
  Collision = "Collision",
  Comprehensive = "Comprehensive",
  BodilyInjury = "Bodily Injury",
  PropertyDamage = "Property Damage",
  Liability = "Liability",
}

export enum Tier {
  T1 = "T1",
  T2 = "T2",
  T3 = "T3",
}

export const TIER_LABELS: Record<Tier, string> = {
  [Tier.T1]: "standard",
  [Tier.T2]: "involved",
  [Tier.T3]: "senior",
};

export enum Stage {
  Received = "received",
  Validated = "validated",
  Enriched = "enriched",
  Prioritized = "prioritized",
  Assigned = "assigned",
  WithAdjuster = "with_adjuster",
  Exception = "exception",
}

export type YesNo = "Yes" | "No";
export type IntakeChannel = "E-Portal" | "Phone" | "Fax/EDI";
export type Complexity = "Simple" | "Moderate" | "Complex";
export type Disposition = "Paid in Full" | "Partial Payment" | "Denied" | "Settled" | "Pending Review";
export type ReviewLane = "fast_lane" | "standard_review" | "regulatory_review" | "senior_review";
export type BriefStatus = "pending" | "ready" | "failed";
export type AdjusterRole = "adjuster" | "senior" | "lead";

/** ISO 8601 datetime string. */
export type DateTime = string;
/** ISO 8601 date string (YYYY-MM-DD). */
export type DateString = string;

export interface Claim {
  // Extract columns, in reference/data_dictionary.md order.
  claim_id: string;
  filed_date: DateString;
  claim_type: Skill;
  state: string;
  intake_channel: IntakeChannel;
  cost_per_claim_usd: number;
  claim_amount_usd: number;
  complexity: Complexity;
  automation_eligibility_score: number;
  flagged_for_human_review: YesNo;
  requires_human_by_regulation: YesNo;
  queue_wait_hours: number;
  handling_hours: number;
  total_cycle_time_hours: number;
  disposition: Disposition;
  denial_reason: string | null;
  adjuster_id: string;
  document_count: number;
  customer_satisfaction_1to5: number | null;
  review_actually_needed: YesNo | null;

  // Demo provenance.
  received_at: DateTime;
  synthetic: boolean;
  sources: string[];
  details: Record<string, unknown>;

  // ClaimsPro custom fields, filled by the pre-processing pipeline (#3).
  skills: Skill[];
  tier: Tier | null;
  routing_reason: string | null;
  review_lane: ReviewLane | null;
  brief_status: BriefStatus | null;
  /** received_at + 24h, computed server-side. */
  sla_due_at: DateTime;
}

export interface FixtureExpectation {
  skills: Skill[];
  tier: Tier;
  regulated: boolean;
  routing_reason: string;
  sla_in_demo: "on_track" | "at_risk" | "breached";
}

export interface ClaimFixture {
  claim: Claim;
  expected: FixtureExpectation;
}

export interface Adjuster {
  id: string;
  name: string;
  skills: Skill[];
  tiers: Tier[];
  role: AdjusterRole;
  current_load: number;
  extract_code: boolean;
}

export interface PipelineEvent {
  claim_id: string;
  stage: Stage;
  timestamp: DateTime;
  payload: Record<string, unknown>;
  pipeline_version: string;
}

export interface ReviewInterval {
  actor: string;
  start: DateTime;
  end: DateTime | null;
}

export interface AuditRecord {
  // The five fields the compliance floor requires.
  claim_id: string;
  input_data_ref: string;
  model_version: string;
  output: Record<string, unknown>;
  confidence: number;
  human_reviewed: boolean;
  // Beyond the floor.
  rationale: string;
  skills: Skill[];
  tier: Tier | null;
  review_intervals: ReviewInterval[];
}

// Panel summary: the six sections in docs/presentation/panel_examples.md.

export interface SourceRef {
  label: string;
  path: string;
  anchor: string | null;
  verified: boolean;
}

export interface PanelHeader {
  claim_id: string;
  skills: Skill[];
  tier: Tier;
  sla_due_at: DateTime;
  regulated: boolean;
  routing_reason: string;
}

export interface WhatMattersPoint {
  text: string;
  unusual: boolean;
  source: SourceRef;
}

export interface KeyFact {
  label: string;
  value: string;
  sources: SourceRef[];
}

export interface KeyFacts {
  template: Skill;
  facts: KeyFact[];
  collapsed: boolean;
}

export interface AttentionItem {
  kind: "missing" | "conflict" | "low_confidence";
  label: string;
  sources: SourceRef[];
  values: string[];
  suggested: string | null;
}

export interface ContentsEntry {
  fact: string;
  location: SourceRef;
}

export interface FooterTouch {
  actor: string;
  at: DateTime;
}

export interface PanelFooter {
  touches: FooterTouch[];
  pipeline_version: string;
}

export interface PanelSummary {
  header: PanelHeader;
  what_matters: WhatMattersPoint[];
  key_facts: KeyFacts;
  needs_attention: AttentionItem[];
  contents: ContentsEntry[];
  footer: PanelFooter;
}
