import { LabFlowWorkflowDiagnostic } from "./apiClient";

export interface DiagnosticRange {
  startLine: number;
  startCharacter: number;
  endLine: number;
  endCharacter: number;
}

export interface MappedDiagnostic {
  code: string;
  message: string;
  severity: "error" | "warning" | "information";
  path?: string | null;
  suggestedAction?: string | null;
  range: DiagnosticRange;
}

const SEVERITY_MAP = new Map<string, "error" | "warning" | "information">([
  ["error", "error"],
  ["blocking", "error"],
  ["warning", "warning"],
  ["info", "information"],
  ["information", "information"]
]);

export function mapApiDiagnostic(
  diagnostic: LabFlowWorkflowDiagnostic,
  workflowText: string
): MappedDiagnostic {
  return {
    code: diagnostic.code,
    message: diagnostic.suggested_action
      ? `${diagnostic.message} Suggested action: ${diagnostic.suggested_action}`
      : diagnostic.message,
    severity: SEVERITY_MAP.get(diagnostic.severity.toLowerCase()) ?? "error",
    path: diagnostic.path,
    suggestedAction: diagnostic.suggested_action,
    range: rangeForPath(workflowText, diagnostic.path)
  };
}

export function rangeForPath(workflowText: string, diagnosticPath?: string | null): DiagnosticRange {
  const lines = workflowText.split(/\r?\n/);
  const key = firstPathSegment(diagnosticPath);
  if (key !== undefined) {
    const lineIndex = lines.findIndex((line) => line.trimStart().startsWith(`${key}:`));
    if (lineIndex >= 0) {
      return {
        startLine: lineIndex,
        startCharacter: indentation(lines[lineIndex]),
        endLine: lineIndex,
        endCharacter: Math.max(lines[lineIndex].length, indentation(lines[lineIndex]) + key.length)
      };
    }
  }
  return {
    startLine: 0,
    startCharacter: 0,
    endLine: Math.max(lines.length - 1, 0),
    endCharacter: Math.max(lines.at(-1)?.length ?? 1, 1)
  };
}

function firstPathSegment(diagnosticPath?: string | null): string | undefined {
  if (!diagnosticPath) {
    return undefined;
  }
  return diagnosticPath.split(".")[0];
}

function indentation(line: string): number {
  return line.length - line.trimStart().length;
}
