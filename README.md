# Contexto

A navigable graph of your Python codebase for LLMs. Instead of dumping your entire codebase, Contexto lets LLMs explore and navigate your code structure autonomously.

## Installation

```bash
pip install contexto
```

## Quick Start

### 1. Index your project

```bash
cd /path/to/your/project
contexto index
```

This creates a `.contexto.db` database with the project graph.

### 2. Start the MCP server

```bash
contexto serve
```

The MCP server starts on `stdio`, ready to be used by Claude or other LLMs.

### 3. Configure your LLM

#### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "contexto": {
      "command": "contexto",
      "args": ["serve"],
      "cwd": "/path/to/your/project"
    }
  }
}
```

#### Claude Code (CLI)

Add to `.claude/settings.json` in your project:

```json
{
  "mcpServers": {
    "contexto": {
      "command": "contexto",
      "args": ["serve"]
    }
  }
}
```

## MCP Tools

Once configured, the LLM has access to these tools:

### `map()`

Returns a compact map of the project structure.

```xml
<map project="myapp" root="/path/to/myapp">
  <dir name="src" files="12" classes="8" functions="45">
    <dir name="api" files="3"/>
    <dir name="services" files="2"/>
  </dir>
  <dir name="tests" files="8"/>
</map>
```

### `expand(path)`

Expands a node to show its children.

```
expand("src/api/users.py")
```

```xml
<file path="src/api/users.py" lines="1-95">
  <class name="UserController" lines="10-89">
    <docstring>Handles user API endpoints</docstring>
    <method name="get_user" lines="15-25"/>
    <method name="create_user" lines="27-45"/>
  </class>
  <function name="validate_user_id" lines="91-95"/>
</file>
```

### `inspect(path)`

Shows detailed info about an entity: signature, docstring, relationships.

```
inspect("src/api/users.py:UserController.get_user")
```

```xml
<method name="get_user" path="src/api/users.py" lines="15-25">
  <signature>def get_user(self, user_id: int) -> User</signature>
  <docstring>Retrieve user by ID from database.</docstring>
  <calls>
    <ref path="src/services/user_service.py:UserService.find_by_id"/>
  </calls>
</method>
```

### `read(path, start_line?, end_line?)`

Reads source code from a file or specific line range.

```
read("src/api/users.py", 15, 25)
```

### `search(query, limit?)`

Searches for entities by keyword (names, docstrings, signatures).

```
search("authentication")
```

```xml
<results query="authentication" count="3">
  <result score="0.89" path="src/api/auth.py:require_auth">
    <type>function</type>
    <signature>def require_auth(func: Callable) -> Callable</signature>
  </result>
</results>
```

## CLI Commands

```bash
# Index project (creates .contexto.db)
contexto index [path]

# Start MCP server
contexto serve

# Debug: show project map
contexto map

# Debug: expand a node
contexto expand <path>

# Debug: search
contexto search <query>
```

## How the LLM Uses Contexto

When you ask the LLM "add authentication to API endpoints":

1. **LLM calls `map()`** → sees project structure
2. **LLM calls `expand("src/api")`** → sees API files
3. **LLM calls `search("auth")`** → finds existing patterns
4. **LLM calls `inspect("src/api/users.py:UserController")`** → sees methods to modify
5. **LLM knows exactly WHERE and HOW to modify**

## Why Contexto?

| Approach | Tokens | LLM Control |
|----------|--------|-------------|
| Dump entire codebase | 10,000+ | None |
| **Contexto navigation** | ~100-500 | Full |

Instead of overwhelming the LLM with your entire codebase, Contexto lets the LLM explore only what it needs, when it needs it.

## Limitations

- Python only (for now)
- Requires LLM with MCP support (Claude, GPT with function calling)

## License

MIT
