# LabFlow VS Code Extension Smoke Test

Run from the repository root:

```text
npm --prefix apps/vscode-extension test
```

The smoke tests compile the extension, verify that the required commands are contributed and registered, verify LabFlow YAML activation and the `labflow.apiUrl` setting, and unit-test API diagnostic mapping.

Manual Stage 13 check:

1. Start the local API from the repository root.
2. Open `examples/workflows/invalid_missing_blank.workflow.yaml` in VS Code.
3. Run `LabFlow: Validate Workflow` or save the file.
4. Confirm a LabFlow diagnostic appears with code `MISSING_PLATE_BLANK` and a suggested action.
5. Put the cursor on that diagnostic and run `LabFlow: Ask AI About Diagnostic`.
6. Confirm the `LabFlow AI Studio` output channel shows an answer, sources, tool calls, and next safe action.
