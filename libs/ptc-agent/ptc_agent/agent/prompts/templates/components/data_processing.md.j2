# Data Processing

**Core principle**: Always dump data first, then process. This enables iterative inspection and reprocessing without re-fetching.

## Workflow: Dump First, Then Process

1. **Dump raw result** → Save to `data/` immediately after tool call
2. **Inspect structure** → Use bash/jq or code to peek at schema
3. **Extract what you need** → Process the saved file, not the raw result
4. **Return summary** → Only summaries flow to LLM

This approach:
- Preserves raw data for reprocessing
- Enables quick inspection with bash/jq
- Minimizes token usage
- Allows iterative refinement

## Inspecting Large Data

### Peek at JSON Structure
```python
import json

# Quick structure inspection
with open('data/large_file.json') as f:
    data = json.load(f)

# Show top-level keys and types
for key, value in data.items():
    print(f"{key}: {type(value).__name__}", end="")
    if isinstance(value, list):
        print(f" ({len(value)} items)")
    elif isinstance(value, dict):
        print(f" ({len(value)} keys)")
    else:
        print()
```

### Using jq for Quick Inspection (Bash)
```bash
# View structure
jq 'keys' data/file.json

# First item of array
jq '.[0]' data/file.json

# Count items
jq 'length' data/file.json

# Extract specific field
jq '.items[].name' data/file.json
```

### Display Key Statistics
```python
import json
from collections import Counter

with open('data/results.json') as f:
    data = json.load(f)

# For list data
if isinstance(data, list):
    print(f"Total records: {len(data)}")
    if data and isinstance(data[0], dict):
        print(f"Fields: {list(data[0].keys())}")
        # Count by category if applicable
        if 'type' in data[0]:
            types = Counter(item['type'] for item in data)
            print(f"By type: {dict(types)}")
```

## Finding Specific Sections

### Search within JSON
```python
# Find items matching criteria
matches = [item for item in data if 'keyword' in item.get('name', '').lower()]
print(f"Found {len(matches)} matches")
```

### Using grep for Quick Search
```bash
# Find lines containing pattern
grep -n "error" data/logs.json

# Context around match
grep -B2 -A2 "target_id" data/results.json
```

## When to Dump to `data/` Directory

ALWAYS dump tool results to `data/` when:
- **Structured data**: JSON, dictionaries, lists with >10 items
- **Large text**: Responses >500 characters
- **Tabular data**: DataFrames, CSV-like data with >5 rows
- **API responses**: Raw API responses (preserve for reprocessing)
- **Intermediate results**: Data that may be referenced later

## Storage and Summary Pattern

```python
import json

# 1. Get data from tool
result = some_mcp_tool(query="...")

# 2. Dump full result
with open('data/tool_result_001.json', 'w') as f:
    json.dump(result, f, indent=2)

# 3. Return ONLY summary
items = result.get('items', [])
print(f"""
## Result Summary
- Saved to: data/tool_result_001.json
- Records: {len(items)}
- Fields: {list(items[0].keys()) if items else 'N/A'}
- Sample: {items[0] if items else 'empty'}
""")
```
