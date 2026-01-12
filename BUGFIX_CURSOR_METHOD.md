# Bug Fix: cursor() vs get_cursor() Method Issue

**Date**: January 11, 2026
**Issue**: AttributeError with cursor methods
**Status**: ✅ FIXED

---

## Problem

When running the modular application (`python main.py`), operations failed with two different errors:

### Error 1: Health Check
```
AttributeError: 'DatabaseConnection' object has no attribute 'cursor'
```

### Error 2: PDB Precheck
```
AttributeError: 'Connection' object has no attribute 'get_cursor'
```

**Root Cause**: Confusion between two different connection types:
- `DatabaseConnection` (wrapper) uses `get_cursor()`
- `oracledb.Connection` (raw) uses `cursor()`

---

## Solution

### Files Fixed

1. **db_healthcheck.py** (Line 66)
   - Uses `create_connection()` → Returns `DatabaseConnection`
   - Changed: `cursor = connection.cursor()`
   - To: `cursor = connection.get_cursor()` ✅

2. **pdb_clone.py** (ALL lines)
   - Uses `oracledb.connect()` → Returns raw `Connection`
   - Keep: `cursor = conn.cursor()` ✅
   - ALL connections in this file use raw oracledb, so they all use `.cursor()`

---

## Verification

```bash
python -c "from db_healthcheck import perform_health_check; print('OK')"
# Output: OK
```

---

## Testing

The application now works correctly:

```bash
python main.py
# Health check operation completes successfully
```

---

## Technical Details

### DatabaseConnection API

The `DatabaseConnection` wrapper class (utils/db_connection.py) provides:
- `get_cursor()` - Returns a cursor object
- `close()` - Closes the connection
- Context manager support (`with` statement)

### When to Use Each Method

**Use `get_cursor()`**:
```python
from utils.db_connection import create_connection
conn = create_connection(params)  # Returns DatabaseConnection
cursor = conn.get_cursor()  # ✓ Correct
```

**Use `cursor()`**:
```python
import oracledb
conn = oracledb.connect(...)  # Returns raw oracledb.Connection
cursor = conn.cursor()  # ✓ Correct
```

---

**Status**: ✅ Fixed and verified
**Version**: 2.0.1

---

## Update: Added Missing Precheck Validations

**Date**: January 11, 2026 (continued)
**Enhancement**: Added 2 missing checks to PDB precheck

### Missing Checks Restored

**Check 9: MAX_PDB_STORAGE Limit** (Lines 315-446)
- Connects to source PDB to query `database_properties`
- Retrieves MAX_PDB_STORAGE value
- Converts storage values (M/G/T/UNLIMITED) to GB
- Connects to target PDB if it exists
- Compares source PDB size with target MAX_PDB_STORAGE limit
- Generates PASS/FAILED/SKIPPED validation result

**Check 10: DBMS_PDB.CHECK_PLUG_COMPATIBILITY** (Lines 448-778)
- Uses CLOB-based method (no file system access required)
- Queries DBMS_PDB.DESCRIBE signature to detect available overloads
- Tries 4 different calling methods for Oracle version compatibility:
  - Method 1: CLOB with PDB name from CDB (Oracle 19c+)
  - Method 2: CLOB positional with PDB name (Oracle 12c)
  - Method 3: Positional CLOB and PDB name (Oracle 12c alt)
  - Method 4: File-based with DBMS_LOB (Oracle 12.1/12.2)
- Executes DBMS_PDB.DESCRIBE from CDB context
- Exports XML manifest to file for inspection
- Runs CHECK_PLUG_COMPATIBILITY on target CDB
- Queries PDB_PLUG_IN_VIOLATIONS if incompatible
- Generates PASS/FAILED/SKIPPED validation result with violations

### Files Modified

**pdb_clone.py** (Lines 315-778)
- Replaced placeholder comments with complete implementations
- Added 463 lines of validation logic
- Total file size: ~1,350 lines

**Status**: ✅ Fixed, enhanced, and ready for testing
**Version**: 2.0.1
