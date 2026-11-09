# Connect to ICD10 Reference MCP

**Public terminology and synthetic examples only.** Not production-, clinical- or
PHI-ready. Never enter patient data, even to test the privacy screen.

**Deployment status:** public no-login access and reviewed hardening are live at
commit `def06ee`. Nine public acceptance calls passed through the official SDK,
CLI and local bridge. Native client GUI checks remain manual.
See [verification](verification.md#hardening-rollout).

Endpoint: `https://icd10-reference-mcp.onrender.com/mcp`.
This is an MCP interface, not a browser search page.

## Option 1: connect by URL, no local installation

No server signup, API key or OAuth client is needed. Use **Streamable HTTP**,
not the legacy SSE transport. Client account/plan requirements are separate.

1. In Claude, open **Customize → Connectors → Add custom connector**. Organization
   owners may need to add it first under Organization settings.
2. Name it **ICD10 Reference MCP**.
3. Enter `https://icd10-reference-mcp.onrender.com/mcp`.
4. Choose **No sign-in**, if authentication settings appear. Leave credentials
   and request headers empty. Enable the connector for your conversation.
5. Ask: “Use ICD10 Reference MCP to look up public code E11.9 for example date
   2026-10-01.” Inspect that Claude actually calls `phrase_search`, not just answers
   from memory. Expect `Type 2 diabetes mellitus without complications`.

UI labels/availability depend on the app version, plan and organization policy.
Actual Claude UI acceptance remains manual; official-SDK checks are not GUI checks.

**This connection originates from Claude's cloud and bypasses our local preflight.**
Server screening occurs after receipt. Conversation text can already have been
processed by Claude before a tool call. Neither no-login access nor screening makes
patient-derived input acceptable. Direct clients send the date they supply unchanged.
Only use public example dates and terminology.

### Other MCP clients

These are documented setup recipes, not completed end-to-end app acceptance.
Inspect the actual discovered tools and returned result in each client.

Run only the command for your installed client:

```sh
# Claude Code, then restart and inspect /mcp:
claude mcp add --transport http --scope user icd10-reference https://icd10-reference-mcp.onrender.com/mcp

# OpenAI Codex CLI / IDE, then restart and inspect /mcp:
codex mcp add icd10-reference --url https://icd10-reference-mcp.onrender.com/mcp

# Gemini CLI, then restart and inspect /mcp:
gemini mcp add --transport http --scope user icd10-reference https://icd10-reference-mcp.onrender.com/mcp

# Factory Droid, then inspect /mcp:
droid mcp add icd10-reference https://icd10-reference-mcp.onrender.com/mcp --type http --no-oauth
```

For **Cursor**, merge this entry into your existing `~/.cursor/mcp.json`
or project `.cursor/mcp.json`, then enable the server in MCP settings:

```json
{
  "mcpServers": {
    "icd10-reference": {
      "url": "https://icd10-reference-mcp.onrender.com/mcp"
    }
  }
}
```

For **VS Code / GitHub Copilot**, run **MCP: Add Server** from the Command Palette,
choose **HTTP**, enter the endpoint and `icd10-reference` ID, and choose the desired
scope (current guided setup offers **Global → Copilot Global**). Enable its tools
through **Chat: Open Customizations → Tools**. Versions use different configuration
locations/schemas; do not paste Cursor JSON into `.vscode/mcp.json`.

For **ChatGPT web**, follow its current custom-MCP/plugin setup and select
**No authentication**. Availability depends on plan and workspace policy.
Search/fetch-only connectors do not establish compatibility with these custom
tools. ChatGPT web does not read the Codex CLI configuration.

First-party references: [Claude Code](https://code.claude.com/docs/en/mcp),
[Codex](https://developers.openai.com/codex/mcp),
[Gemini CLI](https://geminicli.com/docs/tools/mcp-server/),
[Droid](https://docs.factory.com/harness/mcp),
[Cursor](https://cursor.com/docs/mcp),
[VS Code](https://code.visualstudio.com/docs/copilot/chat/mcp-servers), and
[ChatGPT](https://developers.openai.com/plugins/deploy/connect-chatgpt).
Labels and support can change; managed clients may block unapproved servers.

## Option 2: screened Python, terminal or local stdio bridge

The optional local client screens before connecting and substitutes the release's
public start date on the wire, restoring your requested date locally. It can miss
identifiers or block legitimate terms; it does not guarantee PII absence. It rejects
rather than silently redacts clinical meaning.

No CDC downloads, local catalog, OpenMed or model weights are required.
For entirely local lookup, use the [local trial guide](local-trial.md).

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```sh
git clone https://github.com/riccc-rush-lab/icd_10_mcp.git
cd icd_10_mcp
uv sync --frozen --python 3.13
```

### Terminal

From the checkout on macOS/Linux:

```sh
.venv/bin/python -m icd10_mcp.reference_client \
  --url https://icd10-reference-mcp.onrender.com/mcp \
  --anonymous --public-terminology <<'JSON'
{"operation":"lookup","query":"pneumonia","service_date":"2026-10-01","limit":5}
JSON
```

Expect `J18.9`, `Pneumonia, unspecified organism`, for `icd10cm-2026-10-01`.
For validation, replace stdin JSON with:

```json
{"operation":"validate","codes":["E11.9"],"service_date":"2026-10-01"}
```

Expect `results[0].code_validity.status` to be `valid`. No note field is accepted.
`--anonymous` sends no credential, even if an old token is in the environment.
Exit `2` means blocked/invalid input or unavailable service.
The hardened local client requests uncompressed responses, rejects unsupported
compression and caps remote bodies at 256 KiB before SDK parsing. Invalid or
oversized upstream responses return generic `remote_unavailable`; the whole
exchange has a 90-second cooperative deadline.
Redirects are rejected before SDK processing, even to another path on the same
host. Configure the final HTTPS `/mcp` URL, not a redirecting alias.

### Python

Use the same virtual environment:

```python
import asyncio
import json

from icd10_mcp.reference_client import ReferenceClient

client = ReferenceClient("https://icd10-reference-mcp.onrender.com/mcp")
print(json.dumps(asyncio.run(client.lookup("E11.9", "2026-10-01")), indent=2))
# Also available: await client.validate(["E11.9"], "2026-10-01")
```

### Claude Desktop local bridge

**A local bridge does not make Claude conversations local.** The chat provider can
process text before MCP. Public/synthetic examples only, never notes or encounters.

Use your approved local-MCP configuration workflow. Builds with **Settings →
Developer → Edit Config** expose the JSON file there; labels vary. Managed apps
may prohibit local servers. Follow policy, do not bypass it.

Usual configuration files:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Templates: [macOS](../examples/claude-desktop.mac.example.json),
[Windows](../examples/claude-desktop.windows.example.json).

Replace `YOUR_USER` and the checkout location with real **absolute paths**.
Use `.venv/bin/python` on macOS or `.venv\Scripts\python.exe` on Windows.
No `~`, `${HOME}`, relative paths or activated-shell aliases inside JSON.
Keep the checkout and environment in place. The public templates contain no token.

Merge only `icd10-reference` into the existing `mcpServers` object. Preserve other
servers and preferences. Validate JSON, save, fully quit/reopen Claude, then approve
the tools. No installed settings are changed automatically. This is manual stdio
configuration, not a packaged desktop extension.

Expected bridge identity: **ICD10 Reference MCP (screened bridge)**.
Both the direct server and bridge expose exactly these read-only tools:

| Tool | Inputs |
| --- | --- |
| `phrase_search` | `query`, `service_date`, optional `limit` (1–25) |
| `validate_selected_codes` | `codes`, `service_date` |

Official-SDK subprocess configuration is tested on macOS. Windows templates are
syntax/path examples, not Windows runtime or GUI acceptance.

## Compatibility: token-protected deployments

Protected mode remains the server default. Public mode requires the operator to
explicitly set `ICD10_PUBLIC_ACCESS=1` and deploy. A `401` can mean it is not active
or has been rolled back; there is no automatic signup.

For a protected deployment, obtain its token privately from its operator.
Replace `--anonymous` with `--token-file /absolute/path/to/private/token`.
The CLI also retains `ICD10_DEMO_TOKEN` environment support without those flags.

For the bridge, add `ICD10_REFERENCE_TOKEN_FILE` to its `env` with the absolute file
path, never the token value. Omit that variable entirely for anonymous access.
Python can pass `load_token_file(...)` from `icd10_mcp.client_config` as the second
`ReferenceClient` argument.

Use an absolute regular, non-symlink file, at most 4 KiB, containing one ASCII token
line without quotes/BOM. On POSIX, it must belong to your user with no group/other
permission bits (`chmod 600` or `400`); use a private directory. Windows requires
manual ACL restriction; the loader does not validate Windows ACLs.
Never publish tokens in Git, prompts, screenshots, URLs, command arguments or logs.

## Public limits and zero-spend conditions

Public-mode defaults, shared by all callers of one process:

- 120 HTTP requests per 60-second fixed window, not 120 tool calls.
- Four admitted in-flight requests.
- 8 KiB request bodies; 256 KiB response bodies.
- A 15-second cooperative deadline for body receipt, application work and response writes.
- Minimal GET `/healthz` and `/readyz` probes are outside admission limits.

MCP initialization/notifications also consume requests. Limits reset on process
restart and are not distributed/monthly quotas. They do not stop traffic from
reaching the hosting provider or impose a hard CPU, socket-delivery or billing cap.
Oversized responses are replaced, not silently truncated clinical instructions.
Rejection writes are bounded, with at most one extra second to attempt a pre-header
timeout response. These controls are deployed; see [SECURITY](../SECURITY.md).

The operator's zero-spend setup depends on **Free workspace/resources, no linked
payment method, no paid add-ons/APIs, and accepting shutdown at exhausted quotas**.
The operator reports no payment method is linked; this was not an independent
billing-account audit. Under [Render's current policy](https://render.com/docs/free),
linked payment methods can permit overage charges even on Free compute.
A pipeline spending limit or usage alert is not an overall bill cap.
Do not add a payment method or upgrade resources under this arrangement.

Allowances are shared with other workspace services. Heavy use can suspend other
Free apps too. There is no uptime SLA or perpetual guarantee about provider terms.
Claude/other clients may have their own account fees; this MCP does not call or
bill a model API.

## Troubleshooting and privacy

- **`429`:** shared request quota reached. Respect `Retry-After`; do not retry-loop.
- **`503`:** busy, oversized response or unavailable backend. Narrow the query/limit
  and try later; do not strip coding instructions to make an answer look complete.
- **`504`:** application deadline. Do not repeatedly submit the same request.
- **`remote_unavailable`:** the screened client sanitizes HTTP/protocol failures.
  The Free host may be sleeping, rate-limited or quota-suspended. Minimal readiness:
  <https://icd10-reference-mcp.onrender.com/readyz>.
- **Startup/no tools:** check absolute executable paths, installed dependencies,
  valid JSON and organization permissions. A stdio bridge waits for protocol input.
- **`privacy_blocked`:** do not bypass screening or use redacted patient text.
  Choose an independently selected public term instead.
- Dates are required: 2026-04-01 through 2027-09-30 across two releases; no default
  current date or fallback. Only the local client/bridge substitutes release anchors.
- Hosted checks are after receipt. Arbitrary clients, cloud conversations,
  provider/proxy logs and debug logging remain outside local screening's control.
  Authentication and screening do not establish patient-data or clinical safety.

See [verification](verification.md), [hosting limits](render-demo.md), and first-party
[Claude remote connector instructions](https://claude.com/docs/connectors/custom/remote-mcp).
