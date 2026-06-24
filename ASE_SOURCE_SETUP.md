# ASE Source Configuration Setup Guide

This guide explains how to create and configure an Adaptive Server Enterprise (ASE/Sybase) source (dSource) in Delphix Data Control Tower (DCT) using the MCP server.

## Overview

An ASE source configuration establishes a link between a production ASE database and DCT, enabling:
- Continuous data synchronization via native ASE replication
- Virtual database (VDB) provisioning from snapshots
- Time-travel recovery to any point in transaction history
- Support for ASE versions 15.x, 16.x, and later

## Prerequisites

Before creating an ASE source, you need:

1. **Source ASE Database**
   - Sybase ASE 15.x, 16.x, or later
   - SSH/Telnet access to the host running ASE
   - System Administrator (SA) or System Security Officer (SSO) privileges
   - Database in SIMPLE or FULL recovery model
   - Transaction log backups enabled
   - Replication agent running (for log-based replication)

2. **Staging/Target Environment**
   - UNIX-based OS (Linux, AIX, Solaris) or Windows
   - ASE software installed (same or compatible version as source)
   - At least 300GB free space for staging database
   - Network connectivity to source database (port 5000 or configured port)
   - Delphix-managed OS user account (e.g., `delphix_os`)

3. **DCT Setup**
   - Engine running and accessible
   - Environment created for source ASE host
   - Environment created for staging/target host
   - Environment user credentials configured

## Configuration Parameters

### Source Database Configuration

```yaml
source:
  hostname: ase-prod.example.com
  port: 5000
  server_name: ASE_PROD
  database_type: ASE
  
  # ASE software locations
  sybase_home: /opt/sybase/ASE-16_0
  sybase_ocs: /opt/sybase/OCS-16_0
  ase_user: sybase
  
  # Connection method
  interfaces_file: /opt/sybase/interfaces
  character_set: utf8
  language: us_english
```

### Staging/Target Configuration

```yaml
staging:
  hostname: ase-staging.example.com
  environment_id: 3-UNIX_HOST_ENVIRONMENT-1
  
  # Delphix OS user
  environment_user: delphix_os
  environment_user_id: ENVIRONMENT_USER-1
  
  # ASE software on staging
  sybase_home: /opt/sybase/ASE-16_0
  sybase_ocs: /opt/sybase/OCS-16_0
  
  # Staging ASE instance
  staging_server_name: ASE_STG
  staging_port: 5000
```

### Credentials

```yaml
credentials:
  # Source database credentials
  source_db_user: sa
  source_db_password: SecurePassword123!
  
  # Staging environment OS access
  staging_os_user: delphix_os
  staging_os_password: OsPassword123!
  
  # Staging database credentials
  staging_db_user: sa
  staging_db_password: SecurePassword123!
```

### DCT Integration Parameters

```yaml
dct_parameters:
  # Source type: determines replication method
  sourceType: "Continuous Data Admin"  # or "Self-Service"
  
  # Automatic resync on divergence
  resync: true
  
  # Log-based replication configuration
  log_sync_enabled: true
  log_sync_interval: 10  # seconds
  
  # Network optimization
  number_of_connections: 4
  bandwidth_limit: 500  # MB/s
  
  # Compression and encryption
  compressed_linking_enabled: false
  encrypted_linking_enabled: false
  
  # ASE-specific options
  recovery_model: FULL
  dump_database_enabled: true
```

## Creating an ASE Source

### Method 1: Using the Python Script

```bash
# Set up environment variables
export DCT_API_KEY="your-api-key"
export DCT_BASE_URL="https://your-dct-engine.example.com"

# Run the creation script with defaults
python3 create_ase_source.py

# Or with custom parameters
python3 create_ase_source.py \
  --source-name "prod-ase-src" \
  --hostname "ase-prod.example.com" \
  --server-name "ASE_PROD" \
  --sybase-home "/opt/sybase/ASE-16_0" \
  --port 5000
```

### Method 2: Using DCT API Directly

```python
import asyncio
from dct_mcp_server.dct_client.client import DCTAPIClient

async def create_ase_source():
    client = DCTAPIClient(
        api_key="your-api-key",
        base_url="https://your-dct-engine.example.com",
        verify_ssl=False
    )
    
    source_config = {
        "name": "ase-prod-source",
        "environment_id": "3-UNIX_HOST_ENVIRONMENT-1",
        "repository_id": "REPO-1",
        "hostname": "ase-prod.example.com",
        "port": 5000,
        "server_name": "ASE_PROD",
        "sybase_home": "/opt/sybase/ASE-16_0",
        "sybase_ocs": "/opt/sybase/OCS-16_0",
        "ase_user": "sybase",
        "type": "ASE",
    }
    
    result = await client.post_resource("/sources", source_config)
    print(f"Source created: {result.get('id')}")
    await client.close()

asyncio.run(create_ase_source())
```

### Method 3: Using MCP Tool Directly

```bash
# Enable the environment_source_tool in your MCP client configuration
# Then call:

environment_source_tool(
    action="create_ase_source",
    name="ase-prod-source",
    environment_id="3-UNIX_HOST_ENVIRONMENT-1",
    hostname="ase-prod.example.com",
    port=5000,
    server_name="ASE_PROD",
    sybase_home="/opt/sybase/ASE-16_0",
    sybase_ocs="/opt/sybase/OCS-16_0",
    ase_user="sybase"
)
```

## Verification Steps

After creating the ASE source:

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
   - Server name and port
   - ASE home location
   - Status: Should be "LINKED" or "ACTIVE"

4. **Test Database Connectivity**
   ```bash
   # From the staging host
   isql -S ASE_PROD -U sa -P password
   ```

## Troubleshooting

### "Unable to connect to ASE database"
- Verify network connectivity: `telnet ase-prod.example.com 5000`
- Check ASE is running: `ps -ef | grep dataserver`
- Verify interfaces file exists: `cat /opt/sybase/interfaces`
- Check database credentials and permissions
- Verify firewall rules allow port 5000

### "Replication agent not running"
- Start replication agent: `startrepagent -S ASE_PROD`
- Check agent status: `sp_helprepagent`
- Verify replication is enabled on database

### "Transaction log backup failed"
- Verify transaction log device exists: `sp_helpdevice`
- Check disk space available for log backups
- Verify database is in FULL recovery mode: `sp_helpdb <database_name>`

### "Staging environment credentials invalid"
- Verify OS user exists and can SSH to staging host
- Check sudo privileges if needed for ASE operations
- Verify ASE user has write permissions to data/log directories
- Test connectivity manually first: `isql -S ASE_STG -U sa`

## Example Configurations

### Standard Single-Instance Configuration

```yaml
source:
  hostname: db1.company.com
  server_name: ASE_PROD
  port: 5000
  sybase_home: /opt/sybase/ASE-16_0
  sybase_ocs: /opt/sybase/OCS-16_0

staging:
  hostname: db2.company.com
  staging_server_name: ASE_STG
  environment_user: delphix_os

dct_parameters:
  sourceType: Continuous Data Admin
  recovery_model: FULL
  log_sync_enabled: true
  log_sync_interval: 10
```

### Clustered ASE Configuration (ESD - Extended Server Deployment)

```yaml
source:
  hostname: ase-cluster-1.company.com
  server_name: ASE_PROD_1
  cluster_server_name: ASE_PROD
  is_cluster: true
  cluster_virtual_hostname: ase-virtual.company.com
  port: 5000

dct_parameters:
  sourceType: Continuous Data Admin
  cluster_aware: true
  failover_enabled: true
```

### High-Volume Database Configuration

```yaml
dct_parameters:
  number_of_connections: 8
  bandwidth_limit: 1000
  compressed_linking_enabled: true
  dump_database_enabled: true
  dump_parallel_count: 4
```

## Next Steps

After successfully creating the ASE source:

1. **Create a dSource** to enable continuous data replication
2. **Configure log backups** for transaction log shipping
3. **Provision Virtual Databases (VDBs)** for development/testing
4. **Configure Snapshots** and retention policies
5. **Set up Compliance** policies if required
6. **Monitor** the dSource health and sync status

## References

- [DCT API Documentation](https://docs.delphix.com)
- [Sybase ASE Documentation](https://infocenter.sybase.com)
- [Delphix Continuous Data Support Matrix](https://docs.delphix.com/continuous-data-platform/)
- [ASE System Administration Guide](https://infocenter.sybase.com/help/index.jsp?topic=/com.sybase.infocenter.dc32710.1610/doc/html/an11258.htm)
