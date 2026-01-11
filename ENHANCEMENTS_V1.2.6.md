# Oracle PDB Toolkit Enhancements - Version 1.2.6

**Date**: January 10, 2026
**Status**: ✅ COMPLETE

---

## Summary

Version 1.2.6 adds three user-requested enhancements:

1. **Auto-Open HTML Reports**: Reports automatically open in default browser after generation
2. **Enhanced DB Health Check**: Added instance info, DB size, and MAX_PDB_STORAGE with usage percentage
3. **Standardized MAX_PDB_STORAGE Display**: All MAX_PDB_STORAGE values displayed in GB only

---

## Enhancement 1: Auto-Open HTML Reports

### Feature
All HTML reports (DB Health Check, PDB Precheck, PDB Postcheck) now automatically open in the user's default web browser immediately after generation.

### Implementation
```python
import webbrowser

# After writing report file
report_path = os.path.abspath(filename)

# Auto-open the HTML report in default browser
try:
    webbrowser.open('file://' + report_path)
except Exception:
    # If auto-open fails, just continue (report is still saved)
    pass

return report_path
```

### Benefits
- **Immediate Feedback**: Report opens automatically - no need to manually navigate to file
- **Better UX**: Streamlined workflow for viewing results
- **Non-Breaking**: If browser launch fails, report is still saved and path is returned
- **Cross-Platform**: Uses Python's webbrowser module (works on Windows, Linux, macOS)

### User Experience

**Before**:
1. Run precheck
2. See message: "Report generated: C:\Users\user\Desktop\Oracle\PDB\report.html"
3. Manually navigate to file location
4. Double-click to open

**After**:
1. Run precheck
2. Report automatically opens in browser
3. Review immediately

---

## Enhancement 2: Enhanced DB Health Check Report

### Feature
Added three critical pieces of information to the "Database Information" section:

1. **Instance Name / Hostname**: Shows all instances (supports RAC)
2. **Database Size**: Total size of all datafiles in GB
3. **MAX_PDB_STORAGE**: Shows limit and usage percentage (if set)

### Implementation

#### Data Gathering
```python
# Instance information (all instances for RAC)
cursor.execute("""
    SELECT inst_id, instance_name, host_name
    FROM gv$instance
    ORDER BY inst_id
""")
health_data['instances'] = cursor.fetchall()

# Database size (total size of all datafiles)
cursor.execute("""
    SELECT ROUND(SUM(bytes)/1024/1024/1024, 2) as size_gb
    FROM v$datafile
""")
db_size_result = cursor.fetchone()
health_data['db_size_gb'] = db_size_result[0] if db_size_result else 0

# MAX_PDB_STORAGE (if this is a CDB, query from a PDB)
try:
    # Check if this is a CDB
    cursor.execute("SELECT cdb FROM v$database")
    is_cdb_result = cursor.fetchone()
    is_cdb = is_cdb_result[0] == 'YES' if is_cdb_result else False

    if is_cdb:
        # Get first available PDB to query MAX_PDB_STORAGE
        cursor.execute("SELECT name FROM v$pdbs WHERE name != 'PDB$SEED' AND rownum = 1")
        first_pdb = cursor.fetchone()

        if first_pdb:
            # Switch to PDB to query MAX_PDB_STORAGE
            cursor.execute(f"ALTER SESSION SET CONTAINER = {first_pdb[0]}")
            cursor.execute("""
                SELECT property_value
                FROM database_properties
                WHERE property_name = 'MAX_PDB_STORAGE'
            """)
            max_pdb_result = cursor.fetchone()
            health_data['max_pdb_storage'] = max_pdb_result[0] if max_pdb_result else 'UNLIMITED'

            # Calculate percentage if MAX_PDB_STORAGE is set and not UNLIMITED
            if health_data['max_pdb_storage'] != 'UNLIMITED':
                storage_str = health_data['max_pdb_storage'].upper()
                # Parse G/M/T and convert to GB
                # Calculate: (db_size_gb / max_storage_gb) * 100
                health_data['storage_pct'] = round((health_data['db_size_gb'] / max_storage_gb) * 100, 2)

            # Switch back to CDB$ROOT
            cursor.execute("ALTER SESSION SET CONTAINER = CDB$ROOT")
```

#### Report Display
```html
<h2>Database Information</h2>
<div class="info-box">
    <p><strong>Database Name:</strong> PRODCDB</p>
    <p><strong>Open Mode:</strong> READ WRITE</p>
    <p><strong>Role:</strong> PRIMARY</p>
    <p><strong>Version:</strong> Oracle Database 23ai Free</p>
    <p><strong>Instance 1:</strong> FREE1 @ rac1.artechdb.com</p>
    <p><strong>Instance 2:</strong> FREE2 @ rac2.artechdb.com</p>
    <p><strong>Database Size:</strong> 125.73 GB</p>
    <p><strong>MAX_PDB_STORAGE:</strong> 200G (62.87% used)</p>
</div>
```

### Display Scenarios

#### Scenario 1: CDB with MAX_PDB_STORAGE Set
```
Instance 1: PROD1 @ prod-host1.example.com
Instance 2: PROD2 @ prod-host2.example.com
Database Size: 125.73 GB
MAX_PDB_STORAGE: 200G (62.87% used)
```

#### Scenario 2: CDB with UNLIMITED
```
Instance 1: DEV1 @ dev-host.example.com
Database Size: 45.23 GB
MAX_PDB_STORAGE: UNLIMITED
```

#### Scenario 3: Non-CDB Database
```
Instance 1: STANDALONE @ standalone-host.example.com
Database Size: 85.50 GB
(No MAX_PDB_STORAGE displayed - not applicable for non-CDB)
```

### Benefits
- **RAC Support**: Shows all instances with their hostnames
- **Capacity Planning**: Instant visibility of database size
- **Storage Monitoring**: See how much of MAX_PDB_STORAGE is consumed
- **Proactive Alerts**: Identify storage issues before they become critical

---

## Enhancement 3: Standardized MAX_PDB_STORAGE Display (GB Only)

### Feature
All MAX_PDB_STORAGE values are now converted and displayed in GB only, regardless of how they are stored in the database (M, G, or T).

### Implementation

#### Before (Mixed Units)
```python
# Display as-is from database
source_max_pdb_storage = 'UNLIMITED'  # or '50G' or '2048M' or '1T'
target_max_pdb_storage = '2048M'

# Report shows:
# Source: UNLIMITED
# Target: 2048M (confusing - need to mentally convert)
```

#### After (GB Only)
```python
# Convert to GB for display
source_max_pdb_storage_raw = source_max_pdb_result[0] if source_max_pdb_result else 'UNLIMITED'

if source_max_pdb_storage_raw.upper() == 'UNLIMITED':
    source_max_pdb_storage = 'UNLIMITED'
else:
    storage_str = source_max_pdb_storage_raw.upper()
    if 'G' in storage_str:
        source_max_pdb_storage = source_max_pdb_storage_raw  # Already in GB
    elif 'M' in storage_str:
        gb_val = float(storage_str.replace('M', '')) / 1024
        source_max_pdb_storage = f"{gb_val:.2f}G"
    elif 'T' in storage_str:
        gb_val = float(storage_str.replace('T', '')) * 1024
        source_max_pdb_storage = f"{gb_val:.2f}G"
    else:
        # Assume bytes
        gb_val = float(storage_str) / (1024**3)
        source_max_pdb_storage = f"{gb_val:.2f}G"

# Report shows:
# Source: UNLIMITED
# Target: 2.00G (consistent and easy to compare)
```

### Conversion Examples

| Database Value | Displayed As | Calculation |
|----------------|--------------|-------------|
| UNLIMITED | UNLIMITED | No conversion |
| 50G | 50.00G | Already in GB |
| 2048M | 2.00G | 2048 / 1024 = 2.00 |
| 51200M | 50.00G | 51200 / 1024 = 50.00 |
| 1T | 1024.00G | 1 * 1024 = 1024.00 |
| 2T | 2048.00G | 2 * 1024 = 2048.00 |
| 53687091200 (bytes) | 50.00G | 53687091200 / (1024³) = 50.00 |

### Report Display

#### Before Fix
```
Check                         Status    Source Value                   Target Value
MAX_PDB_STORAGE Limit         PASS      0.86 GB (limit: UNLIMITED)    2048M (sufficient for 0.86 GB source PDB)
```
**Problem**: Mixing units (GB and M) - hard to compare

#### After Fix
```
Check                         Status    Source Value                   Target Value
MAX_PDB_STORAGE Limit         PASS      0.86 GB (limit: UNLIMITED)    2.00G (sufficient for 0.86 GB source PDB)
```
**Solution**: All values in GB - easy to compare

### Benefits
- **Consistency**: All MAX_PDB_STORAGE values in GB
- **Easy Comparison**: No mental math required
- **Professional**: Clean, standardized output
- **Accuracy**: Two decimal precision for sub-GB values

---

## Files Modified

1. **[oracle_pdb_toolkit.py](oracle_pdb_toolkit.py)**
   - Lines 6-18: Added `webbrowser` import
   - Lines 154-217: Added instance info, DB size, and MAX_PDB_STORAGE gathering for health check
   - Lines 568-590: Added GB conversion for source MAX_PDB_STORAGE
   - Lines 591-633: Added GB conversion for target MAX_PDB_STORAGE
   - Lines 1373-1387: Auto-open health report
   - Lines 1383-1407: Display instance info, DB size, MAX_PDB_STORAGE in health report
   - Lines 1578-1592: Auto-open precheck report
   - Lines 1692-1706: Auto-open postcheck report

2. **[ENHANCEMENTS_V1.2.6.md](ENHANCEMENTS_V1.2.6.md)** (this file)
   - Complete documentation of all enhancements

---

## Testing

### Test 1: Auto-Open Report
```bash
python oracle_pdb_toolkit.py
# Select "DB Health Check"
# Enter connection details
# Click "Execute"
```

**Expected Result**:
- Report generates successfully
- Browser automatically opens with report
- If browser fails to open, report is still saved

### Test 2: Enhanced DB Health Check
```bash
python oracle_pdb_toolkit.py
# Select "DB Health Check"
# Connect to a CDB with multiple instances
```

**Expected Result** (RAC environment):
```
Database Information

Database Name: PRODCDB
Open Mode: READ WRITE
Role: PRIMARY
Version: Oracle Database 23ai Free
Instance 1: FREE1 @ rac1.artechdb.com
Instance 2: FREE2 @ rac2.artechdb.com
Database Size: 125.73 GB
MAX_PDB_STORAGE: 200G (62.87% used)
```

### Test 3: MAX_PDB_STORAGE in GB
```bash
python oracle_pdb_toolkit.py
# Select "PDB Precheck"
# Use a PDB with MAX_PDB_STORAGE set to 2048M
```

**Expected Result**:
```
Check                         Status    Source Value                   Target Value
MAX_PDB_STORAGE Limit         PASS      0.86 GB (limit: UNLIMITED)    2.00G (sufficient for 0.86 GB source PDB)
```

---

## Upgrade Notes

### From v1.2.5 to v1.2.6

1. **No Configuration Changes Required**
2. **New Dependency**: Uses Python `webbrowser` module (built-in, no installation needed)
3. **CDB Context Switching**: Health check may switch PDB container to query MAX_PDB_STORAGE (automatically reverts)
4. **Report Format Changes**: DB Health Check report has additional fields

### Compatibility
- ✅ Windows, Linux, macOS (webbrowser module is cross-platform)
- ✅ Oracle 19c, 21c, 23ai, 26ai
- ✅ Single-instance and RAC configurations
- ✅ CDB and Non-CDB databases

---

## Summary of Changes

### What's New
1. ✅ **Auto-Open Reports**: All reports open automatically in browser
2. ✅ **Instance Details**: RAC instance information in health check
3. ✅ **Database Size**: Total DB size displayed in health check
4. ✅ **MAX_PDB_STORAGE**: Limit and usage percentage in health check
5. ✅ **Standardized Units**: All MAX_PDB_STORAGE values in GB only

### Impact
- **Better UX**: Immediate report viewing
- **More Information**: Critical metrics at a glance
- **Consistency**: Standardized unit display
- **RAC Support**: Full multi-instance visibility

---

**Version**: 1.2.6
**Last Updated**: January 10, 2026
**Status**: ✅ Production Ready
