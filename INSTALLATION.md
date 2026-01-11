# Installation and Setup Guide

## Prerequisites

### 1. Python Requirements
- Python 3.8 or higher
- pip package manager

### 2. Oracle Instant Client (Optional - Required Only for Some Features)

**When Oracle Client is Required** (Thick Mode):
- PDB Clone operations (requires database links)
- External authentication (OS authentication / Oracle Wallet)
- Advanced Oracle features

**When Oracle Client is NOT Required** (Thin Mode):
- DB Health Check with username/password authentication
- Direct connections using hostname/port/service

The toolkit automatically uses **Thin Mode** when connecting with username/password, which requires no Oracle Client installation. For PDB clone operations and external authentication, Oracle Instant Client in **Thick Mode** is required.

#### Windows Installation

**Option A: Download Oracle Instant Client**

1. Download Oracle Instant Client from:
   https://www.oracle.com/database/technologies/instant-client/downloads.html

2. Choose the appropriate version (19c or 21c recommended)

3. Extract to a directory, for example:
   - `C:\oracle\instantclient_19_8`
   - `C:\oracle\instantclient_21_3`

4. Add the directory to your PATH environment variable:
   ```cmd
   setx PATH "%PATH%;C:\oracle\instantclient_19_8"
   ```

**Option B: Use Existing Oracle Client**

If you have Oracle Database Client already installed:
1. Set `ORACLE_HOME` environment variable
2. The toolkit will automatically detect it

#### Linux Installation

```bash
# Download Instant Client
wget https://download.oracle.com/otn_software/linux/instantclient/instantclient-basic-linux.x64-21.1.0.0.0.zip

# Extract
unzip instantclient-basic-linux.x64-21.1.0.0.0.zip -d /opt/oracle

# Set environment variables
export LD_LIBRARY_PATH=/opt/oracle/instantclient_21_1:$LD_LIBRARY_PATH
```

### 3. External Authentication Setup

The toolkit uses **external authentication** (no passwords required).

#### Option A: OS Authentication (Windows)

1. Create Oracle user with OS authentication:
   ```sql
   -- On Oracle Database, as SYSDBA
   CREATE USER ops$DOMAIN\USERNAME IDENTIFIED EXTERNALLY;
   GRANT CONNECT, RESOURCE, DBA TO ops$DOMAIN\USERNAME;
   ```

2. Configure `sqlnet.ora`:
   ```
   SQLNET.AUTHENTICATION_SERVICES = (NTS)
   ```

3. Test connection:
   ```cmd
   sqlplus /@your_tns_alias
   ```

#### Option B: Oracle Wallet

1. Create wallet directory:
   ```cmd
   mkdir C:\oracle\wallet
   ```

2. Create wallet:
   ```cmd
   mkstore -wrl C:\oracle\wallet -create
   ```

3. Add credentials:
   ```cmd
   mkstore -wrl C:\oracle\wallet -createCredential your_tns_alias username password
   ```

4. Configure `sqlnet.ora`:
   ```
   WALLET_LOCATION = (SOURCE = (METHOD = FILE) (METHOD_DATA = (DIRECTORY = C:\oracle\wallet)))
   SQLNET.WALLET_OVERRIDE = TRUE
   ```

## Installation Steps

### 1. Install Python Dependencies

```bash
cd C:\Users\user\Desktop\Oracle\PDB
pip install -r requirements.txt
```

### 2. Verify Oracle Client Installation

Run Python and test:
```python
import oracledb
oracledb.init_oracle_client(lib_dir=r"C:\oracle\instantclient_19_8")
print("Oracle Client initialized successfully")
```

### 3. Configure TNS Names

Edit `tnsnames.ora` (typically in `C:\oracle\instantclient_19_8\network\admin\`):

```
PROD_CDB =
  (DESCRIPTION =
    (ADDRESS = (PROTOCOL = TCP)(HOST = prod-scan.example.com)(PORT = 1521))
    (CONNECT_DATA =
      (SERVER = DEDICATED)
      (SERVICE_NAME = PROD_CDB)
    )
  )

DEV_CDB =
  (DESCRIPTION =
    (ADDRESS = (PROTOCOL = TCP)(HOST = dev-scan.example.com)(PORT = 1521))
    (CONNECT_DATA =
      (SERVER = DEDICATED)
      (SERVICE_NAME = DEV_CDB)
    )
  )
```

### 4. Test Database Connectivity

```bash
# Test with SQL*Plus
sqlplus /@PROD_CDB

# Should connect without prompting for password
```

### 5. Run the Application

```bash
python oracle_pdb_toolkit.py
```

## Troubleshooting

### Error: "DPY-4001: no credentials specified"

**Cause**: Oracle Client is not in Thick Mode or external auth is not configured.

**Solution**:
1. Verify Oracle Instant Client is installed
2. Check that `oracledb.init_oracle_client()` succeeds
3. Verify external authentication is configured (OS auth or wallet)

### Error: "DPI-1047: Cannot locate a 64-bit Oracle Client library"

**Cause**: Oracle Instant Client DLLs not found.

**Solution**:
1. Install Oracle Instant Client
2. Add to PATH or specify `lib_dir` in code
3. Ensure 64-bit Python matches 64-bit Oracle Client

### Error: "ORA-12154: TNS:could not resolve the connect identifier"

**Cause**: TNS alias not found in `tnsnames.ora`.

**Solution**:
1. Create `tnsnames.ora` in correct location
2. Set `TNS_ADMIN` environment variable:
   ```cmd
   setx TNS_ADMIN "C:\oracle\instantclient_19_8\network\admin"
   ```

### Error: "ORA-01017: invalid username/password"

**Cause**: External authentication not configured correctly.

**Solution**:
1. Verify OS authentication is enabled on database
2. Check user exists with `IDENTIFIED EXTERNALLY`
3. Verify `SQLNET.AUTHENTICATION_SERVICES = (NTS)` in `sqlnet.ora`

## Verification Checklist

Before running the toolkit, verify:

- [ ] Python 3.8+ installed
- [ ] `pip install -r requirements.txt` completed
- [ ] Oracle Instant Client installed
- [ ] Oracle Client added to PATH or `lib_dir` configured
- [ ] `tnsnames.ora` configured with your database aliases
- [ ] External authentication configured (OS auth or wallet)
- [ ] Can connect via SQL*Plus without password: `sqlplus /@your_alias`
- [ ] User has necessary privileges for CDB and PDB operations

## Recommended Database Privileges

The user should have the following privileges:

```sql
-- Minimum privileges for read-only operations (health check, precheck, postcheck)
GRANT SELECT ON v_$instance TO your_user;
GRANT SELECT ON v_$database TO your_user;
GRANT SELECT ON v_$pdbs TO your_user;
GRANT SELECT ON v_$parameter TO your_user;
GRANT SELECT ON v_$session TO your_user;
GRANT SELECT ON v_$system_event TO your_user;
GRANT SELECT ON v_$encryption_wallet TO your_user;
GRANT SELECT ON dba_tablespace_usage_metrics TO your_user;
GRANT SELECT ON dba_registry TO your_user;
GRANT SELECT ON database_properties TO your_user;
GRANT SELECT ON nls_database_parameters TO your_user;
GRANT SELECT ON cdb_services TO your_user;
GRANT SELECT ON pdb_plug_in_violations TO your_user;

-- Additional privileges for PDB clone operations
GRANT CREATE PLUGGABLE DATABASE TO your_user;
GRANT ALTER PLUGGABLE DATABASE TO your_user;
GRANT CREATE DATABASE LINK TO your_user;
GRANT DROP DATABASE LINK TO your_user;
GRANT EXECUTE ON dbms_pdb TO your_user;

-- For full DBA operations
GRANT DBA TO your_user;
```

## Quick Start Example

After installation:

```bash
# 1. Start the application
python oracle_pdb_toolkit.py

# 2. Go to "DB Health Check" tab
#    - Enter database alias: PROD_CDB
#    - Click "Generate Health Report"

# 3. Go to "PDB Clone" tab
#    - Fill in source and target information
#    - Click "Run Precheck"
#    - Review HTML report
#    - Click "Execute PDB Clone" if precheck passes
#    - Click "Run Postcheck" after clone completes
```

## Support

For issues:
1. Check Oracle alert log for database errors
2. Verify connectivity with SQL*Plus first
3. Review application output for detailed error messages
4. Ensure all prerequisites are met

## Additional Resources

- Oracle Instant Client: https://www.oracle.com/database/technologies/instant-client.html
- Oracle Wallet: https://docs.oracle.com/en/database/oracle/oracle-database/19/dbseg/configuring-secure-external-password-store.html
- Oracle Multitenant: https://docs.oracle.com/en/database/oracle/oracle-database/19/multi/index.html
