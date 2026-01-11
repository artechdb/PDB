# Quick Start Guide

## ✅ Setup Complete!

Your Oracle Client has been detected at:
```
C:\Users\user\Downloads\WINDOWS.X64_213000_client_home\bin
```

The toolkit will automatically detect your ORACLE_HOME environment variable on any computer.

## Launch the Application

```bash
python oracle_pdb_toolkit.py
```

## Before First Use

### 1. Verify External Authentication

Test your database connection without the GUI:

```bash
# Test with SQL*Plus (should NOT ask for password)
sqlplus /@YOUR_TNS_ALIAS

# Or use the test script
python test_connection.py
```

### 2. Configure External Authentication

If you haven't configured external authentication yet, choose one option:

#### Option A: OS Authentication (Recommended for Windows)

On your Oracle Database (as SYSDBA):
```sql
-- Replace DOMAIN\USERNAME with your actual Windows domain and username
CREATE USER ops$DOMAIN\USERNAME IDENTIFIED EXTERNALLY;
GRANT CREATE SESSION, SELECT ANY DICTIONARY TO ops$DOMAIN\USERNAME;
GRANT CREATE PLUGGABLE DATABASE, ALTER PLUGGABLE DATABASE TO ops$DOMAIN\USERNAME;
GRANT CREATE DATABASE LINK, DROP DATABASE LINK TO ops$DOMAIN\USERNAME;
GRANT EXECUTE ON DBMS_PDB TO ops$DOMAIN\USERNAME;

-- For full DBA operations
GRANT DBA TO ops$DOMAIN\USERNAME;
```

Configure `sqlnet.ora` (in `%ORACLE_HOME%\network\admin\`):
```
SQLNET.AUTHENTICATION_SERVICES = (NTS)
```

#### Option B: Oracle Wallet

Create and configure a wallet:
```cmd
mkdir C:\oracle\wallet
mkstore -wrl C:\oracle\wallet -create
mkstore -wrl C:\oracle\wallet -createCredential YOUR_TNS_ALIAS username password
```

Configure `sqlnet.ora`:
```
WALLET_LOCATION = (SOURCE = (METHOD = FILE) (METHOD_DATA = (DIRECTORY = C:\oracle\wallet)))
SQLNET.WALLET_OVERRIDE = TRUE
```

### 3. Configure TNS Names

Edit `tnsnames.ora` (in `%ORACLE_HOME%\network\admin\` or `%TNS_ADMIN%`):

```
PROD_CDB =
  (DESCRIPTION =
    (ADDRESS = (PROTOCOL = TCP)(HOST = prod-db-scan.example.com)(PORT = 1521))
    (CONNECT_DATA =
      (SERVER = DEDICATED)
      (SERVICE_NAME = PROD_CDB)
    )
  )

DEV_CDB =
  (DESCRIPTION =
    (ADDRESS = (PROTOCOL = TCP)(HOST = dev-db-scan.example.com)(PORT = 1521))
    (CONNECT_DATA =
      (SERVER = DEDICATED)
      (SERVICE_NAME = DEV_CDB)
    )
  )
```

## Using the Toolkit

### Health Check

The health check supports two connection methods:

#### Option A: External Authentication (Thick Mode)

**Method 1: Using TNS Alias**
1. Go to **"DB Health Check"** tab
2. Select **"External Authentication (OS Auth / Wallet)"**
3. Enter **TNS Alias** (e.g., `PROD_CDB`)
4. Click **"Generate Health Report"**
5. Review the HTML report generated in the current directory

**Method 2: Using Hostname/Port (No TNS Configuration Needed)**
1. Go to **"DB Health Check"** tab
2. Select **"External Authentication (OS Auth / Wallet)"**
3. Leave TNS Alias empty
4. Fill in:
   - **Hostname**: `dbserver.example.com`
   - **Port**: `1521`
   - **Service Name**: `PROD_CDB`
5. Click **"Generate Health Report"**
6. Review the HTML report generated in the current directory

**Note**: External auth works with both TNS aliases and direct hostname/port connections!

#### Option B: Username/Password (Thin Mode - No Oracle Client Required)
1. Go to **"DB Health Check"** tab
2. Select **"Username / Password"**
3. Fill in connection details:
   - **Hostname**: `dbserver.example.com` or IP address
   - **Port**: `1521` (default, adjust if needed)
   - **Service Name**: `ORCL` or `orcl_high`
   - **Username**: `system` or your database user
   - **Password**: Your password (not stored)
4. Click **"Generate Health Report"**
5. Review the HTML report generated in the current directory

**Note**: Username/password mode works without Oracle Client installation (uses Thin Mode), making it perfect for quick health checks from any computer.

### PDB Clone Workflow

#### Step 1: Precheck

1. Go to **"PDB Clone"** tab
2. Fill in configuration:
   - **Source CDB**: `PROD_CDB`
   - **Source PDB**: `PRODPDB`
   - **Source SCAN Host**: `prod-scan.example.com` (optional)
   - **Target CDB**: `DEV_CDB`
   - **Target PDB**: `DEVPDB`
   - **Target SCAN Host**: `dev-scan.example.com` (optional)
3. Click **"Run Precheck"**
4. Review the validation report
5. **Ensure all checks show PASS** before proceeding

#### Step 2: Execute Clone

1. After precheck passes, click **"Execute PDB Clone"**
2. Confirm the operation
3. Wait for completion (may take several minutes)
4. Check the output log for progress

#### Step 3: Postcheck

1. Click **"Run Postcheck"**
2. Review the postcheck report
3. Verify all parameters match between source and target

## HTML Reports

All reports are saved in the current directory with timestamps:

- `db_health_report_YYYYMMDD_HHMMSS.html`
- `pdb_validation_report_YYYYMMDD_HHMMSS.html` (precheck)
- `pdb_postcheck_report_YYYYMMDD_HHMMSS.html`

Reports use the `report_styles.css` file for professional styling.

## Common Issues

### "DPY-4001: no credentials specified"

**Cause**: External authentication is not configured.

**Fix**:
1. Configure OS authentication or Oracle Wallet (see above)
2. Test with: `sqlplus /@YOUR_TNS_ALIAS`
3. Should connect without password prompt

### "ORA-12154: TNS:could not resolve the connect identifier"

**Cause**: TNS alias not found.

**Fix**:
1. Check `tnsnames.ora` exists and contains your alias
2. Verify `TNS_ADMIN` environment variable points to correct directory
3. Or place `tnsnames.ora` in `%ORACLE_HOME%\network\admin\`

### "ORA-01017: invalid username/password"

**Cause**: External authentication not working.

**Fix**:
1. Verify user exists with `IDENTIFIED EXTERNALLY`
2. Check `SQLNET.AUTHENTICATION_SERVICES = (NTS)` in `sqlnet.ora`
3. Restart SQL*Net listener if needed

### Precheck Shows FAILED Status

Review the specific validation that failed:

- **Version mismatch**: Source and target must be same version/patch
- **Character set**: Target must support source character set
- **TDE mismatch**: Both must use same encryption method
- **Local undo disabled**: Enable local undo mode on both CDBs
- **Plug-in violations**: Review violation details in report

## Portability

The toolkit is fully portable and will work on any computer with:

✅ **Automatically detected**:
- Reads `ORACLE_HOME` environment variable
- Searches common Oracle Client installation paths
- Works with any Oracle Client version (19c, 21c, 23ai)

✅ **No hardcoded paths**:
- All paths use environment variables
- Works across different computers
- Compatible with different Oracle Client locations

## Support Files

- **[README.md](README.md)**: Full documentation
- **[INSTALLATION.md](INSTALLATION.md)**: Detailed installation guide
- **[test_connection.py](test_connection.py)**: Connection diagnostic tool
- **[report_styles.css](report_styles.css)**: HTML report styling

## Need Help?

1. Run diagnostic: `python test_connection.py`
2. Check application output log for errors
3. Review Oracle alert log for database-side errors
4. Consult [INSTALLATION.md](INSTALLATION.md) for detailed troubleshooting

## Example Session

```bash
# 1. Test connection
python test_connection.py

# 2. Launch application
python oracle_pdb_toolkit.py

# 3. Perform health check
#    - Tab: DB Health Check
#    - Database: PROD_CDB
#    - Click: Generate Health Report

# 4. Clone a PDB
#    - Tab: PDB Clone
#    - Source: PROD_CDB / PRODPDB
#    - Target: DEV_CDB / DEVPDB
#    - Click: Run Precheck → Execute PDB Clone → Run Postcheck
```

## Tips

- Always run **Precheck** before cloning
- Review validation reports carefully
- Keep reports for audit trail
- Test in non-production first
- Ensure adequate disk space on target
- Close source PDB users during clone if possible

Enjoy your Oracle PDB Management Toolkit! 🎉
