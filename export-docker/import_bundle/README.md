# KAI-Fusion Workflow Export Bundle

Export Name: `<your_export_name>`
Generated: `<timestamp>`
Exported by: `<exporter_email>`

## Contents
- `X` workflow(s)
- `X` credential(s) (empty - fill before import)

## Import Instructions

### 1. Edit `<your_export_name>_workflows_config.yaml`

- Set `target_user_email` to the target user's email ID. If the user does not exist within the system, you can provide a `user_password` to securely and automatically create the user account during import.
- **Security Notice:** Check the YAML configurations and manually fill in all credential `secret` values (such as API Keys, Connection Strings, Base URLs) with actual values. **Do not commit the filled file to version control.**

### 2. Run Import Script

Run the following command in the terminal within your backend deployment environment:

```bash
cd backend
python -m scripts.import_workflows --config /path/to/<your_export_name>_workflows_config.yaml
```

*Note: The script safely creates new UUID bounds, updates existing schemas if names match, and automatically links workflow internal dependencies avoiding any data-corruption or primary-key collisions across environments.*

## Workflows

*The exported workflows are sequentially listed here with their names and reference IDs during a real export.*
*- Example Workflow Name 1*
*- Example Workflow Name 2*

## Credentials (fill these before import)

*Details regarding sensitive logic, API keys, or database integrations needed by the specific workflows outline themselves here. The actual secret variables are excluded safely by KAI-Flow—you must securely assign them in your `.yaml` config before running the import step.*
