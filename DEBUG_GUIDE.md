# Debug Guide - DBMS_PDB.DESCRIBE Troubleshooting

## Overview

This guide explains how to interpret the enhanced debug output for the DBMS_PDB.DESCRIBE compatibility check.

---

## Debug Output Walkthrough

### Step 1: PDB Connection
```
DEBUG: Connecting to source PDB directly...
DEBUG: Source PDB DSN = prod-scan.example.com:1521/PRODPDB
DEBUG: Connection mode = external_auth
DEBUG: Using external authentication for PDB connection
DEBUG: Connected to source PDB successfully
```

**What to Check:**
- ✅ Verify the DSN format is correct: `hostname:port/service`
- ✅ Confirm connection mode matches your setup
- ✅ Look for "Connected to source PDB successfully" message

**If Connection Fails:**
- Check network connectivity to the source host
- Verify the PDB service name is correct and running
- For external auth: ensure OS authentication or Wallet is configured
- For username/password: verify credentials are correct

---

### Step 2: Container Context Verification
```
DEBUG: Current container context = PRODPDB
```

**What to Check:**
- ✅ The container name should match your source PDB name
- ✅ This confirms you're connected to the PDB, not the CDB root

**If Context is Wrong:**
- If shows "CDB$ROOT": The connection went to the CDB instead of the PDB
- If shows different PDB name: Wrong service name was used
- **Fix**: Verify the source PDB service name in your connection settings

---

### Step 3: CLOB Variable Creation
```
DEBUG: Created CLOB variable for XML output
```

**What to Check:**
- ✅ This is just a confirmation that the CLOB variable was created
- ⚠️ If this message is missing, there's a problem in the code

---

### Step 4: DBMS_PDB.DESCRIBE Execution
```
DEBUG: Executing DBMS_PDB.DESCRIBE...
DEBUG: PL/SQL Block:

                BEGIN
                    DBMS_PDB.DESCRIBE(pdb_descr_xml => :xml_output);
                END;

DEBUG: DBMS_PDB.DESCRIBE executed successfully
```

**What to Check:**
- ✅ Look for "executed successfully" message
- ✅ The PL/SQL block shows only ONE parameter (`:xml_output`)

**If This Step Fails:**
- Check the error message immediately after "Executing DBMS_PDB.DESCRIBE..."
- **Common Error**: `ORA-06550: PLS-00306: wrong number or types of arguments`
  - This means the procedure signature is not what we expect
  - Possible causes:
    1. Oracle version incompatibility
    2. Different DBMS_PDB.DESCRIBE signature in your Oracle version
    3. Missing privileges to execute DBMS_PDB

**Diagnostic Commands (run in SQL*Plus or SQLcl):**
```sql
-- Check Oracle version
SELECT * FROM v$version;

-- Check DBMS_PDB package exists and privileges
SELECT object_name, object_type, status
FROM dba_objects
WHERE object_name = 'DBMS_PDB'
AND owner = 'SYS';

-- Check DBMS_PDB.DESCRIBE signature in your Oracle version
DESC SYS.DBMS_PDB

-- Look for DESCRIBE procedure and its parameters
SELECT argument_name, position, data_type, in_out
FROM dba_arguments
WHERE owner = 'SYS'
AND package_name = 'DBMS_PDB'
AND object_name = 'DESCRIBE'
ORDER BY position;
```

---

### Step 5: XML Export
```
DEBUG: XML exported to file: PROD_CDB_PRODPDB_pdb_describe_20260110_180530.xml
DEBUG: XML length = 45821 characters
```

**What to Check:**
- ✅ File path is shown (file saved in current directory)
- ✅ XML length > 0 (should be 30,000-60,000 characters typically)

**If XML is Empty or Missing:**
- ⚠️ Message says "WARNING - XML CLOB is empty/None!"
- This means DBMS_PDB.DESCRIBE returned NULL or empty result
- **Possible causes**:
  1. Not connected to a PDB (connected to CDB$ROOT)
  2. PDB is not in the correct state
  3. Oracle version incompatibility

**What to Do with the XML File:**
- Open it in a text editor or XML viewer
- Verify it contains valid XML (starts with `<?xml version="1.0"?>`)
- Check for PDB metadata like:
  - `<pdb_name>PRODPDB</pdb_name>`
  - `<compatibility>...</compatibility>`
  - Version information
  - Character set information

---

### Step 6: Connection Cleanup
```
DEBUG: Closed source PDB connection
```

**What to Check:**
- ✅ Confirmation that temporary connection was closed

---

### Step 7: CHECK_PLUG_COMPATIBILITY Execution
```
DEBUG: Running DBMS_PDB.CHECK_PLUG_COMPATIBILITY on target CDB...
DEBUG: Executing CHECK_PLUG_COMPATIBILITY...
DEBUG: Compatibility check result = TRUE
DEBUG: Compatibility check completed successfully
```

**What to Check:**
- ✅ Result should be either "TRUE" or "FALSE"
- ✅ "completed successfully" message confirms no errors

**If This Step Fails:**
- Check if the XML was successfully generated in previous steps
- Error here usually means:
  1. Invalid XML format
  2. Target CDB cannot parse the XML
  3. Missing privileges on target CDB

---

## Error Scenarios

### Scenario 1: ORA-06550 Error
```
ERROR: Plug compatibility check failed!
ERROR: Exception type: DatabaseError
ERROR: Exception message: ORA-06550: line 2, column 21:
       PLS-00306: wrong number or types of arguments in call to 'DESCRIBE'
ERROR: Full traceback:
  ...
```

**Root Cause:** Oracle version has a different DBMS_PDB.DESCRIBE signature

**Investigation Steps:**
1. Run diagnostic SQL commands (see Step 4 above)
2. Check Oracle documentation for your specific version
3. Verify the procedure signature matches our expectations

**Possible Solutions:**
- Oracle 12c: DBMS_PDB.DESCRIBE may have 2 parameters (pdb_name + xml)
- Oracle 19c+: Should have 1 parameter (xml only)
- Check Oracle version: `SELECT * FROM v$version;`

---

### Scenario 2: Connection Refused
```
ERROR: Exception message: DPY-6005: cannot connect to database.
```

**Root Cause:** Cannot connect to the PDB service

**Investigation Steps:**
1. Verify PDB is open: `SELECT name, open_mode FROM v$pdbs;`
2. Check service exists: `SELECT name FROM v$services WHERE pdb = 'PRODPDB';`
3. Test connection with SQL*Plus: `sqlplus user/pass@hostname:port/PRODPDB`

---

### Scenario 3: Empty XML
```
DEBUG: WARNING - XML CLOB is empty/None!
```

**Root Cause:** DBMS_PDB.DESCRIBE returned NULL

**Investigation Steps:**
1. Check container context (should be PDB, not CDB$ROOT)
2. Verify PDB is in READ WRITE mode
3. Test manually in SQL*Plus:
   ```sql
   CONNECT user/pass@hostname:port/PRODPDB
   SELECT SYS_CONTEXT('USERENV', 'CON_NAME') FROM dual;
   -- Should return: PRODPDB

   SET SERVEROUTPUT ON
   DECLARE
       l_xml CLOB;
   BEGIN
       DBMS_PDB.DESCRIBE(pdb_descr_xml => l_xml);
       DBMS_OUTPUT.PUT_LINE('XML Length: ' || DBMS_LOB.GETLENGTH(l_xml));
   END;
   /
   ```

---

## Manual Testing

If automated checks fail, test manually:

### Test 1: Direct PDB Connection
```bash
sqlplus system/password@prod-scan.example.com:1521/PRODPDB

SQL> SELECT SYS_CONTEXT('USERENV', 'CON_NAME') FROM dual;
-- Should return: PRODPDB

SQL> SELECT name, open_mode FROM v$pdbs;
-- Should show: PRODPDB, READ WRITE
```

### Test 2: DBMS_PDB.DESCRIBE Manual Test
```sql
SET SERVEROUTPUT ON SIZE UNLIMITED
DECLARE
    l_xml CLOB;
BEGIN
    -- This is the exact call the toolkit makes
    DBMS_PDB.DESCRIBE(pdb_descr_xml => l_xml);

    DBMS_OUTPUT.PUT_LINE('SUCCESS!');
    DBMS_OUTPUT.PUT_LINE('XML Length: ' || DBMS_LOB.GETLENGTH(l_xml));
    DBMS_OUTPUT.PUT_LINE('First 500 chars:');
    DBMS_OUTPUT.PUT_LINE(SUBSTR(l_xml, 1, 500));
EXCEPTION
    WHEN OTHERS THEN
        DBMS_OUTPUT.PUT_LINE('ERROR: ' || SQLERRM);
        DBMS_OUTPUT.PUT_LINE('Error Code: ' || SQLCODE);
END;
/
```

**Expected Output:**
```
SUCCESS!
XML Length: 45821
First 500 chars:
<?xml version="1.0"?>
<pdb>
  <pdb_name>PRODPDB</pdb_name>
  ...
```

### Test 3: CHECK_PLUG_COMPATIBILITY Manual Test
```sql
-- Save XML from Test 2 to a file, then:
CONNECT system/password@dev-scan.example.com:1521/DEV_CDB

DECLARE
    l_xml CLOB;
    l_compatible BOOLEAN;
    l_result VARCHAR2(10);
BEGIN
    -- Load the XML (in practice, you'd use the CLOB from DESCRIBE)
    -- For testing, just use a minimal valid XML
    l_xml := '<?xml version="1.0"?><pdb><pdb_name>PRODPDB</pdb_name></pdb>';

    l_compatible := DBMS_PDB.CHECK_PLUG_COMPATIBILITY(
        pdb_descr_xml => l_xml
    );

    IF l_compatible THEN
        l_result := 'TRUE';
    ELSE
        l_result := 'FALSE';
    END IF;

    DBMS_OUTPUT.PUT_LINE('Compatibility: ' || l_result);
END;
/
```

---

## Oracle Version-Specific Notes

### Oracle 12.1 and 12.2
- DBMS_PDB.DESCRIBE may require different parameters
- Check documentation: `DESC SYS.DBMS_PDB`

### Oracle 18c and 19c
- Standard signature: `DESCRIBE(pdb_descr_xml OUT CLOB)`
- Should work with current implementation

### Oracle 21c and 23ai
- Enhanced multitenant features
- Standard signature should still work

---

## Quick Checklist

Before running precheck:
- [ ] Source PDB is open in READ WRITE mode
- [ ] Target CDB is accessible
- [ ] User has EXECUTE privilege on DBMS_PDB
- [ ] PDB service names are correct and registered
- [ ] Network connectivity between toolkit and databases

When error occurs:
- [ ] Check Oracle version on both source and target
- [ ] Verify container context in debug output
- [ ] Check XML file was created and contains data
- [ ] Run manual SQL tests (Test 2 and Test 3 above)
- [ ] Check Oracle error codes in error messages

---

## Getting Help

If issues persist after reviewing debug output:

1. **Capture debug output**: Copy all DEBUG and ERROR messages
2. **Oracle version**: `SELECT * FROM v$version;`
3. **DBMS_PDB signature**: `SELECT * FROM dba_arguments WHERE package_name='DBMS_PDB' AND object_name='DESCRIBE';`
4. **XML file**: Include the generated XML file
5. **Manual test results**: Output from Test 2 and Test 3

---

**Version**: 1.2
**Last Updated**: January 10, 2026
