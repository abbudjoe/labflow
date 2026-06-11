export interface LabFlowApiEnvelope<T> {
  ok: boolean;
  trace_id: string;
  data?: T;
  error?: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
}

export interface LabFlowWorkflowDiagnostic {
  code: string;
  message: string;
  severity: string;
  path?: string | null;
  suggested_action?: string | null;
}

export interface LabFlowWorkflowValidationData {
  ok: boolean;
  diagnostics: LabFlowWorkflowDiagnostic[];
}

export interface LabFlowAgentData {
  answer?: string;
  sources?: unknown[];
  tool_calls?: unknown[];
  next_safe_action?: string;
  blocked_reason?: string | null;
}

export interface LabFlowToolExecutionData {
  result?: {
    status?: string;
    errors?: Array<{ code?: string; message?: string; suggested_action?: string | null }>;
    artifacts?: Array<{ artifact_type?: string; name?: string; data?: unknown }>;
  };
}

export class LabFlowApiClient {
  public constructor(private readonly baseUrl: string) {}

  public validateWorkflow(
    workflowYaml: string
  ): Promise<LabFlowApiEnvelope<LabFlowWorkflowValidationData>> {
    return this.post("/workflows/validate", { workflow_yaml: workflowYaml });
  }

  public askAiAboutDiagnostic(
    diagnosticCode: string,
    workflowYaml?: string
  ): Promise<LabFlowApiEnvelope<LabFlowAgentData>> {
    return this.post("/agent/explain-diagnostic", {
      diagnostic_code: diagnosticCode,
      question: `Explain ${diagnosticCode}.`,
      workflow_yaml: workflowYaml
    });
  }

  public explainWorkflow(question: string): Promise<LabFlowApiEnvelope<unknown>> {
    return this.post("/rag/query", { question });
  }

  public generateJanusDryRun(planId: string): Promise<LabFlowApiEnvelope<LabFlowToolExecutionData>> {
    return this.post("/tools/execute", {
      tool_name: "generate_janus_csv",
      mode: "dry_run",
      arguments: {
        plan_id: planId,
        dry_run: true,
        approval_token: null,
        output_dir: null
      }
    });
  }

  public runEvalSuite(): Promise<LabFlowApiEnvelope<unknown>> {
    return this.post("/evals/run", { retrieval_only: true, top_k: 6 });
  }

  public showAuditEvents(): Promise<LabFlowApiEnvelope<unknown>> {
    return this.get("/audit/events");
  }

  private async get<T>(path: string): Promise<LabFlowApiEnvelope<T>> {
    const response = await fetch(this.url(path));
    return this.parseResponse<T>(response);
  }

  private async post<T>(path: string, body: unknown): Promise<LabFlowApiEnvelope<T>> {
    const response = await fetch(this.url(path), {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body)
    });
    return this.parseResponse<T>(response);
  }

  private async parseResponse<T>(response: Response): Promise<LabFlowApiEnvelope<T>> {
    const payload = (await response.json()) as LabFlowApiEnvelope<T>;
    if (!response.ok && payload.error === undefined) {
      return {
        ok: false,
        trace_id: "trace_unavailable",
        error: {
          code: `HTTP_${response.status}`,
          message: response.statusText,
          details: {}
        }
      };
    }
    return payload;
  }

  private url(path: string): string {
    return `${this.baseUrl.replace(/\/$/, "")}${path}`;
  }
}
