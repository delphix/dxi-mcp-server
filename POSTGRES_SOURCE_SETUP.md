# PostgreSQL Source Setup Guide

This guide walks you through setting up a PostgreSQL database as a dSource in Delphix Data Control Tower (DCT).

## Prerequisites

- **DCT Installation**: A running DCT instance with API access
- **PostgreSQL Version**: 9.4 or later (recommended: 12+)
- **Source Database**: A PostgreSQL database you want to replicate
- **Staging Environment**: A separate Linux/Unix environment for the staging dSource
- **DCT Credentials**: Valid API key and base URL

### Permissions Required

- DCT platform admin or source admin role
- OS-level sudo access on both source and staging hosts
- PostgreSQL superuser or role with replication privileges

### Network Requirements

- Source database must be accessible from staging environment
- Staging environment must have network access to source on port 5432 (or configured port)
- Firewall rules must allow replication traffic

## Step 1: Prepare Your PostgreSQL Source

### Enable WAL Archiving (Required for Log-Based Replication)

On the **source PostgreSQL server**, update `postgresql.conf`:

```ini
# Enable WAL archiving
wal_level = replica              # Required for streaming replication
max_wal_senders = 10             # Max concurrent WAL sender processes
wal_keep_segments = 128          # Number of WAL segments to keep
```

Restart PostgreSQL:

```bash
sudo systemctl restart postgresql
```

### Create Replication User (Optional but Recommended)

```sql
-- Connect as superuser
sudo -u postgres psql

-- Create replication user
CREATE ROLE replication_user WITH REPLICATION LOGIN PASSWORD 'strong_password';
GRANT CONNECT ON DATABASE your_database TO replication_user;
```

### Configure pg_hba.conf for Replication

Add replication entry to `/etc/postgresql/15/main/pg_hba.conf`:

```
# Allow replication connections
host    replication     replication_user    staging_host/32    md5
host    replication     replication_user    127.0.0.1/32       md5
```

Reload the configuration:

```bash
sudo -u postgres psql -c "SELECT pg_reload_conf();"
```

## Step 2: Prepare the Staging Environment

### Create Delphix OS User

On the **staging server**:

```bash
# Create delphix_os user if not present
sudo useradd -m -s /bin/bash delphix_os

# Add to sudoers (optional, for elevated privileges)
echo "delphix_os ALL=(ALL) NOPASSWD: ALL" | sudo tee -a /etc/sudoers.d/delphix_os
```

### Install PostgreSQL on Staging

Ensure PostgreSQL client tools are installed (required for recovery operations):

```bash
# Ubuntu/Debian
sudo apt-get install postgresql-client postgresql-15

# RHEL/CentOS
sudo yum install postgresql postgresql-libs
```

### Create Staging Storage Directory

```bash
# Create staging data directory
sudo mkdir -p /var/lib/postgresql/15/staging
sudo chown postgres:postgres /var/lib/postgresql/15/staging
sudo chmod 700 /var/lib/postgresql/15/staging

# Create WAL archive directory
sudo mkdir -p /var/lib/postgresql/15/wal_archive
sudo chown postgres:postgres /var/lib/postgresql/15/wal_archive
sudo chmod 700 /var/lib/postgresql/15/wal_archive
```

## Step 3: Register Environment in DCT

### Via DCT UI

1. Navigate to **Environments** → **Add Environment**
2. Select **Linux/Unix**
3. Enter staging server hostname and credentials
4. Verify connectivity
5. Record the **Environment ID** (e.g., `ENVIRONMENT-123`)

### Via DCT API (Using dct-mcp-test)

```bash
# Search for existing environments
dct-mcp-test localhost environment_tool action=search

# Or create a new environment
dct-mcp-test localhost environment_tool action=create \
  --name "staging-postgres-1" \
  --hostname "staging.example.com" \
  --os "Linux"
```

## Step 4: Create PostgreSQL Source Configuration

### Option A: Use the Configuration Template

1. Copy `postgres_source_config.yaml` to your working directory
2. Fill in all `{{ PLACEHOLDER }}` values:

```yaml
source:
  hostname: "postgres-prod.company.com"
  port: 5432
  database_name: "production"

staging:
  environment_id: "ENVIRONMENT-123"  # From Step 3
  hostname: "postgres-staging.company.com"
  postgres_installation_path: "/usr/lib/postgresql/15"
  postgres_data_path: "/var/lib/postgresql/15/staging"

credentials:
  source:
    db_user: "replication_user"  # Or "postgres"
    db_password: "your_password"
  staging_os:
    username: "delphix_os"
    password: "os_password"
```

### Option B: Use the Python Setup Script

```bash
# Make script executable
chmod +x create_postgres_source.py

# Run with defaults
python3 create_postgres_source.py \
  --source-name "prod-postgres" \
  --hostname "postgres-prod.company.com" \
  --database "production" \
  --installation-path "/usr/lib/postgresql/15" \
  --data-path "/var/lib/postgresql/15/main"

# Or with custom replication user
python3 create_postgres_source.py \
  --source-name "prod-postgres" \
  --hostname "postgres-prod.company.com" \
  --database "production" \
  --replication-user "replication_user"
```

## Step 5: Verify Source Connectivity

### Test Source Connection

```bash
# Test connectivity to source database
psql -h postgres-prod.company.com -U replication_user -d production -c "SELECT version();"

# Expected output should show PostgreSQL version
```

### Test Staging Environment

```bash
# SSH to staging and verify PostgreSQL tools
ssh delphix_os@postgres-staging.company.com
which pg_basebackup
which pg_dump
```

## Step 6: Initiate dSource Link

Once the source is created in DCT:

```bash
# Link the source (creates initial backup and starts continuous sync)
dct-mcp-test localhost dsource_tool action=link \
  --source-id "SOURCE-123" \
  --name "prod-postgres-dsource"

# Monitor linking job
dct-mcp-test localhost job_tool action=get --job-id <job_id>
```

## Step 7: Verify dSource State

```bash
# Search for the created dSource
dct-mcp-test localhost dsource_tool action=search

# Get detailed status
dct-mcp-test localhost dsource_tool action=get --dsource-id "DSOURCE-123"

# Expected status: ENABLED or SYNCING
```

## Troubleshooting

### Connection Timeout

**Symptom**: "Unable to connect to source database"

**Solution**:
1. Verify firewall allows port 5432 from staging to source
2. Check pg_hba.conf allows replication user
3. Verify replication user password is correct

```bash
# Diagnose connectivity
psql -h source_host -U replication_user -d postgres -v "ON_ERROR_STOP=1"
```

### WAL Archiving Not Working

**Symptom**: "WAL archiving failed" or "Archive command exited with code X"

**Solution**:
1. Check `wal_level = replica` in postgresql.conf
2. Verify archive directory exists and has correct permissions
3. Check PostgreSQL logs for errors

```bash
# Check PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-15-main.log | grep archive
```

### Insufficient Disk Space on Staging

**Symptom**: "Linking failed - disk space"

**Solution**:
1. Ensure staging has at least 1.5x source database size
2. Pre-clean archived WAL segments if needed

```bash
# Monitor disk usage
df -h /var/lib/postgresql/

# Clean old WAL archives (if safe)
sudo rm -f /var/lib/postgresql/15/wal_archive/000000010000*
```

### Replication Lag

**Symptom**: Continuous sync falling behind

**Solution**:
1. Increase max_wal_senders on source
2. Adjust network bandwidth limits in DCT config
3. Monitor source write activity during peak hours

## Reference

### Configuration Files

- **Source Template**: `postgres_source_config.yaml`
- **Setup Script**: `create_postgres_source.py`

### DCT Tools

- `environment_tool` — manage environments
- `environment_source_tool` — register sources
- `staging_source_tool` — manage staging instances
- `dsource_tool` — manage dSources (linked sources)

### PostgreSQL Documentation

- [PostgreSQL Streaming Replication](https://www.postgresql.org/docs/current/warm-standby.html)
- [PostgreSQL WAL Archives](https://www.postgresql.org/docs/current/wal-configuration.html)
- [PostgreSQL Roles and Privileges](https://www.postgresql.org/docs/current/user-manag.html)

### Security Best Practices

1. Use SSL/TLS for all connections in production
2. Store credentials in a secure vault (HashiCorp Vault, AWS Secrets Manager)
3. Rotate replication user password regularly
4. Restrict network access with firewall rules
5. Use SSH keys instead of passwords for OS authentication

## Next Steps

Once your dSource is linked and syncing:

1. **Create Snapshots**: Take snapshots for point-in-time recovery
2. **Provision VDBs**: Create virtual databases for development/testing
3. **Set Retention Policies**: Define how long snapshots are retained
4. **Configure Masking**: Apply data masking policies if handling PII
5. **Set Compliance Policies**: Implement compliance tags and policies

## Support

For issues or questions:

- Check DCT logs: `logs/dct_mcp_server.log`
- Review PostgreSQL server logs
- Consult DCT documentation: https://docs.delphix.com
- Check PostgreSQL documentation: https://www.postgresql.org/docs/
