const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const manifest = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"));
const extensionJs = fs.readFileSync(path.join(root, "dist", "extension.js"), "utf8");

const requiredCommands = [
  "labflow.validateWorkflow",
  "labflow.askAiAboutDiagnostic",
  "labflow.explainWorkflow",
  "labflow.generateJanusDryRun",
  "labflow.runEvalSuite",
  "labflow.showAuditEvents"
];

const contributedCommands = new Set(
  manifest.contributes.commands.map((command) => command.command)
);

for (const command of requiredCommands) {
  assert.equal(contributedCommands.has(command), true, `${command} is contributed`);
  assert.match(extensionJs, new RegExp(command), `${command} is registered`);
}

assert.equal(
  manifest.activationEvents.includes("onLanguage:labflow-workflow"),
  true,
  "LabFlow language activation is configured"
);
assert.equal(
  manifest.contributes.configuration.properties["labflow.apiUrl"].default,
  "http://127.0.0.1:8000",
  "local API URL default is configured"
);
assert.match(extensionJs, /LabFlow AI Studio/, "output channel name is compiled");
assert.match(extensionJs, /onDidOpenTextDocument/, "diagnostics validate on document open");
assert.match(extensionJs, /onDidChangeActiveTextEditor/, "diagnostics validate on active editor change");
