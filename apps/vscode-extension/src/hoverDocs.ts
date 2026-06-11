import * as vscode from "vscode";

const DSL_DOCS = new Map<string, string>([
  ["workflow", "Workflow identity and type. LabFlow supports synthetic DNA quantification, DNA normalization, and RNA normalization + re-quantification workflows."],
  ["batch", "Batch metadata, including the batch ID that deterministic validators use for traceability."],
  ["samples", "Synthetic sample records. Sample IDs, source locations, and required concentrations must come from workflow data or deterministic tools."],
  ["normalization", "Normalization settings using canonical ng/uL, uL, and ng units. Molar targets are out of scope."],
  ["quantification", "Quantification settings for Varioskan TSV input, standards, blank correction, and concentration calculation."],
  ["outputs", "Requested outputs. JANUS worklists require deterministic validation and guarded dry-run/approval behavior."],
  ["janus", "JANUS-style CSV output is generated only through deterministic tool execution; invalid batches are blocked."]
]);

export class LabFlowHoverProvider implements vscode.HoverProvider {
  public provideHover(
    document: vscode.TextDocument,
    position: vscode.Position
  ): vscode.ProviderResult<vscode.Hover> {
    const range = document.getWordRangeAtPosition(position, /[A-Za-z_][A-Za-z0-9_]*/);
    if (range === undefined) {
      return undefined;
    }
    const word = document.getText(range);
    const doc = DSL_DOCS.get(word);
    if (doc === undefined) {
      return undefined;
    }
    return new vscode.Hover(new vscode.MarkdownString(`**${word}**\n\n${doc}`), range);
  }
}
