const assert = require("node:assert/strict");
const { mapApiDiagnostic, rangeForPath } = require("../dist/diagnosticMapping");

const workflowText = [
  "workflow:",
  "  name: invalid_missing_blank",
  "batch:",
  "  batch_id: DNA_QUANT_BAD_BLANK",
  "outputs:",
  "  janus: true"
].join("\n");

const mapped = mapApiDiagnostic(
  {
    code: "MISSING_PLATE_BLANK",
    message: "Sample plate is missing a blank.",
    severity: "error",
    path: "outputs.janus",
    suggested_action: "Add one blank well per sample plate."
  },
  workflowText
);

assert.equal(mapped.code, "MISSING_PLATE_BLANK");
assert.equal(mapped.severity, "error");
assert.equal(mapped.range.startLine, 4);
assert.match(mapped.message, /Suggested action/);

const fallback = rangeForPath(workflowText, "does_not_exist.value");
assert.equal(fallback.startLine, 0);
assert.equal(fallback.endLine, 5);
