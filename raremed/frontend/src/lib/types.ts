export type LocaleCode = "en" | "fr" | "ar" | "ary";

export type DependencyStatus = {
  status: "ok" | "unavailable";
  detail: string | null;
};

export type PlatformStatus = {
  service: string;
  version: string;
  api_version: string;
  environment: string;
  decision_support_notice: string;
  database: DependencyStatus;
  neo4j: DependencyStatus;
  ollama: {
    status: string;
    base_url: string;
    detail: string | null;
    models: string[];
    configured_model?: string;
    model_ready?: boolean;
    think?: boolean;
  };
  datasets: {
    readable: boolean;
    total_files: number;
    sources_with_files: string[];
  };
  clinical_reasoning_enabled: boolean;
};

export type DiscoveredFile = {
  name: string;
  relative_path: string;
  size_bytes: number;
  suffix: string;
};

export type SourceDiscovery = {
  source: string;
  relative_directory: string;
  present: boolean;
  file_count: number;
  truncated: boolean;
  files: DiscoveredFile[];
};

export type DiscoveryReport = {
  readable: boolean;
  note: string;
  sources: SourceDiscovery[];
  sample_files: string[];
  reserved_directories: { name: string; present: boolean; purpose: string }[];
};

export type UiFixture = {
  id: string;
  locale: string;
  text: string;
  notice: string;
};

export type GraphStatus = {
  connection: DependencyStatus;
  loaded: boolean;
  note: string;
  run_id?: string | null;
  dataset_run_id?: string | null;
  node_counts?: Record<string, number>;
  relationship_counts?: Record<string, number>;
  evidence_count?: number;
  inferred_relationship_count?: number;
  running?: boolean;
};

export type GraphSearchHit = {
  curie: string;
  kind: string;
  label: string | null;
  score: number;
};

export type GraphNodeRead = {
  curie: string;
  kind: string;
  label: string | null;
  definition?: string | null;
  synonyms?: string[];
  namespace?: string | null;
  source?: string | null;
  source_version?: string | null;
  obsolete?: boolean;
  properties?: Record<string, unknown>;
};

export type GraphEdgeRead = {
  id: string;
  type: string;
  start: string;
  end: string;
  inferred: boolean;
  polarity?: string | null;
  frequency?: string | null;
  frequency_normalized?: string | null;
  evidence?: string | null;
  source?: string | null;
  source_file?: string | null;
  source_version?: string | null;
  source_record_id?: string | null;
  properties?: Record<string, unknown>;
};

export type GraphEvidenceRead = {
  id: string;
  subject: string;
  object: string;
  rel_type: string;
  inferred: boolean;
  source?: string | null;
  source_file?: string | null;
  source_version?: string | null;
  source_release_date?: string | null;
  source_record_id?: string | null;
  evidence?: string | null;
  polarity?: string | null;
  frequency?: string | null;
};

export type DiseaseDetail = {
  disease: GraphNodeRead;
  phenotypes: GraphEdgeRead[];
  genes: GraphEdgeRead[];
  inheritance: GraphEdgeRead[];
  tests?: GraphEdgeRead[];
  xrefs?: GraphEdgeRead[];
};

export type NeighborhoodRead = {
  center: GraphNodeRead;
  nodes: GraphNodeRead[];
  edges: GraphEdgeRead[];
  depth: number;
  bounded: boolean;
  truncated?: boolean;
  read_only?: boolean;
};

export type GraphSearchPage = {
  items: GraphSearchHit[];
  offset: number;
  limit: number;
  has_more: boolean;
};

export type GraphSliceRead = {
  nodes: GraphNodeRead[];
  edges: GraphEdgeRead[];
  truncated: boolean;
  read_only?: boolean;
};

export type SourceFacetRead = {
  name: string;
  version: string | null;
  node_count: number;
};

export type EntityDetail = {
  entity: GraphNodeRead;
  relationships: GraphEdgeRead[];
  evidence: GraphEvidenceRead[];
  read_only?: boolean;
};

export type UserRole = "user" | "clinician" | "admin";

export type SessionUser = {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
};

export type ChatMessage = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system" | string;
  content: string;
  status?: "complete" | "interrupted" | "generating" | string;
  extra?: {
    medical_evidence?: unknown[];
    hpo_entities?: unknown[];
    diagnostic_session_id?: string | null;
    model?: string;
    stopped?: boolean;
  };
  created_at: string;
};

export type ConversationSummary = {
  id: string;
  title: string;
  title_source?: string;
  locale: string;
  archived?: boolean;
  created_at: string;
  updated_at: string;
  message_count: number;
  preview: string | null;
};

export type ConversationList = {
  items: ConversationSummary[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
};

export type ConversationDetail = {
  id: string;
  title: string;
  title_source?: string;
  locale: string;
  archived?: boolean;
  created_at: string;
  updated_at: string;
  messages: ChatMessage[];
  has_more?: boolean;
};

export type MessageExchange = {
  user_message: ChatMessage;
  assistant_message: ChatMessage;
};

export type ChatDone = {
  model: string;
  provider: string;
  elapsed_ms: number;
  eval_count: number | null;
  tokens_per_second: number | null;
  stopped: boolean;
  saved: boolean;
  think: boolean;
  conversation_id?: string | null;
  title?: string | null;
};

export type SourceImportRow = {
  source: string;
  role: string;
  file_path: string | null;
  expected_path?: string | null;
  version: string | null;
  release_date: string | null;
  import_status: string;
  entity_counts: Record<string, number>;
  relationship_counts: Record<string, number>;
  validation_warnings: string[];
  last_successful_import: string | null;
  required?: boolean;
  schema_name?: string | null;
};

export type IngestionRunSummary = {
  run_id: string;
  status: string;
  trigger?: string | null;
  created_at?: string | null;
  finished_at?: string | null;
  entity_count: number;
  relationship_count: number;
  warning_count: number;
  missing_required: string[];
  error_message?: string | null;
};

export type IngestionStatus = {
  running: boolean;
  current_run: IngestionRunSummary | null;
  last_successful_import: string | null;
  missing_required: string[];
  sources: SourceImportRow[];
  history: IngestionRunSummary[];
  counts: Record<string, unknown>;
  note: string;
};

export type ModelIndicator = {
  provider: string;
  model: string;
  base_url: string;
  reachable: boolean;
  model_ready: boolean;
  think: boolean;
  installed_models: string[];
  detail: string | null;
};
