# AppData Source Configuration Guide

This guide covers creating and linking AppData sources in DCT using the configuration-driven approach.

## Overview

An **AppData** source in Delphix allows direct backup/staging of databases using Delphix-managed infrastructure. This is configured via:

1. **Configuration File** (`appdata_source_config.yaml`) — defines the source, staging host, credentials, and DCT parameters
2. **Setup Script** (`setup_appdata_source.py`) — reads the config and executes the dSource link via DCT MCP

## Configuration File Structure

### `appdata_source_config.yaml`

```yaml
source:
  host: <source-database-host>
  type: MySQL|PostgreSQL|Oracle|etc
  link_type: AppDataStaged

staging:
  host: <staging-host>
  os_user: <os-user-on-staging>
  base_directory: <database-installation-path>
  mount_path: <unique-nfs-mount>
  port: <staging-database-port>
  server_id: <unique-server-id>

credentials:
  db_user: <database-user>
  db_password: <database-password>
  staging_init_password: <host-user-password>

dct_parameters:
  dSourceType: "Staging Push"
  resync: true

group:
  id: <dct-group-id>

environment:
  source_id: <dct-source-config-id>
  user_id: <dct-user-id>
  staging_environment_id: <dct-environment-id>
```

## Usage

### 1. Prepare Configuration

Edit `appdata_source_config.yaml` with your environment values:

```bash
# For MySQL on rh95-mys-s1.dlpxdc.co with staging on rh95-mys-t1.dlpxdc.co
vi appdata_source_config.yaml
```

Required fields:
- `source.host` — read/backup host
- `staging.host` — staging/link host
- `staging.port` — staging MySQL port (must differ from source 3306)
- `staging.server_id` — unique MySQL server-id
- `staging.mount_path` — unique NFS mount on staging host
- `credentials.db_password` — database user password
- `credentials.staging_init_password` — host user password
- `environment.*` — DCT resource IDs (search DCT for these)

### 2. Run Setup Script

```bash
# Using default config and auto-generated name
python setup_appdata_source.py

# Using custom config file
python setup_appdata_source.py --config my-config.yaml

# Using custom dSource name
python setup_appdata_source.py --name "my-prod-mysql-ds"

# Using different toolset
python setup_appdata_source.py --toolset platform_admin
```

### 3. Monitor Link Job

The script returns a job ID when successful:

```
✓ dSource link initiated
  Job ID: JOB-1234
  Status: RUNNING
```

Monitor progress via:
```bash
dct-mcp-test localhost --api-key $DCT_API_KEY
# Then: job_tool(action="get_job", job_id="JOB-1234")
```

## Environment ID Lookup

If you don't know the DCT environment IDs, search DCT:

```bash
# In Claude Code with dct-mcp-server running:
/dct-mcp-test localhost

# Then use these commands:
environment_source_tool(action="search_environment_sources")
staging_source_tool(action="search_staging_sources")
environment_tool(action="search_environments")
iam_tool(action="search_users")
group_tool(action="search_groups")
```

Extract the IDs and update your config file.

## MySQL AppData Field Reference

| Field | Value | Notes |
|-------|-------|-------|
| **Source Host** | rh95-mys-s1.dlpxdc.co | Read/backup host |
| **Staging Host** | rh95-mys-t1.dlpxdc.co | Where staging MySQL runs |
| **Staging Port** | 2150 | Must differ from source (3306) |
| **Staging Mount** | /mnt/link/2150 | Unique per staging port |
| **Server ID** | 150–999 | Unique on network |
| **DB User** | delphix_os | Standard Delphix user |
| **DB Password** | Delphix@123 | Use secure vault in production |
| **Host Password** | Delphix@123 | For OS-level setup |

## Troubleshooting

### Connection Refused (staging host)
- Verify staging host is reachable: `ssh delphix_os@<staging-host>`
- Check staging port is available: `netstat -an | grep 2150`
- Verify NFS mount exists: `ls -la /mnt/link/2150`

### Confirmation Required
If the response shows `confirmation_required`, the operation needs explicit approval:

```python
# In your script or MCP client:
data_tool(action="dsource_link_appdata", ..., confirmed=True)
```

### Job Fails
Check DCT logs on the staging host:

```bash
ssh delphix_os@<staging-host>
tail -f /var/log/delphix/dct.log
```

### Password Issues
- Verify credentials are correct for the environment
- Check password doesn't contain special shell characters (use quotes)
- In production, use DCT credential storage instead of YAML

## Advanced: Custom Configurations

Create multiple configs for different environments:

```bash
appdata_source_config.yaml           # Production MySQL
appdata_source_config_test.yaml      # Test MySQL
appdata_source_config_postgres.yaml  # PostgreSQL AppData
```

Run each:
```bash
python setup_appdata_source.py --config appdata_source_config_test.yaml --name "test-ds"
python setup_appdata_source.py --config appdata_source_config_postgres.yaml
```

## Security Best Practices

- Never commit passwords to git (use `.gitignore` or secrets manager)
- In production, store configs in encrypted vaults
- Restrict file permissions: `chmod 600 appdata_source_config.yaml`
- Rotate database passwords regularly
- Use DCT's built-in credential storage (`credentials_tool`)

## See Also

- [DCT API Documentation](https://docs.delphix.com/dct)
- [AppData Sources in DCT](https://docs.delphix.com/dct/data-management/appdata)
- [CLAUDE.md](./CLAUDE.md) — MCP server architecture
- [Testing Guide](./.claude/test/testing.md) — Running integration tests
