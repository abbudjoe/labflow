import * as vscode from "vscode";
import { LabFlowApiClient } from "./apiClient";
import { mapApiDiagnostic, MappedDiagnostic } from "./diagnosticMapping";

export class LabFlowDiagnosticsProvider {
  public constructor(
    private readonly collection: vscode.DiagnosticCollection,
    private readonly clientFactory: () => LabFlowApiClient
  ) {}

  public async validateDocument(document: vscode.TextDocument): Promise<MappedDiagnostic[]> {
    if (!isLabFlowWorkflowDocument(document)) {
      return [];
    }
    const response = await this.clientFactory().validateWorkflow(document.getText());
    if (!response.ok || response.data === undefined) {
      this.collection.set(document.uri, []);
      return [];
    }
    const mapped = response.data.diagnostics.map((diagnostic) =>
      mapApiDiagnostic(diagnostic, document.getText())
    );
    this.collection.set(
      document.uri,
      mapped.map((diagnostic) => toVsCodeDiagnostic(diagnostic))
    );
    return mapped;
  }

  public clear(document: vscode.TextDocument): void {
    this.collection.delete(document.uri);
  }
}

export function isLabFlowWorkflowDocument(document: vscode.TextDocument): boolean {
  return (
    document.languageId === "labflow-workflow" ||
    document.fileName.endsWith(".labflow.yaml") ||
    document.fileName.endsWith(".labflow.yml") ||
    document.fileName.endsWith(".workflow.yaml") ||
    document.fileName.endsWith(".workflow.yml")
  );
}

function toVsCodeDiagnostic(mapped: MappedDiagnostic): vscode.Diagnostic {
  const range = new vscode.Range(
    mapped.range.startLine,
    mapped.range.startCharacter,
    mapped.range.endLine,
    mapped.range.endCharacter
  );
  const diagnostic = new vscode.Diagnostic(range, mapped.message, toVsCodeSeverity(mapped.severity));
  diagnostic.code = mapped.code;
  diagnostic.source = "LabFlow";
  return diagnostic;
}

function toVsCodeSeverity(severity: MappedDiagnostic["severity"]): vscode.DiagnosticSeverity {
  switch (severity) {
    case "warning":
      return vscode.DiagnosticSeverity.Warning;
    case "information":
      return vscode.DiagnosticSeverity.Information;
    case "error":
    default:
      return vscode.DiagnosticSeverity.Error;
  }
}
