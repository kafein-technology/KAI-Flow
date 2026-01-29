# KAI-Fusion Workflow Export Bundle

Generated: 2026-01-15T06:09:00.663354Z
Exported by: mmetehanaydemir@gmail.com

## Contents
- 3 workflow(s)
- 1 credential(s) (empty - fill before import)

## Import Instructions

### 1. Edit `workflows_config.yaml`

- Set `target_user_email` to the target user's email
- Fill in all credential `secret` values with actual API keys

### 2. Run Import Script

```bash
cd backend
python -m scripts.import_workflows --config /path/to/workflows_config.yaml
```

## Workflows

- **Data Focus- Glossaries Generator** (ID: `02d9874c-9e48-4117-8aa6-35e6011d73a6`)
- **Data Focus- Regex List Generation** (ID: `6f47a6c7-f59c-486d-b2ea-83d82872c54c`)
- **Data Focus- List Generation** (ID: `4333653c-02ca-470f-8537-8eeda8ac6df6`)

## Credentials (fill these before import)

- **Open Router** (openai)
  - ID: `2da90dbb-80f4-4fad-8b51-a068e43a3b40`
  - Fields: ['api_key', 'created_at', 'id', 'name', 'service_type', 'updated_at']

