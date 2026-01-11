-- Oracle PDB Toolkit v1.2.5 - Enhancement Testing Script
-- Date: January 10, 2026
-- Purpose: Verify SQL queries for new features

SET SERVEROUTPUT ON SIZE UNLIMITED
SET LINESIZE 200
SET PAGESIZE 100

PROMPT ========================================
PROMPT Testing Enhancement #1: PDB Size Query
PROMPT ========================================

-- Test PDB size calculation (replace 'PRODPDB' with your PDB name)
COLUMN pdb_name FORMAT A20
COLUMN size_gb FORMAT 999,999.99
COLUMN con_id FORMAT 999

SELECT p.name as pdb_name,
       p.con_id,
       ROUND(SUM(d.bytes)/1024/1024/1024, 2) as size_gb
FROM v$pdbs p, v$datafile d
WHERE p.con_id = d.con_id
  AND UPPER(p.name) = UPPER('&PDB_NAME')
GROUP BY p.name, p.con_id;

-- Alternative query using parameter substitution (like in toolkit)
SELECT ROUND(SUM(bytes)/1024/1024/1024, 2) as size_gb
FROM v$datafile
WHERE con_id = (SELECT con_id FROM v$pdbs WHERE UPPER(name) = UPPER('&PDB_NAME'));

PROMPT
PROMPT ========================================
PROMPT Testing Enhancement #2: MAX_STRING_SIZE
PROMPT ========================================

-- Test MAX_STRING_SIZE parameter query
COLUMN parameter FORMAT A30
COLUMN value FORMAT A20

SELECT name as parameter,
       value,
       CASE value
           WHEN 'STANDARD' THEN 'VARCHAR2 max = 4000 bytes'
           WHEN 'EXTENDED' THEN 'VARCHAR2 max = 32767 bytes'
           ELSE 'Unknown setting'
       END as description
FROM v$parameter
WHERE name = 'max_string_size';

PROMPT
PROMPT ========================================
PROMPT Testing Enhancement #3: Timezone Setting
PROMPT ========================================

-- Test DBTIMEZONE query
COLUMN timezone FORMAT A30

SELECT DBTIMEZONE as timezone,
       CASE
           WHEN DBTIMEZONE = '+00:00' THEN 'UTC (Coordinated Universal Time)'
           WHEN DBTIMEZONE LIKE '+%' OR DBTIMEZONE LIKE '-%' THEN 'Offset from UTC'
           ELSE 'Named timezone region'
       END as description
FROM dual;

-- Additional timezone information
SELECT property_name,
       property_value
FROM database_properties
WHERE property_name IN ('DBTIMEZONE', 'NLS_TERRITORY');

PROMPT
PROMPT ========================================
PROMPT Testing Enhancement #4: MAX_PDB_STORAGE
PROMPT ========================================

-- Test MAX_PDB_STORAGE property query (from database_properties, not v$parameter)
COLUMN property_name FORMAT A30
COLUMN property_value FORMAT A30
COLUMN interpretation FORMAT A50

SELECT property_name,
       property_value,
       CASE
           WHEN property_value IS NULL THEN 'Not configured (unlimited)'
           WHEN UPPER(property_value) = 'UNLIMITED' THEN 'UNLIMITED - No storage limit'
           WHEN UPPER(property_value) = '0' THEN 'UNLIMITED - No storage limit'
           WHEN property_value LIKE '%G' THEN 'Limit in Gigabytes'
           WHEN property_value LIKE '%M' THEN 'Limit in Megabytes'
           WHEN property_value LIKE '%T' THEN 'Limit in Terabytes'
           ELSE 'Limit in bytes'
       END as interpretation
FROM database_properties
WHERE property_name = 'MAX_PDB_STORAGE';

-- Check PDB-specific storage limits
COLUMN pdb_name FORMAT A20
COLUMN max_size FORMAT A20

SELECT name as pdb_name,
       CASE
           WHEN total_size IS NOT NULL THEN ROUND(total_size/1024/1024/1024, 2) || ' GB'
           ELSE 'UNLIMITED'
       END as max_size
FROM v$pdbs
ORDER BY name;

PROMPT
PROMPT ========================================
PROMPT Comprehensive Compatibility Check
PROMPT ========================================

-- Run all checks together (simulation of toolkit checks)
SET SERVEROUTPUT ON SIZE UNLIMITED

DECLARE
    v_pdb_name VARCHAR2(128) := '&PDB_NAME';
    v_pdb_size_gb NUMBER;
    v_max_string_size VARCHAR2(20);
    v_timezone VARCHAR2(30);
    v_max_pdb_storage VARCHAR2(30);
    v_max_storage_gb NUMBER;
    v_storage_ok BOOLEAN := TRUE;
BEGIN
    DBMS_OUTPUT.PUT_LINE('===========================================');
    DBMS_OUTPUT.PUT_LINE('Oracle PDB Toolkit v1.2.5 - Compatibility Check');
    DBMS_OUTPUT.PUT_LINE('PDB Name: ' || v_pdb_name);
    DBMS_OUTPUT.PUT_LINE('===========================================');
    DBMS_OUTPUT.PUT_LINE('');

    -- Check 1: PDB Size
    BEGIN
        SELECT ROUND(SUM(bytes)/1024/1024/1024, 2)
        INTO v_pdb_size_gb
        FROM v$datafile
        WHERE con_id = (SELECT con_id FROM v$pdbs WHERE UPPER(name) = UPPER(v_pdb_name));

        DBMS_OUTPUT.PUT_LINE('✓ PDB Size: ' || v_pdb_size_gb || ' GB');
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            DBMS_OUTPUT.PUT_LINE('✗ PDB Size: Could not determine (PDB not found)');
            v_pdb_size_gb := 0;
    END;

    -- Check 2: MAX_STRING_SIZE
    BEGIN
        SELECT value
        INTO v_max_string_size
        FROM v$parameter
        WHERE name = 'max_string_size';

        DBMS_OUTPUT.PUT_LINE('✓ MAX_STRING_SIZE: ' || v_max_string_size);
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            v_max_string_size := 'STANDARD';
            DBMS_OUTPUT.PUT_LINE('✓ MAX_STRING_SIZE: STANDARD (default)');
    END;

    -- Check 3: Database Timezone
    BEGIN
        SELECT DBTIMEZONE
        INTO v_timezone
        FROM dual;

        DBMS_OUTPUT.PUT_LINE('✓ Database Timezone: ' || v_timezone);
    EXCEPTION
        WHEN OTHERS THEN
            DBMS_OUTPUT.PUT_LINE('✗ Database Timezone: Could not determine');
    END;

    -- Check 4: MAX_PDB_STORAGE (from database_properties)
    BEGIN
        SELECT property_value
        INTO v_max_pdb_storage
        FROM database_properties
        WHERE property_name = 'MAX_PDB_STORAGE';

        IF v_max_pdb_storage IS NULL OR UPPER(v_max_pdb_storage) = 'UNLIMITED' OR v_max_pdb_storage = '0' THEN
            DBMS_OUTPUT.PUT_LINE('✓ MAX_PDB_STORAGE: UNLIMITED');
        ELSE
            -- Parse storage value
            IF INSTR(UPPER(v_max_pdb_storage), 'G') > 0 THEN
                v_max_storage_gb := TO_NUMBER(REPLACE(UPPER(v_max_pdb_storage), 'G', ''));
            ELSIF INSTR(UPPER(v_max_pdb_storage), 'M') > 0 THEN
                v_max_storage_gb := TO_NUMBER(REPLACE(UPPER(v_max_pdb_storage), 'M', '')) / 1024;
            ELSIF INSTR(UPPER(v_max_pdb_storage), 'T') > 0 THEN
                v_max_storage_gb := TO_NUMBER(REPLACE(UPPER(v_max_pdb_storage), 'T', '')) * 1024;
            ELSE
                v_max_storage_gb := TO_NUMBER(v_max_pdb_storage) / (1024*1024*1024);
            END IF;

            v_storage_ok := v_max_storage_gb >= v_pdb_size_gb;

            IF v_storage_ok THEN
                DBMS_OUTPUT.PUT_LINE('✓ MAX_PDB_STORAGE: ' || v_max_pdb_storage ||
                                   ' (sufficient for ' || v_pdb_size_gb || ' GB PDB)');
            ELSE
                DBMS_OUTPUT.PUT_LINE('✗ MAX_PDB_STORAGE: ' || v_max_pdb_storage ||
                                   ' (INSUFFICIENT for ' || v_pdb_size_gb || ' GB PDB)');
            END IF;
        END IF;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            DBMS_OUTPUT.PUT_LINE('✓ MAX_PDB_STORAGE: Not configured (unlimited)');
    END;

    DBMS_OUTPUT.PUT_LINE('');
    DBMS_OUTPUT.PUT_LINE('===========================================');
    DBMS_OUTPUT.PUT_LINE('Compatibility check completed');
    DBMS_OUTPUT.PUT_LINE('===========================================');
END;
/

PROMPT
PROMPT ========================================
PROMPT Testing Complete
PROMPT ========================================
PROMPT
PROMPT Next Steps:
PROMPT 1. Review the output above
PROMPT 2. Verify all queries returned expected results
PROMPT 3. Run the Oracle PDB Toolkit precheck to see enhancements in action
PROMPT 4. Compare manual query results with toolkit report
PROMPT
PROMPT Usage Example:
PROMPT python oracle_pdb_toolkit.py
PROMPT -> Select "PDB Precheck"
PROMPT -> Check Section 1 for PDB size display
PROMPT -> Check Section 2 for new validation checks
PROMPT
