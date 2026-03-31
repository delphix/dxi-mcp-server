# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Config Directory

This directory is the primary place to make changes without touching Python code.

### Toolset Files (`toolsets/*.txt`)

Define which DCT API endpoints belong to each persona toolset.

**Format:**
```
# Toolset Name - N Tools
# Description: <shown in auto-mode discovery>
# Target users: <shown in auto-mode discovery>

# TOOL N: tool_name - Tool Description
METHOD|/endpoint/path/{pathParam}|action_name
```

**Rules:**
- The `# TOOL N: tool_name - Description` header defines a grouped tool. All lines below it (until the next `# TOOL` header) belong to that tool.
- `action_name` must match what the tool implementation in `tools/*_endpoints_tool.py` handles.
- Use `@inherit:parent_toolset_name` to include all APIs from another toolset.
- The toolset file name (without `.txt`) is the value used in `DCT_TOOLSET`.

**Adding a new endpoint to an existing toolset:**
1. Find the relevant `# TOOL` section in the `.txt` file.
2. Add a line: `METHOD|/path/{param}|action_name`
3. Implement `action_name` handling in the corresponding `tools/*_endpoints_tool.py`.
4. No other changes needed.

**Creating a new toolset:**
1. Create `toolsets/my_toolset.txt` with the format above.
2. Add tool-to-module mappings in `loader.py:get_modules_for_toolset()` for any new tool names.

### Confirmation Rules (`mappings/manual_confirmation.txt`)

Controls which operations require user confirmation before execution.

**Format:**
```
METHOD|path_pattern|confirmation_level|message_template
```

**Confirmation levels:**
| Level | Meaning |
|---|---|
| `standard` | Simple yes/no confirmation |
| `elevated` | Stronger warning |
| `manual` | Must type specific text to confirm |
| `retention_check:N` | Conditional — triggers only if snapshot retention < N days |
| `policy_impact_check:N` | Conditional — triggers if policy affects > N objects |

- Use `*` as the method wildcard to match any HTTP method.
- Path patterns support `{paramName}` placeholders (matched as `[^/]+` regex).
- Message templates support variable substitution with `{variable_name}`.
- Rules are evaluated in order; first match wins.

### `config.py` and `loader.py`

- `config.py` — Reads and validates all environment variables. Add new env vars here.
- `loader.py` — Parses `.txt` files; results are `@lru_cache`d. Call `clear_cache()` if config files change at runtime.
