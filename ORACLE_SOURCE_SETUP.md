# Oracle Source Configuration Setup Guide

This guide explains how to create and configure an Oracle source (dSource) in Delphix Data Control Tower (DCT) using the MCP server.

## Overview

An Oracle source configuration establishes a link between a production Oracle database and DCT, enabling:
- Continuous data synchronization via RMAN or log-based replication
- Virtual database (VDB) provisioning from snapshots
- Time-travel recovery to any point in transaction history

## Prerequisites

Before creating an Oracle source, you need:

1. **Source Oracle Database**
   - Oracle Database 11g, 12c, 18c, 19c, or 21c
   - SSH access to the host running Oracle
   - DBA or equivalent privileges on the database
   - RMAN backup capability enabled

2. **Staging/Target Environment**
   - UNIX-based OS (Linux, AIX, Solaris) or Windows
   - Oracle software installed (same or compatible version as source)
   - At least 500GB free space for staging database
   - Network connectivity to source database
   - Delphix-managed OS user account (e.g., `delphix_os`)

3. **DCT Setup**
   - Engine running and accessible
   - Environment created for source Oracle host
   - Environment created for staging/target host
   - Environment user credentials configured

## Configuration Parameters

### Source Database Configuration

```yaml
source:
  hostname: oracle-prod.example.com
  port: 1521
  instance_name: ORCL
  database_type: Oracle
  
  # Oracle software locations
  oracle_home: /u01/app/oracle/product/19c/db_1
  oracle_base: /u01/app/oracle
  instance_owner: oracle
  
  # RAC Configuration (if applicable)
  is_cluster: false
  cluster_address: scan.example.com          # For RAC only
  cluster_user: oracle                        # For RAC only
  oracle_cluster_node_name: orcl1             # For RAC only
```

### Staging/Target Configuration

```yaml
staging:
  hostname: oracle-staging.example.com
  environment_id: 3-UNIX_HOST_ENVIRONMENT-1
  
  # Delphix OS user
  environment_user: delphix_os
  environment_user_id: ENVIRONMENT_USER-1
  
  # Oracle software on staging
  oracle_home: /u01/app/oracle/product/19c/db_1
  oracle_base: /u01/app/oracle
  
  # Staging database instance
  staging_instance_name: ORCL_STG
  staging_port: 1521
```

### Credentials

```yaml
credentials:
  # Source database credentials
  source_db_user: sys
  source_db_password: SecurePassword123!
  
  # For ASE authentication (if applicable)
  use_kerberos_authentication: false
  
  # Staging environment OS access
  staging_os_user: delphix_os
  staging_os_password: OsPassword123!
```

### DCT Integration Parameters

```yaml
dct_parameters:
  # Source type: determines replication method
  sourceType: "Continuous Data Admin"  # or "Self-Service"
  
  # Automatic resync on divergence
  resync: true
  
  # RMAN backup configuration
  rman_channels: 2
  files_per_set: 5
  backup_level_enabled: true
  
  # Network optimization
  number_of_connections: 4
  bandwidth_limit: 500  # MB/s
  
  # Compression and encryption
  compressed_linking_enabled: false
  encrypted_linking_enabled: false
  
  # TDE (Transparent Data Encryption) Configuration
  tde_enabled: false
  # tde_keystore_config_type: FILE          # FILE, ORACLE_CLOUD, AWS_KMS
  # tde_keystores_root_path: /u01/app/oracle/admin/ORCL/wallet
  
  # LogSync Configuration (if using log-based replication)
  logsync_enabled: true
  logsync_interval: 10  # seconds
  logsync_mode: AUTO   # AUTO or MANUAL
```

## Creating an Oracle Source

### Method 1: Using the Python Script

```bash
# Set up environment variables
export DCT_API_KEY="your-api-key"
export DCT_BASE_URL="https://your-dct-engine.example.com"

# Run the creation script with defaults
python3 create_oracle_source.py

# Or with custom parameters
python3 create_oracle_source.py \
  --source-name "prod-oracle-src" \
  --hostname "oracle-prod.example.com" \
  --instance "PRODDB" \
  --oracle-home "/u01/app/oracle/product/19c/db_1" \
  --port 1521
```

### Method 2: Using DCT API Directly

```python
import asyncio
from dct_mcp_server.dct_client.client import DCTAPIClient

async def create_oracle_source():
    client = DCTAPIClient(
        api_key="your-api-key",
        base_url="https://your-dct-engine.example.com",
        verify_ssl=False
    )
    
    source_config = {
        "name": "oracle-prod-source",
        "environment_id": "3-UNIX_HOST_ENVIRONMENT-1",
        "repository_id": "REPO-1",
        "hostname": "oracle-prod.example.com",
        "port": 1521,
        "instance_name": "ORCL",
        "oracle_home": "/u01/app/oracle/product/19c/db_1",
        "oracle_base": "/u01/app/oracle",
        "instance_owner": "oracle",
        "type": "OracleCompatible",
    }
    
    result = await client.post_resource("/sources", source_config)
    print(f"Source created: {result.get('id')}")
    await client.close()

asyncio.run(create_oracle_source())
```

### Method 3: Using MCP Tool Directly

```bash
# Enable the environment_source_tool in your MCP client configuration
# Then call:

environment_source_tool(
    action="create_oracle_source",
    name="oracle-prod-source",
    environment_id="3-UNIX_HOST_ENVIRONMENT-1",
    hostname="oracle-prod.example.com",
    port=1521,
    instance_name="ORCL",
    oracle_home="/u01/app/oracle/product/19c/db_1",
    oracle_base="/u01/app/oracle",
    instance_owner="oracle"
)
```

## Verification Steps

After creating the Oracle source:

1. **Verify JDBC Connection**
   ```bash
   environment_source_tool(
       action="verify_source_jdbc_connection",
       source_id="3-SOURCE-123"
   )
   ```

2. **Check Source Status**
   ```bash
   environment_source_tool(
       action="get_source",
       source_id="3-SOURCE-123"
   )
   ```

3. **Review Source Details**
   - Name and hostname
   - Instance name and port
   - Oracle home location
   - Status: Should be "LINKED" or "ACTIVE"

## Troubleshooting

### "Unable to connect to Oracle database"
- Verify network connectivity: `telnet oracle-prod.example.com 1521`
- Check listener status on source host: `lsnrctl status`
- Verify database credentials
- Check firewall rules

### "RMAN backup failed"
- Verify Oracle home and RMAN binaries: `$ORACLE_HOME/bin/rman`
- Check Archive Log Mode: `SELECT log_mode FROM v$database;`
- Verify backup destination space
- Check RMAN configuration: `SHOW ALL;` in RMAN

### "TDE (Transparent Data Encryption) not supported"
- Verify TDE wallet location and permissions
- Check wallet is open: `SELECT * FROM v$encryption_wallet;`
- Verify keystore type matches configuration

### "Staging environment credentials invalid"
- Verify OS user exists and can SSH to staging host
- Check sudo privileges if needed for Oracle operations
- Verify database user exists on staging database
- Test connectivity manually first

## Example Configurations

### Standard Single-Instance Configuration

```yaml
source:
  hostname: db1.company.com
  instance_name: PROD
  oracle_home: /u01/app/oracle/product/19c/db_1
  oracle_base: /u01/app/oracle

staging:
  hostname: db2.company.com
  environment_user: delphix_os

dct_parameters:
  sourceType: Continuous Data Admin
  rman_channels: 4
  logsync_enabled: true
```

### RAC (Real Application Cluster) Configuration

```yaml
source:
  hostname: rac-node1.company.com
  is_cluster: true
  cluster_address: rac-scan.company.com
  cluster_user: oracle
  oracle_cluster_node_name: rac1
  instance_name: PROD1

dct_parameters:
  rman_channels: 8
  number_of_connections: 8
```

### TDE-Enabled Database Configuration

```yaml
dct_parameters:
  tde_enabled: true
  tde_keystore_config_type: FILE
  tde_keystores_root_path: /u01/app/oracle/admin/PROD/wallet
```

## Next Steps

After successfully creating the Oracle source:

1. **Create a dSource** to enable continuous data replication
2. **Provision Virtual Databases (VDBs)** for development/testing
3. **Configure Snapshots** and retention policies
4. **Set up Compliance** policies if required
5. **Monitor** the dSource health and sync status

## References

- [DCT API Documentation](https://docs.delphix.com)
- [Oracle Database Documentation](https://docs.oracle.com)
- [RMAN Backup and Recovery](https://docs.oracle.com/en/database/oracle/oracle-database/19/bradv/)
- [Delphix Continuous Data Support Matrix](https://docs.delphix.com/continuous-data-platform/)
