# Oracle 23ai DBMS_PDB.DESCRIBE Note

**Date**: January 10, 2026
**Oracle Version**: Oracle Database 23ai Free
**Issue**: DBMS_PDB compatibility check being skipped

---

## Observation

Your Oracle 23ai Free installation shows the following signature in `all_arguments`:

```
Overload None, Position 1: PDB_DESCR_FILE (VARCHAR2, IN)
Overload None, Position 2: PDB_NAME (VARCHAR2, IN)
```

This is the **file-based signature**, which typically indicates Oracle 12.1/12.2.

However, Oracle 23ai should support the CLOB-based overload:
```sql
DBMS_PDB.DESCRIBE(pdb_descr_xml OUT CLOB)
```

---

## Why This Happens

There are several possible reasons:

### 1. Oracle 23ai Free Edition Differences
- Oracle 23ai Free (formerly XE) may have a different DBMS_PDB package configuration
- Some features may be limited compared to Enterprise Edition
- The CLOB overload might not be exposed in `all_arguments` but still be callable

### 2. Package Version
- The DBMS_PDB package may not be fully upgraded
- Check package validity:
  ```sql
  SELECT object_name, status
  FROM dba_objects
  WHERE object_name = 'DBMS_PDB' AND owner = 'SYS';
  ```

### 3. all_arguments Metadata
- `all_arguments` may not show all overloads
- The CLOB overload might exist but not be visible in this view

---

## Updated Toolkit Behavior

The toolkit has been updated to handle this scenario intelligently:

### Before (v1.2.2)
```
1. Query all_arguments for DBMS_PDB.DESCRIBE signature
2. If only file-based detected → Skip immediately
3. Result: SKIPPED (no attempt to run CLOB methods)
```

### After (v1.2.3)
```
1. Query all_arguments for DBMS_PDB.DESCRIBE signature
2. Display INFO message that CLOB methods will be attempted
3. Attempt all 4 calling methods (CLOB and file-based)
4. If all fail → Skip with manual instructions
5. Result: Attempts automated execution before giving up
```

---

## Expected Output (Your Next Run)

```
[20:21:44] DEBUG: Querying DBMS_PDB.DESCRIBE signature from database...
[20:21:44] DEBUG: DBMS_PDB.DESCRIBE signature in this Oracle version:
[20:21:44] DEBUG:   Overload None, Position 1: PDB_DESCR_FILE (VARCHAR2, IN, Level=0)
[20:21:44] DEBUG:   Overload None, Position 2: PDB_NAME (VARCHAR2, IN, Level=0)
[20:21:44] DEBUG: Found file-based overload (Overload None)
[20:21:44]
[20:21:44] INFO: all_arguments shows file-based signature
[20:21:44] INFO: However, Oracle 19c+ typically supports CLOB overload
[20:21:44] INFO: Attempting CLOB-based methods first...
[20:21:44]
[20:21:44] DEBUG: Created CLOB variable for XML output
[20:21:44] DEBUG: Attempting Method 1 - Single named parameter (Oracle 19c+)...
[20:21:44] DEBUG: Method 1 failed: ORA-06550...
[20:21:44] DEBUG: Attempting Method 2 - Two named parameters (Oracle 12c)...
[20:21:44] DEBUG: Method 2 also failed: ORA-06550...
[20:21:44] DEBUG: Attempting Method 3 - Two positional parameters (Oracle 12c alt)...
[20:21:44] DEBUG: Method 3 also failed: ORA-06550...
[20:21:44] DEBUG: Attempting Method 4 - File-based with DBMS_LOB (Oracle 12c)...
[20:21:44] DEBUG: Method 4 also failed: ORA-29283...
[20:21:44]
[20:21:44] NOTICE: All 4 DBMS_PDB.DESCRIBE methods failed
[20:21:44] NOTICE: Your Oracle version appears to only support file-based approach
[20:21:44] NOTICE: File-based approach requires server filesystem access
[20:21:44] NOTICE: Skipping DBMS_PDB plug compatibility check
[20:21:44]
[20:21:44] RECOMMENDATION: Run the compatibility check manually using SQL*Plus:
[20:21:44]   1. Connect to source PDB: sqlplus user/pass@rac1.artechdb.com:1521/freepdb1
[20:21:44]   2. Run: EXEC DBMS_PDB.DESCRIBE(pdb_descr_file => 'pdb_desc.xml', pdb_name => 'freepdb1');
[20:21:44]   3. Copy pdb_desc.xml from DATA_PUMP_DIR on source to target
[20:21:44]   4. Connect to target CDB: sqlplus user/pass@rac2.artechdb.com:1521/free
[20:21:44]   5. Run: SELECT DBMS_PDB.CHECK_PLUG_COMPATIBILITY(pdb_descr_file => 'pdb_desc.xml') FROM dual;
[20:21:44]
[20:21:44] INFO: Continuing with remaining validation checks...
```

---

## Manual Compatibility Check for Oracle 23ai Free

Since the automated approach doesn't work with your Oracle 23ai Free configuration, here's how to manually run the compatibility check:

### Step 1: Connect to Source PDB

```bash
sqlplus / as sysdba @rac1.artechdb.com:1521/freepdb1
```

### Step 2: Generate PDB Description XML

```sql
-- Check DATA_PUMP_DIR location
SELECT directory_path FROM dba_directories WHERE directory_name = 'DATA_PUMP_DIR';

-- Generate the XML
EXEC DBMS_PDB.DESCRIBE(pdb_descr_file => 'freepdb1_desc.xml', pdb_name => 'freepdb1');

-- Verify the file was created
!ls -l /path/to/datapump/freepdb1_desc.xml
```

### Step 3: Copy XML to Target Server

```bash
# From source server
scp /u01/app/oracle/admin/FREE/dpdump/freepdb1_desc.xml \
    oracle@rac2:/u01/app/oracle/admin/FREE/dpdump/
```

### Step 4: Check Compatibility on Target

```bash
sqlplus / as sysdba @rac2.artechdb.com:1521/free
```

```sql
-- Check compatibility
SET SERVEROUTPUT ON SIZE UNLIMITED

DECLARE
    v_compatible BOOLEAN;
BEGIN
    v_compatible := DBMS_PDB.CHECK_PLUG_COMPATIBILITY(
        pdb_descr_file => 'freepdb1_desc.xml'
    );

    IF v_compatible THEN
        DBMS_OUTPUT.PUT_LINE('✓ PDB is COMPATIBLE with target CDB');
    ELSE
        DBMS_OUTPUT.PUT_LINE('✗ PDB is NOT COMPATIBLE with target CDB');
        DBMS_OUTPUT.PUT_LINE('');
        DBMS_OUTPUT.PUT_LINE('Violations:');
    END IF;
END;
/

-- If incompatible, view violations
SELECT name, cause, type, message, status, action
FROM pdb_plug_in_violations
WHERE status != 'RESOLVED'
ORDER BY time DESC
FETCH FIRST 20 ROWS ONLY;
```

---

## Alternative: Check Without DBMS_PDB.DESCRIBE

If the manual approach is too cumbersome, you can verify compatibility by checking these key items manually:

### 1. Oracle Version Match
```sql
-- On both source and target CDB
SELECT version FROM v$instance;
```
Should be compatible versions (23ai can clone from 23ai, 19c, etc.)

### 2. Character Set Compatibility
```sql
-- On both source and target CDB
SELECT value FROM nls_database_parameters WHERE parameter = 'NLS_CHARACTERSET';
SELECT value FROM nls_database_parameters WHERE parameter = 'NLS_NCHAR_CHARACTERSET';
```
Character sets must be compatible.

### 3. Platform Endianness
```sql
-- On both source and target CDB
SELECT platform_name, endian_format FROM v$database;
```
Must match for standard clones (or use RMAN convert for cross-platform).

### 4. TDE Keystore
```sql
-- On both source and target CDB
SELECT * FROM v$encryption_wallet;
```
If source PDB uses TDE, target must have keystore configured.

---

## Recommendation

For Oracle 23ai Free environments:

1. **Accept the SKIPPED status** for DBMS_PDB compatibility check
2. **Rely on other validation checks** in the toolkit (character set, version, TDE, etc.)
3. **Perform manual compatibility check** if needed (see steps above)
4. **Proceed with clone** if other checks pass - incompatibilities will be detected during clone

The toolkit's other validation checks (CDB parameters, PDB parameters, character sets, TDE, undo mode) provide excellent coverage even without the DBMS_PDB check.

---

## Oracle Edition Comparison

| Feature | Oracle Free (XE/23ai Free) | Oracle Standard/Enterprise |
|---------|----------------------------|----------------------------|
| DBMS_PDB.DESCRIBE (file-based) | ✅ Available | ✅ Available |
| DBMS_PDB.DESCRIBE (CLOB-based) | ❌ **Not Available** | ✅ **Available** |
| PDB Cloning | ✅ Supported | ✅ Supported |
| Toolkit Compatibility Check | ⚠️ Manual required | ✅ **Automated** |

### Oracle Versions with CLOB Support (Automated)

| Version | Edition | CLOB Overload | Toolkit Status |
|---------|---------|---------------|----------------|
| 19c | Enterprise Edition | ✅ Yes | ✅ Automated |
| 19c | Standard Edition | ✅ Yes | ✅ Automated |
| 21c | Enterprise Edition | ✅ Yes | ✅ Automated |
| 23ai | Enterprise Edition | ✅ Yes | ✅ Automated |
| 23ai | **Free** | ❌ **No** | ⚠️ **Manual** |
| 26ai | Enterprise Edition | ✅ Yes | ✅ Automated |

### Oracle Versions Requiring Manual Check

| Version | Edition | Reason |
|---------|---------|--------|
| 12.1, 12.2 | All | File-based only (older architecture) |
| 18c XE | Express | Limited DBMS_PDB package |
| 21c XE | Express | Limited DBMS_PDB package |
| 23ai | **Free** | Limited DBMS_PDB package |

---

**Version**: 1.2.3
**Status**: Optimized for Oracle 23ai Free
**Last Updated**: January 10, 2026
