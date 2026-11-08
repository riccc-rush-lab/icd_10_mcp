# Connect to ICD10 Reference MCP

For **public terminology and synthetic examples only**. Not production-, clinical-
or PHI-ready. Never enter patient data, even to test the privacy screen.

Two ways to use the hosted reference service:

- Python or terminal: the screened local client.
- Claude Desktop: a local stdio bridge to that same client.

Neither requires CDC downloads, a local catalog, OpenMed, or model weights.
For fully local lookup instead, follow the [local trial guide](local-trial.md).

## 1. Get access and install

Source: <https://github.com/riccc-rush-lab/icd_10_mcp>.
Hosted MCP endpoint: `https://icd10-reference-mcp.onrender.com/mcp`.

**Public source is not public hosted access.** Ask the service operator for
approved trusted-pilot access and obtain the replacement service's token through
a private channel. There is no self-service signup or per-user OAuth. Do not put
the token in GitHub issues, chat prompts, screenshots, command arguments, or this repo.
The old demo's token does not work with the replacement endpoint.

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```sh
git clone https://github.com/riccc-rush-lab/icd_10_mcp.git
cd icd_10_mcp
uv sync --frozen --python 3.13
```

Keep the checkout and its `.venv` in place; the desktop configuration will point
to that Python executable. No global package installation is needed.

## 2. Store the token privately

On macOS/Linux, create a private directory:

```sh
mkdir -p "$HOME/.config/icd10-reference"
chmod 700 "$HOME/.config/icd10-reference"
```

Use a trusted local editor to save the operator-provided token as
`$HOME/.config/icd10-reference/token`, then:

```sh
chmod 600 "$HOME/.config/icd10-reference/token"
```

Use one plain ASCII token line, without quotes or a byte-order mark.
The file must be an **absolute-path, regular, non-symlink file**, at most 4 KiB.
On POSIX it must belong to your user and have no group/other permission bits
(`600` or `400`). Do not commit or share it.

On Windows, use a private file such as
`C:\Users\YOUR_USER\AppData\Roaming\icd10-reference\token`.
Restrict its ACL to your user under your organization's policy before using it.
**The loader does not validate Windows ACLs.** Windows runtime/desktop acceptance
has not been performed; the Windows example is a configuration template.

## 3. Check from the terminal

From the checkout on macOS/Linux:

```sh
.venv/bin/python -m icd10_mcp.reference_client \
  --url https://icd10-reference-mcp.onrender.com/mcp \
  --token-file "$HOME/.config/icd10-reference/token" \
  --public-terminology <<'JSON'
{"operation":"lookup","query":"pneumonia","service_date":"2026-10-01","limit":5}
JSON
```

Expect a `candidates` response containing `J18.9`,
`Pneumonia, unspecified organism`, for `icd10cm-2026-10-01`.
The first request may wait for the Free service to wake.
No note field is accepted. For selected-code validation, replace stdin JSON with:

```json
{"operation":"validate","codes":["E11.9"],"service_date":"2026-10-01"}
```

Expect `results[0].code_validity.status` to be `valid`. Exit `2` indicates a
blocked/invalid request or unavailable service. The terminal client also retains
`ICD10_DEMO_TOKEN` environment support when `--token-file` is omitted, but the
private file is preferred for this handoff.

Python callers, using the same virtual environment:

```python
import asyncio
import json

from icd10_mcp.client_config import load_token_file
from icd10_mcp.reference_client import ReferenceClient

client = ReferenceClient(
    "https://icd10-reference-mcp.onrender.com/mcp",
    load_token_file("/absolute/path/to/private/token"),
)
print(json.dumps(asyncio.run(client.lookup("E11.9", "2026-10-01")), indent=2))
# Also available: await client.validate(["E11.9"], "2026-10-01")
```

## 4. Configure Claude Desktop manually

**A local bridge does not make Claude conversations local.** Text entered into
Claude can be processed by its provider before any MCP tool call. Screening cannot
undo that transmission. Use only public/synthetic terminology in the conversation,
not patient-derived queries, identifiers, notes, or actual encounter details.

Use your approved Claude Desktop local-MCP configuration workflow. Builds with
**Settings → Developer → Edit Config** expose the JSON file there; UI labels vary
by version. Managed installations can prohibit local servers. Follow your admin's
policy, do not bypass it. This repo does not provide a desktop extension bundle.

Usual configuration locations:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Templates:

- [macOS example](../examples/claude-desktop.mac.example.json)
- [Windows example](../examples/claude-desktop.windows.example.json)

Replace `YOUR_USER` and the checkout location with **real absolute paths**.
The Python executable is `.venv/bin/python` on macOS, `.venv\Scripts\python.exe`
on Windows. Do not use `~`, `${HOME}`, relative paths or an activated-shell alias
inside the JSON. The token-file path belongs in `env`; **the token value does not**.

Merge only the `icd10-reference` entry into your existing `mcpServers` object.
Preserve other servers and unrelated settings. If the file does not exist, the
whole template is a starting point. Validate JSON, save, fully quit and reopen
Claude Desktop, then enable/approve the server through the app's tool controls.
No installed app settings are modified by this repository.

Expected server: **ICD10 Reference MCP (screened bridge)**. Exactly two tools:

| Tool | Inputs |
| --- | --- |
| `phrase_search` | `query`, `service_date`, optional `limit` (1–25) |
| `validate_selected_codes` | `codes`, `service_date` |

Use a synthetic/public request such as “Look up public code E11.9 for the example
date 2026-10-01 using ICD10 Reference MCP.” Inspect that the app actually calls
`phrase_search`; an uncited model answer is not a connection test.
Expect `Type 2 diabetes mellitus without complications`.

**Acceptance boundary:** official-SDK subprocess negotiation, these configuration
arguments, and live bridge calls have been checked on macOS. Actual Claude Desktop
UI/version behavior still requires this manual acceptance check. No GUI compatibility
or organization policy approval is claimed.

## Troubleshooting and limits

- **Startup failure:** check absolute Python/token paths, private file permissions,
  ownership, file size and token format. A generic error deliberately omits values.
  The executable must come from the installed checkout, not system Python.
- **No tools:** check valid JSON, preserve the existing config, restart fully, and
  confirm local-MCP access is permitted. A bridge launched in a terminal normally
  waits for protocol messages; it is not an interactive shell or a browser page.
- **`remote_unavailable`:** check network access and the operator-issued token;
  the Free service can sleep. Anonymous readiness is at
  <https://icd10-reference-mcp.onrender.com/readyz>. Readiness does not verify your token.
  Do not paste credentials or raw debug logs into support requests.
- **`privacy_blocked`:** do not bypass the screen. Use an independently chosen
  public code/short terminology phrase, not redacted patient text.
- **Invalid date:** supported examples are 2026-04-01 through 2027-09-30 across
  two releases. Dates are required; there is no current-date default or fallback.
- The screen is best effort and can both miss identifiers and block legitimate terms.
  It rejects rather than redacts. It does not establish PII absence or patient-data safety.
- The exact requested date is replaced on the wire with the release's public start
  date, then restored locally. This does not make patient-derived input acceptable.
- Hosted screening occurs after receipt. Arbitrary clients, desktop conversations,
  provider/proxy logs and debug logging remain outside the screen's control.
- Shared-secret trusted pilots are not institution-ready authentication, a production
  SLA, or clinical coding approval. Review all results and inherited instructions.

See [verification](verification.md) and [hosting/access limits](render-demo.md).
First-party configuration references:
[MCP local server guide](https://modelcontextprotocol.io/docs/2026-07-28/develop/connect-local-servers)
and [Claude local-server help](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop).
