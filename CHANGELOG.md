# Oracle PDB Toolkit - Change Log

## Version 1.2.5 - 2026-01-10

### Enhancement: PDB Size Display in Reports

#### Feature
- Added total database size display for both source and target PDBs
- Shows size in GB (gigabytes) in Section 1: Connection Metadata
- Calculates size from v$datafile view using con_id lookup
- **Implementation**:
  - Precheck data gathering: [oracle_pdb_toolkit.py:264-281](oracle_pdb_toolkit.py#L264-L281)
  - Postcheck data gathering: [oracle_pdb_toolkit.py:1103-1120](oracle_pdb_toolkit.py#L1103-L1120)
  - Precheck report display: [oracle_pdb_toolkit.py:1358-1362](oracle_pdb_toolkit.py#L1358-L1362)
  - Postcheck report display: [oracle_pdb_toolkit.py:1550-1554](oracle_pdb_toolkit.py#L1550-L1554)

#### Report Display (Precheck)
```
Section 1: Connection Metadata

Component              Source                   Target
CDB                    PROD_CDB                 DEV_CDB
PDB                    PRODPDB                  DEVPDB
Instance Information
Instance 1             Instance 1: PROD1 @ host1  Instance 1: DEV1 @ host2
PDB Size Information
PDB Total Size (GB)    45.73 GB                 N/A (PDB not created yet)
```

#### Report Display (Postcheck)
```
PDB Size Information
PDB Total Size (GB)    45.73 GB                 45.73 GB
```

#### Benefits
- Instant visibility of PDB storage requirements
- Capacity planning before clone operations
- Documentation of PDB sizes at time of validation
- Helps identify size discrepancies between source and target

---

### Enhancement: MAX_STRING_SIZE Compatibility Check

#### Feature
- Added validation check for MAX_STRING_SIZE parameter compatibility
- Compares source and target CDB settings
- Prevents clone failures due to VARCHAR2/NVARCHAR2/RAW size mismatches
- **Implementation**: [oracle_pdb_toolkit.py:434-450](oracle_pdb_toolkit.py#L434-L450)

#### Report Display
```
Section 2: Verification Checks

Check                              Status    Source Value    Target Value
MAX_STRING_SIZE Compatibility      PASS      EXTENDED        EXTENDED
```

#### Why This Matters
| Setting | VARCHAR2 Max Size | Compatibility |
|---------|-------------------|---------------|
| STANDARD | 4000 bytes | Traditional Oracle limit |
| EXTENDED | 32767 bytes | Oracle 12c+ extended types |

**Critical**: Source EXTENDED + Target STANDARD = Clone will FAIL

#### Actions on FAILED Status
1. Set target CDB to EXTENDED mode
2. Run utl32k.sql script on target
3. Recompile invalid objects
4. Retry PDB clone operation

---

### Enhancement: Timezone Setting Compatibility Check

#### Feature
- Added validation check for database timezone settings
- Compares DBTIMEZONE between source and target
- Ensures TIMESTAMP WITH LOCAL TIME ZONE data consistency
- **Implementation**: [oracle_pdb_toolkit.py:452-467](oracle_pdb_toolkit.py#L452-L467)

#### Report Display
```
Section 2: Verification Checks

Check                              Status    Source Value    Target Value
Timezone Setting Compatibility     PASS      +00:00          +00:00
```

#### Why This Matters
- TIMESTAMP WITH LOCAL TIME ZONE columns use database timezone
- Mismatched timezones cause data display inconsistencies
- Application behavior may change with different timezone settings
- Date/time arithmetic depends on database timezone

#### Common Timezone Values
- `+00:00` - UTC (recommended for global applications)
- `-05:00` - US Eastern Standard Time
- `+01:00` - Central European Time
- `US/Pacific` - Named timezone region

#### Actions on FAILED Status
```sql
-- On target CDB (before clone)
ALTER DATABASE SET TIME_ZONE = '+00:00';
```

**Note**: Changing DBTIMEZONE requires downtime and may affect existing data

---

### Enhancement: MAX_PDB_STORAGE Limit Check

#### Feature
- Added validation check for target CDB PDB storage limits
- Compares source PDB size against target MAX_PDB_STORAGE setting
- Queries `database_properties` view (not `v$parameter`)
- Prevents clone failures due to insufficient storage quota
- Supports G (GB), M (MB), T (TB) units and UNLIMITED
- **Implementation**: [oracle_pdb_toolkit.py:469-521](oracle_pdb_toolkit.py#L469-L521)

#### Report Display Examples

**Example 1: UNLIMITED (PASS)**
```
Check                         Status    Source Value    Target Value
MAX_PDB_STORAGE Limit         PASS      45.73 GB        UNLIMITED (sufficient for 45.73 GB source PDB)
```

**Example 2: Sufficient Storage (PASS)**
```
Check                         Status    Source Value    Target Value
MAX_PDB_STORAGE Limit         PASS      45.73 GB        100G (sufficient for 45.73 GB source PDB)
```

**Example 3: Insufficient Storage (FAILED)**
```
Check                         Status    Source Value    Target Value
MAX_PDB_STORAGE Limit         FAILED    45.73 GB        20G (insufficient for 45.73 GB source PDB)
```

**Example 4: Not Configured (PASS)**
```
Check                         Status    Source Value    Target Value
MAX_PDB_STORAGE Limit         PASS      45.73 GB        Not configured (unlimited)
```

#### Why This Matters
MAX_PDB_STORAGE (Oracle 19c+) limits maximum storage a PDB can consume:
- **Resource Control**: Prevent one PDB from consuming all CDB storage
- **Multi-Tenant Management**: Enforce storage quotas per tenant/PDB
- **Cost Management**: Limit PDB growth for billing/chargeback

**Critical**: Clone will FAIL with ORA-65114 if storage limit exceeded

#### Actions on FAILED Status
```sql
-- Option 1: Increase MAX_PDB_STORAGE for specific PDB
ALTER PLUGGABLE DATABASE devpdb STORAGE (MAXSIZE 100G);

-- Option 2: Set CDB-level default for all PDBs
ALTER SYSTEM SET max_pdb_storage = '100G' SCOPE=BOTH;

-- Option 3: Remove limit (set to unlimited)
ALTER PLUGGABLE DATABASE devpdb STORAGE (MAXSIZE UNLIMITED);
```

---

### Summary of Version 1.2.5 Enhancements

#### Four Major Features Added:
1. **PDB Size Display** - Section 1 now shows total database size for capacity planning
2. **MAX_STRING_SIZE Check** - Section 2 validates VARCHAR2/NVARCHAR2/RAW compatibility
3. **Timezone Check** - Section 2 ensures DBTIMEZONE consistency
4. **MAX_PDB_STORAGE Check** - Section 2 validates storage quota sufficiency

#### Benefits:
- ✅ Enhanced visibility of PDB characteristics
- ✅ Proactive detection of compatibility issues
- ✅ Better capacity planning and documentation
- ✅ Reduced clone failures during operations
- ✅ Comprehensive pre-validation before maintenance windows

#### Upgrade Notes:
- No configuration changes required
- All enhancements are automatic
- Backward compatible with existing reports
- New checks added to Section 2 validation results

---

## Version 1.2 - 2026-01-10

### Enhancement: Report Naming with Database Prefixes

#### DB Health Check Reports
- **Feature**: Added database name prefix to health check report filenames
- **Format**: `DATABASENAME_db_health_report_YYYYMMDD_HHMMSS.html`
- **Example**: `PROD_CDB_db_health_report_20260110_174408.html`
- **Implementation**: [oracle_pdb_toolkit.py:533](oracle_pdb_toolkit.py#L533)

#### PDB Clone Reports
- **Feature**: Added CDB/PDB name prefixes to clone operation reports
- **Precheck Format**: `SOURCECDB_SourcePDB_TARGETCDB_TargetPDB_pdb_validation_report_YYYYMMDD_HHMMSS.html`
- **Postcheck Format**: `SOURCECDB_SourcePDB_TARGETCDB_TargetPDB_pdb_postcheck_report_YYYYMMDD_HHMMSS.html`
- **Example**: `PROD_CDB_PRODPDB_DEV_CDB_DEVPDB_pdb_validation_report_20260110_175328.html`
- **Implementation**:
  - Precheck: [oracle_pdb_toolkit.py:622](oracle_pdb_toolkit.py#L622)
  - Postcheck: [oracle_pdb_toolkit.py:758](oracle_pdb_toolkit.py#L758)

### Enhancement: Instance Information in Reports

#### Feature
- Added instance names and hostnames to Section 1 of validation reports
- Uses `gv$instance` view to gather cluster/RAC information
- Shows all instances with their names and hostnames
- **Implementation**:
  - Precheck data gathering: [oracle_pdb_toolkit.py:242-257](oracle_pdb_toolkit.py#L242-L257)
  - Postcheck data gathering: [oracle_pdb_toolkit.py:680-695](oracle_pdb_toolkit.py#L680-L695)
  - Precheck report: [oracle_pdb_toolkit.py:910-930](oracle_pdb_toolkit.py#L910-L930)
  - Postcheck report: [oracle_pdb_toolkit.py:1060-1080](oracle_pdb_toolkit.py#L1060-L1080)

#### Report Display
```
Section 1: Connection Metadata
Component    Source                                    Target
CDB          PROD_CDB                                  DEV_CDB
PDB          PRODPDB                                   DEVPDB
Instance 1   Instance 1: PROD1 @ prod-host1.local     Instance 1: DEV1 @ dev-host1.local
Instance 2   Instance 2: PROD2 @ prod-host2.local     Instance 2: DEV2 @ dev-host2.local
```

### Enhancement: Target PDB Existence Check

#### Feature
- Added validation to check target PDB status
- Shows whether target PDB exists or is ready for clone
- Always shows PASS status with appropriate message
- **Implementation**: [oracle_pdb_toolkit.py:330-354](oracle_pdb_toolkit.py#L330-L354)

#### Check Results
- **PASS** with "PDB already exists (READ WRITE)": Target PDB exists and is open
- **PASS** with "PDB does not exist (ready for clone)": Ready for new clone

### Bug Fix: Source PDB Open Status Check

#### Issue
- Source PDB status check was showing "PDB not found" error
- Root cause: Case-sensitive PDB name matching

#### Solution
- Updated SQL query to use case-insensitive comparison
- Changed: `WHERE name = :pdb_name`
- To: `WHERE UPPER(name) = UPPER(:pdb_name)`
- **Implementation**: [oracle_pdb_toolkit.py:304-329](oracle_pdb_toolkit.py#L304-L329)

### Bug Fix: DBMS_PDB.DESCRIBE Compatibility Check

#### Issue
- Error: `ORA-06550: line 2, column 21: PLS-00306: wrong number or types of arguments in call to 'DESCRIBE'`
- Root cause: Different Oracle versions have different DBMS_PDB.DESCRIBE signatures
  - **Oracle 19c+**: `DESCRIBE(pdb_descr_xml OUT CLOB)` - Single CLOB parameter
  - **Oracle 12.1/12.2**: `DESCRIBE(pdb_descr_file VARCHAR2, pdb_name VARCHAR2)` - File-based approach

#### Solution (v1.2.2 - Final)
The toolkit now:
1. **Detects the Oracle version signature** by querying `all_arguments`
2. **Attempts 4 different calling methods** for maximum compatibility
3. **Gracefully skips file-based versions** (Oracle 12.1/12.2) with helpful user message

**File-Based Detection Logic**:
```python
# Check if this is file-based signature (Oracle 12.1/12.2)
is_file_based = False
if describe_signature:
    for arg in describe_signature:
        arg_name = arg[0] or 'RETURN_VALUE'
        # Check if first parameter is FILE path (VARCHAR2 IN)
        if arg[1] == 1 and 'FILE' in str(arg_name).upper() and arg[2] == 'VARCHAR2' and arg[3] == 'IN':
            is_file_based = True

if is_file_based:
    # Skip the check and provide manual instructions
    validation_results.append({
        'check': 'DBMS_PDB Plug Compatibility',
        'status': 'SKIPPED',
        'source_value': 'N/A',
        'target_value': 'File-based Oracle version (requires manual check)'
    })
```

**Why File-Based Cannot Be Automated**:
- File-based DBMS_PDB.DESCRIBE creates XML files on the **remote database server**
- Python client has no filesystem access to the remote server's DATA_PUMP_DIR
- Manual SQL*Plus access required for this Oracle version

**User Guidance Provided**:
When file-based signature is detected, the toolkit displays:
```
NOTICE: Your Oracle version uses file-based DBMS_PDB.DESCRIBE
NOTICE: This signature requires writing files to the remote database server,
NOTICE: which cannot be accessed from this Python client.
NOTICE: Skipping DBMS_PDB plug compatibility check.

RECOMMENDATION: Run the compatibility check manually using SQL*Plus:
  1. Connect to source PDB: sqlplus user/pass@host:port/pdb
  2. Run: EXEC DBMS_PDB.DESCRIBE(pdb_descr_file => 'pdb_desc.xml', pdb_name => 'PRODPDB');
  3. Connect to target CDB: sqlplus user/pass@host:port/cdb
  4. Run compatibility check using the XML file
```

#### Enhanced Debugging (v1.2.1)
- Added comprehensive debug logging to terminal output
- Queries exact DBMS_PDB.DESCRIBE signature from database
- Attempts 4 different calling methods automatically
- Exports XML to file for manual inspection (when successful)
- Shows container context verification
- Displays full error traces with stack traces
- File format: `{source_cdb}_{source_pdb}_pdb_describe_{timestamp}.xml`
- See [DEBUG_GUIDE.md](DEBUG_GUIDE.md) for troubleshooting guide

```python
# Connect directly to source PDB to run DBMS_PDB.DESCRIBE
source_pdb_dsn_temp = f"{source_scan}:{source_port}/{source_pdb}"

if connection_mode == 'external_auth':
    source_pdb_conn_temp = oracledb.connect(dsn=source_pdb_dsn_temp, externalauth=True)
else:
    source_user = self.params.get('source_username')
    source_pass = self.params.get('source_password')
    source_pdb_conn_temp = oracledb.connect(user=source_user, password=source_pass, dsn=source_pdb_dsn_temp)

source_pdb_cursor_temp = source_pdb_conn_temp.cursor()
xml_var = source_pdb_cursor_temp.var(oracledb.DB_TYPE_CLOB)

# DBMS_PDB.DESCRIBE has only ONE parameter: the OUT CLOB
source_pdb_cursor_temp.execute("""
    BEGIN
        DBMS_PDB.DESCRIBE(pdb_descr_xml => :xml_output);
    END;
""", xml_output=xml_var)

xml_clob = xml_var.getvalue()
source_pdb_cursor_temp.close()
source_pdb_conn_temp.close()
```

### Enhancement: Overall Precheck Status Display

#### Feature
- Added overall PASS/FAIL status to precheck validation report title
- Status displayed in green (PASS) or red (FAIL)
- PASS: All checks passed
- FAIL: Any check failed
- **Implementation**: [oracle_pdb_toolkit.py:624-638](oracle_pdb_toolkit.py#L624-L638)

#### Report Title Example
```html
<h1>PDB Clone Validation Report (Precheck) - <span class="pass">PASS</span></h1>
```

### Enhancement: CDB Parameters Comparison with Status Column

#### Feature
- Updated Section 3 title to "ORACLE CDB Parameters Comparison (Non-Default)"
- Added Status column showing SAME/DIFF for each parameter
- Color-coded rows: green for matching, red for differences
- **Implementation**: [oracle_pdb_toolkit.py:678-705](oracle_pdb_toolkit.py#L678-L705)

#### Table Structure
| Parameter Name | Source Value | Target Value | Status |
|----------------|--------------|--------------|--------|
| parameter_name | value1       | value2       | DIFF   |

### Enhancement: PDB Parameters Comparison Section

#### Feature
- Added new Section 4: "ORACLE PDB Parameters Comparison (Non-Default)"
- Shows PDB-level parameter differences
- Includes Status column (SAME/DIFF)
- Color-coded rows for easy identification
- **Implementation**: [oracle_pdb_toolkit.py:710-737](oracle_pdb_toolkit.py#L710-L737)

#### Precheck Behavior
- During precheck, target PDB doesn't exist yet
- Report shows source PDB parameters vs "N/A" for target
- All parameters marked as "DIFF" (expected behavior)
- Postcheck will show actual comparison after clone

### Enhancement: PDB Clone Connection Method Options

#### Feature: Flexible Connection Methods
- Added connection method selection (External Auth / Username & Password)
- Added hostname and port fields for direct connections
- Supports TNS-free connections using `hostname:port/service` format
- **Implementation**: [oracle_pdb_toolkit.py:998-1148](oracle_pdb_toolkit.py#L998-L1148)

#### Connection Options

**Option 1: External Authentication**
- Uses OS authentication or Oracle Wallet
- Requires Oracle Instant Client (Thick Mode)
- Connection format: `hostname:port/service`
- No password entry required

**Option 2: Username/Password**
- Direct credential authentication
- Works in Thin Mode (no Oracle Client needed)
- Connection format: `hostname:port/service`
- Passwords not stored

#### GUI Elements Added
- Radio buttons for connection method selection
- Hostname fields (Source SCAN Host, Target SCAN Host)
- Port fields (default: 1521)
- Service name fields (CDB and PDB)
- Username/Password fields (conditionally displayed)

#### Connection Formats Used
- Source CDB: `source_scan_host:port/source_cdb`
- Source PDB: `source_scan_host:port/source_pdb`
- Target CDB: `target_scan_host:port/target_cdb`
- Target PDB: `target_scan_host:port/target_pdb`

### Bug Fix: PDB Connection Format and Parameter Gathering

#### Issues Fixed
1. **Source PDB Open Status** showing "PDB not found"
2. **DBMS_PDB Plug Compatibility** failing with `ORA-06550: PLS-00306: wrong number or types of arguments`

#### Root Cause
- Queries for PDB information were failing because they assumed PDB services didn't exist
- Code was not using the correct connection format

#### Solution
All database connections now use the hostname:port/service format as specified:

**CDB Connections:**
- Source CDB: `source_scan_host:port/source_cdb`
- Target CDB: `target_scan_host:port/target_cdb`

**PDB Connections:**
- Source PDB: `source_scan_host:port/source_pdb`
- Target PDB: `target_scan_host:port/target_pdb`

**Key Changes:**
- **NO ALTER SESSION SET CONTAINER** used anywhere
- **Direct PDB connections** using PDB name as service name (standard Oracle behavior)
- **Precheck**: Connects to CDB for validation queries, connects to source PDB for parameters
- **Postcheck**: Connects to both source and target PDBs directly for parameter comparison

**Implementation**:
- Precheck: [oracle_pdb_toolkit.py:457-484](oracle_pdb_toolkit.py#L457-L484)
- Postcheck: [oracle_pdb_toolkit.py:458-499](oracle_pdb_toolkit.py#L458-L499)

#### Code Changes
**Before** (caused error):
```python
source_cursor.execute(f"ALTER SESSION SET CONTAINER = {source_pdb}")
target_cursor.execute(f"ALTER SESSION SET CONTAINER = {target_pdb}")  # FAILS!
```

**After** (fixed):
```python
# Connect directly to source PDB
source_pdb_dsn = f"{source_scan}:{source_port}/{source_pdb}"
source_pdb_conn = oracledb.connect(dsn=source_pdb_dsn, externalauth=True)
# Or with credentials:
source_pdb_conn = oracledb.connect(user=user, password=pass, dsn=source_pdb_dsn)

# Get source PDB parameters
source_pdb_cursor = source_pdb_conn.cursor()
source_pdb_cursor.execute("SELECT name, value, isdefault FROM v$parameter WHERE isdefault = 'FALSE'")
source_data['pdb_parameters'] = source_pdb_cursor.fetchall()

# Target PDB doesn't exist yet
target_data['pdb_parameters'] = []
```

#### Report Behavior
- Precheck: Shows source PDB parameters vs "N/A" for target (expected)
- Postcheck: Shows actual comparison after clone completes

### Updated Database Link Creation

#### Feature
- Updated database link creation to use TNS descriptor format
- Supports hostname:port connections without tnsnames.ora
- **Implementation**: [oracle_pdb_toolkit.py:393-400](oracle_pdb_toolkit.py#L393-L400)

#### TNS Descriptor Format
```python
tns_descriptor = f"(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST={source_scan})(PORT={source_port}))(CONNECT_DATA=(SERVICE_NAME={source_cdb})))"

target_cursor.execute(f"""
    CREATE PUBLIC DATABASE LINK {link_name}
    CONNECT TO CURRENT_USER
    USING '{tns_descriptor}'
""")
```

## Summary of All Changes

### Files Modified
1. **[oracle_pdb_toolkit.py](oracle_pdb_toolkit.py)** - Main application file with all enhancements

### New Features
1. Database name prefixes in report filenames
2. Overall PASS/FAIL status in precheck reports
3. Status column in CDB parameters comparison
4. New PDB parameters comparison section
5. Connection method selection (External Auth / Username & Password)
6. Hostname/Port/Service connection fields
7. TNS-free connection support

### Bug Fixes
1. Source PDB status check (case-insensitive)
2. DBMS_PDB.DESCRIBE CLOB handling
3. ALTER SESSION SET CONTAINER error during precheck
4. ALTER SESSION SET CONTAINER error during postcheck

### Technical Improvements
1. Direct PDB connections using service names
2. TNS descriptor generation for database links
3. Proper CLOB variable handling
4. Empty target PDB parameters during precheck

## Testing Recommendations

### Test Case 1: Precheck with External Auth
```
Connection Method: External Authentication
Source SCAN Host: prod-scan.example.com
Source Port: 1521
Source CDB: PROD_CDB
Source PDB: PRODPDB
Target SCAN Host: dev-scan.example.com
Target Port: 1521
Target CDB: DEV_CDB
Target PDB: DEVPDB

Expected:
- Report filename: PROD_CDB_PRODPDB_DEV_CDB_DEVPDB_pdb_validation_report_YYYYMMDD_HHMMSS.html
- All checks should show proper status
- Section 4 shows source PDB params vs N/A for target
- Overall status: PASS or FAIL in colored text
```

### Test Case 2: Precheck with Username/Password
```
Connection Method: Username / Password
Source Hostname: 192.168.1.100
Source Port: 1521
Source CDB: ORCL
Source PDB: PDB1
Source Username: system
Source Password: oracle
Target Hostname: 192.168.1.200
Target Port: 1521
Target CDB: ORCL
Target PDB: PDB1CLONE
Target Username: system
Target Password: oracle

Expected:
- Connects successfully without Oracle Client
- Report generated with proper naming
- All validations execute correctly
```

### Test Case 3: Health Check
```
Database: PROD_CDB
Connection Method: External Authentication

Expected:
- Report filename: PROD_CDB_db_health_report_YYYYMMDD_HHMMSS.html
- Report contains all health metrics
```

## Version Compatibility

- **Oracle Database**: 19c, 21c, 23ai, 26ai
- **Python**: 3.8+
- **python-oracledb**: 2.0+
- **PyQt6**: 6.0+

## Migration Notes

All changes are backward compatible. Existing configurations will continue to work. New features are additive and optional.

---

**Release Date**: January 10, 2026
**Version**: 1.2
**Status**: Production Ready
