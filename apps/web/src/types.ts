export type ApiEnvelope<T> = {
  data: T;
  meta: {
    request_id: string;
    total?: number;
    limit?: number;
    offset?: number;
    [key: string]: unknown;
  };
};

export type Money = {
  currency: string;
  amount_minor: number;
};

export type UserSession = {
  user_id: string;
  organization_id: string;
  email: string;
  name: string;
  roles: string[];
  location_ids: string[];
  department_ids: string[];
};

export type CommandCard = {
  id: string;
  section: string;
  plain_language_issue: string;
  dollar_impact_minor: number;
  location_id: string;
  source: string;
  owner: string;
  recommended_action: string;
  deadline: string;
  rank: number;
  confidence: string;
  actions: string[];
  history: Array<{ at: string; event: string; actor_id?: string }>;
};

export type TimelineStep = {
  step: string;
  status: string;
  record?: { domain: string; id: string } | null;
};

export type UniversalRecord = Record<string, unknown> & {
  id: string;
  organization_id: string;
  location_id?: string;
  department_id?: string;
  version?: number;
  status?: string;
};

export type GlobalIQAnswer = {
  answer: string;
  confidence: string;
  citations: Array<{ domain: string; id: string }>;
  evidence_complete: boolean;
  agent?: string | null;
};
