import * as vscode from "vscode";
import {
  LabFlowAgentData,
  LabFlowApiClient,
  LabFlowApiEnvelope,
  LabFlowToolExecutionData
} from "./apiClient";
import { LabFlowDiagnosticsProvider } from "./diagnostics";
import { LabFlowHoverProvider } from "./hoverDocs";

const OUTPUT_CHANNEL_NAME = "LabFlow AI Studio";

export function activate(context: vscode.ExtensionContext): void {
  const output = vscode.window.createOutputChannel(OUTPUT_CHANNEL_NAME);
  const clientFactory = (): LabFlowApiClient => new LabFlowApiClient(apiUrl());
  const diagnosticCollection = vscode.languages.createDiagnosticCollection("labflow");
  const diagnostics = new LabFlowDiagnosticsProvider(diagnosticCollection, clientFactory);
  const selector: vscode.DocumentSelector = { language: "labflow-workflow", scheme: "file" };

  context.subscriptions.push(
    output,
    diagnosticCollection,
    vscode.languages.registerHoverProvider(selector, new LabFlowHoverProvider()),
    vscode.workspace.onDidOpenTextDocument((document) => {
      void diagnostics.validateDocument(document);
    }),
    vscode.workspace.onDidSaveTextDocument((document) => {
      void diagnostics.validateDocument(document);
    }),
    vscode.workspace.onDidCloseTextDocument((document) => {
      diagnostics.clear(document);
    }),
    vscode.window.onDidChangeActiveTextEditor((editor) => {
      if (editor !== undefined) {
        void diagnostics.validateDocument(editor.document);
      }
    }),
    vscode.commands.registerCommand("labflow.validateWorkflow", async () => {
      const document = activeDocument();
      if (document === undefined) {
        return;
      }
      await runCommand(output, "Validate Workflow", async () => {
        const mapped = await diagnostics.validateDocument(document);
        return {
          ok: true,
          trace_id: "trace_vscode_diagnostics",
          data: {
            diagnostics: mapped,
            count: mapped.length
          }
        };
      });
    }),
    vscode.commands.registerCommand("labflow.askAiAboutDiagnostic", async () => {
      const diagnosticCode = await selectedDiagnosticCode();
      if (!diagnosticCode) {
        return;
      }
      await runCommand(output, "Ask AI About Diagnostic", () =>
        clientFactory().askAiAboutDiagnostic(diagnosticCode, activeDocumentText(false))
      );
    }),
    vscode.commands.registerCommand("labflow.explainWorkflow", async () => {
      const question =
        (await vscode.window.showInputBox({
          prompt: "Question for the LabFlow knowledge corpus",
          placeHolder: "Why is this workflow not robot-ready?"
        })) ?? "Explain this LabFlow workflow.";
      await runCommand(output, "Explain Workflow", () => clientFactory().explainWorkflow(question));
    }),
    vscode.commands.registerCommand("labflow.generateJanusDryRun", async () => {
      const planId = await vscode.window.showInputBox({
        prompt: "Normalization config path for JANUS dry-run",
        placeHolder: "examples/configs/normalization.yaml"
      });
      if (!planId) {
        return;
      }
      await runCommand(output, "Generate JANUS Worklist Dry Run", () =>
        clientFactory().generateJanusDryRun(planId)
      );
    }),
    vscode.commands.registerCommand("labflow.runEvalSuite", async () => {
      await runCommand(output, "Run Eval Suite", () => clientFactory().runEvalSuite());
    }),
    vscode.commands.registerCommand("labflow.showAuditEvents", async () => {
      await runCommand(output, "Show Audit Events", () => clientFactory().showAuditEvents());
    })
  );

  if (vscode.window.activeTextEditor !== undefined) {
    void diagnostics.validateDocument(vscode.window.activeTextEditor.document);
  }
}

export function deactivate(): void {}

function apiUrl(): string {
  return vscode.workspace
    .getConfiguration("labflow")
    .get<string>("apiUrl", "http://127.0.0.1:8000");
}

function activeDocument(): vscode.TextDocument | undefined {
  const editor = vscode.window.activeTextEditor;
  if (editor === undefined) {
    void vscode.window.showWarningMessage("Open a LabFlow workflow YAML file first.");
    return undefined;
  }
  return editor.document;
}

function activeDocumentText(showWarning = true): string | undefined {
  const editor = vscode.window.activeTextEditor;
  if (editor === undefined) {
    if (showWarning) {
      void vscode.window.showWarningMessage("Open a LabFlow workflow YAML file first.");
    }
    return undefined;
  }
  return editor.document.getText();
}

async function runCommand<T>(
  output: vscode.OutputChannel,
  title: string,
  callApi: () => Promise<LabFlowApiEnvelope<T>>
): Promise<void> {
  output.show(true);
  output.appendLine(`\n## ${title}`);
  try {
    const response = await callApi();
    output.appendLine(formatCommandResponse(response));
    if (!response.ok) {
      void vscode.window.showWarningMessage(
        `LabFlow API returned ${response.error?.code ?? "an error"}.`
      );
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    output.appendLine(`API request failed: ${message}`);
    void vscode.window.showErrorMessage(`LabFlow API request failed: ${message}`);
  }
}

async function selectedDiagnosticCode(): Promise<string | undefined> {
  const editor = vscode.window.activeTextEditor;
  if (editor !== undefined) {
    const diagnostics = vscode.languages
      .getDiagnostics(editor.document.uri)
      .filter((diagnostic) => diagnostic.source === "LabFlow");
    const selected = diagnostics.find((diagnostic) =>
      diagnostic.range.contains(editor.selection.active)
    ) ?? diagnostics[0];
    if (selected?.code !== undefined) {
      return String(selected.code);
    }
  }
  return vscode.window.showInputBox({
    prompt: "Diagnostic code",
    placeHolder: "MISSING_CONCENTRATION"
  });
}

function formatCommandResponse<T>(response: LabFlowApiEnvelope<T>): string {
  if (!response.ok) {
    return JSON.stringify(response, null, 2);
  }
  if (isAgentData(response.data)) {
    return formatAgentData(response.data);
  }
  if (isToolExecutionData(response.data)) {
    return formatToolExecutionData(response.data);
  }
  return JSON.stringify(response, null, 2);
}

function formatAgentData(data: LabFlowAgentData): string {
  const lines = ["Answer:", data.answer ?? "(no answer)", ""];
  if (data.sources !== undefined) {
    lines.push("Sources:", JSON.stringify(data.sources, null, 2), "");
  }
  if (data.tool_calls !== undefined) {
    lines.push("Tool calls:", JSON.stringify(data.tool_calls, null, 2), "");
  }
  if (data.next_safe_action !== undefined) {
    lines.push("Next safe action:", data.next_safe_action, "");
  }
  if (data.blocked_reason) {
    lines.push("Blocked reason:", data.blocked_reason, "");
  }
  return lines.join("\n");
}

function formatToolExecutionData(data: LabFlowToolExecutionData): string {
  const result = data.result;
  if (result === undefined) {
    return JSON.stringify(data, null, 2);
  }
  const lines = [`Status: ${result.status ?? "unknown"}`];
  if (result.errors !== undefined && result.errors.length > 0) {
    lines.push("", "Blocked reason:");
    for (const error of result.errors) {
      lines.push(`- ${error.code ?? "ERROR"}: ${error.message ?? ""}`);
      if (error.suggested_action) {
        lines.push(`  Suggested action: ${error.suggested_action}`);
      }
    }
  }
  if (result.artifacts !== undefined && result.artifacts.length > 0) {
    lines.push("", "Artifact preview:");
    for (const artifact of result.artifacts) {
      lines.push(`- ${artifact.artifact_type ?? "artifact"} (${artifact.name ?? "unnamed"})`);
      lines.push(JSON.stringify(artifact.data, null, 2));
    }
  }
  return lines.join("\n");
}

function isAgentData(value: unknown): value is LabFlowAgentData {
  return typeof value === "object" && value !== null && "answer" in value;
}

function isToolExecutionData(value: unknown): value is LabFlowToolExecutionData {
  return typeof value === "object" && value !== null && "result" in value;
}
