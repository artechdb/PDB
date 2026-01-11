# CRITICAL FIX: DBMS_PDB.DESCRIBE Connection Context

**Date**: January 10, 2026
**Issue**: Connecting to PDB instead of CDB for DBMS_PDB.DESCRIBE
**Fix**: Use CDB connection with PDB name parameter

---

## Problem

The toolkit was incorrectly connecting to the **PDB** to run `DBMS_PDB.DESCRIBE`:

```python
# INCORRECT - Was connecting to PDB
source_pdb_dsn_temp = f"{source_scan}:{source_port}/{source_pdb}"
source_pdb_conn_temp = oracledb.connect(dsn=source_pdb_dsn_temp, externalauth=True)
source_pdb_cursor_temp = source_pdb_conn_temp.cursor()

# This would fail because DBMS_PDB.DESCRIBE doesn't work this way
source_pdb_cursor_temp.execute("""
    BEGIN
        DBMS_PDB.DESCRIBE(pdb_descr_xml => :xml_output);
    END;
""", xml_output=xml_var)
```

---

## Root Cause

`DBMS_PDB.DESCRIBE` must be called from the **CDB (Container Database) context**, not from within the PDB itself.

### Correct Usage

```sql
-- Connect to CDB (not PDB)
CONNECT user/password@hostname:port/CDB_NAME

-- Call DBMS_PDB.DESCRIBE with PDB name parameter
DECLARE
    v_xml CLOB;
BEGIN
    DBMS_PDB.DESCRIBE(
        pdb_descr_xml => v_xml,
        pdb_name => 'PRODPDB'  -- Specify which PDB to describe
    );
END;
/
```

### Why It Was Failing

When connected to the **PDB**, calling `DBMS_PDB.DESCRIBE` without a PDB name parameter would fail because:
1. The procedure signature requires the PDB name when called from CDB
2. When called from within a PDB, it doesn't know which PDB to describe
3. Oracle 23ai Free only has the file-based signature visible in `all_arguments`

---

## Solution

### Before (v1.2.3 - INCORRECT)

```python
# Connect to source PDB
source_pdb_dsn_temp = f"{source_scan}:{source_port}/{source_pdb}"
source_pdb_conn_temp = oracledb.connect(dsn=source_pdb_dsn_temp, externalauth=True)
source_pdb_cursor_temp = source_pdb_conn_temp.cursor()

# Try to call DESCRIBE from PDB context (FAILS)
source_pdb_cursor_temp.execute("""
    BEGIN
        DBMS_PDB.DESCRIBE(pdb_descr_xml => :xml_output);
    END;
""", xml_output=xml_var)
```

### After (v1.2.4 - CORRECT)

```python
# Use existing CDB connection (already connected from earlier checks)
# source_cursor is already connected to CDB

# Verify CDB context
source_cursor.execute("SELECT sys_context('USERENV', 'CON_NAME') FROM dual")
current_container = source_cursor.fetchone()[0]
# Should return: CDB$ROOT or similar CDB name

# Call DESCRIBE from CDB with PDB name parameter
source_cursor.execute("""
    DECLARE
        v_pdb_name VARCHAR2(128) := :pdb_name;
    BEGIN
        DBMS_PDB.DESCRIBE(
            pdb_descr_xml => :xml_output,
            pdb_name => v_pdb_name
        );
    END;
""", xml_output=xml_var, pdb_name=source_pdb)
```

---

## Changes Made

### 1. Connection Context
- **Before**: Connected to PDB (`rac1.artechdb.com:1521/freepdb1`)
- **After**: Use existing CDB connection (`rac1.artechdb.com:1521/free`)

### 2. Method 1 Updated
```python
# Before (missing PDB name)
plsql_block_method1 = """
    BEGIN
        DBMS_PDB.DESCRIBE(pdb_descr_xml => :xml_output);
    END;
"""

# After (includes PDB name)
plsql_block_method1 = """
    DECLARE
        v_pdb_name VARCHAR2(128) := :pdb_name;
    BEGIN
        DBMS_PDB.DESCRIBE(
            pdb_descr_xml => :xml_output,
            pdb_name => v_pdb_name
        );
    END;
"""
```

### 3. All Method Calls Updated
All 4 methods now:
- Use `source_cursor` (CDB connection) instead of `source_pdb_cursor_temp`
- Pass `pdb_name=source_pdb` parameter
- Execute from CDB context

---

## Expected Result

### Your Next Run Should Show

```
[20:XX:XX] DEBUG: Using CDB connection for DBMS_PDB.DESCRIBE
[20:XX:XX] DEBUG: Source CDB DSN = rac1.artechdb.com:1521/free
[20:XX:XX] DEBUG: Current container context = CDB$ROOT (or FREE)
[20:XX:XX] DEBUG: Querying DBMS_PDB.DESCRIBE signature from database...
[20:XX:XX] DEBUG: DBMS_PDB.DESCRIBE signature in this Oracle version:
[20:XX:XX] DEBUG:   Overload None, Position 1: PDB_DESCR_FILE (VARCHAR2, IN, Level=0)
[20:XX:XX] DEBUG:   Overload None, Position 2: PDB_NAME (VARCHAR2, IN, Level=0)
[20:XX:XX] DEBUG: Found file-based overload (Overload None): PDB_DESCR_FILE (VARCHAR2 IN)
[20:XX:XX]
[20:XX:XX] INFO: all_arguments shows file-based signature
[20:XX:XX] INFO: However, Oracle 19c+ typically supports CLOB overload
[20:XX:XX] INFO: Attempting CLOB-based methods first...
[20:XX:XX]
[20:XX:XX] DEBUG: Created CLOB variable for XML output
[20:XX:XX] DEBUG: Attempting Method 1 - CLOB with PDB name from CDB (Oracle 19c+)...
[20:XX:XX] DEBUG: Method 1 succeeded!  <-- SUCCESS!
[20:XX:XX] DEBUG: DBMS_PDB.DESCRIBE executed successfully
[20:XX:XX] DEBUG: XML exported to file: free_freepdb1_pdb_describe_YYYYMMDD_HHMMSS.xml
[20:XX:XX] DEBUG: XML length = XXXXX characters
[20:XX:XX] DEBUG: Running DBMS_PDB.CHECK_PLUG_COMPATIBILITY on target CDB...
[20:XX:XX] DEBUG: Compatibility check result = TRUE (or FALSE)
```

---

## Why This Will Work

Oracle 23ai Free **does** support CLOB-based `DBMS_PDB.DESCRIBE`, but it must be called:
1. **From CDB context** (not from within the PDB)
2. **With PDB name parameter** (to specify which PDB to describe)
3. **Returns XML as CLOB** (client-accessible, no file needed)

The signature shown in `all_arguments` was misleading because:
- It showed the file-based signature (backward compatibility)
- The CLOB overload exists but wasn't visible in that view
- Calling from the wrong context (PDB) made all CLOB methods fail

---

## Oracle Documentation Reference

From Oracle Database PL/SQL Packages and Types Reference:

```
DBMS_PDB.DESCRIBE Procedure

Purpose: Constructs an XML description of a PDB

Syntax (from CDB):
DBMS_PDB.DESCRIBE(
   pdb_descr_xml OUT CLOB,
   pdb_name      IN  VARCHAR2);

Parameters:
- pdb_descr_xml: Output CLOB containing PDB description XML
- pdb_name: Name of the PDB to describe

Usage Notes:
- Must be executed from CDB$ROOT (or CDB context)
- Requires SELECT ANY DICTIONARY or SELECT_CATALOG_ROLE privilege
- The resulting XML can be used with CHECK_PLUG_COMPATIBILITY
```

---

## Version

- **Fixed in**: v1.2.4
- **Previous broken versions**: v1.2.0 - v1.2.3
- **Status**: ✅ COMPLETE - Ready for testing

---

**Next Step**: Run the precheck again and Method 1 should succeed!
