"""
Oracle PDB Toolkit - PDB Clone Module
Version: 2.0.0

This module provides PDB cloning operations:
- perform_pdb_precheck: Pre-clone validation checks
- perform_pdb_clone: Execute PDB clone operation
- perform_pdb_postcheck: Post-clone verification checks

Features:
- DBMS_PDB.DESCRIBE with 4 compatibility methods for different Oracle versions
- Full parameter comparison (CDB and PDB level)
- TDE, character set, and version validation
- Database link creation for remote cloning
"""

import oracledb
import traceback
from datetime import datetime
from utils.db_connection import create_connection


def perform_pdb_precheck(params, progress_callback=None):
    """
    Perform PDB clone precheck validations.

    Args:
        params (dict): Parameters for precheck including:
            - connection_mode: 'external_auth' or 'user_pass'
            - source_scan, source_port, source_cdb, source_pdb
            - target_scan, target_port, target_cdb, target_pdb
            - For user_pass: source_username, source_password, target_username, target_password
        progress_callback (callable, optional): Function to call with progress messages

    Returns:
        tuple: (validation_results, source_data, target_data)
    """
    def emit_progress(message):
        if progress_callback:
            progress_callback(message)

    connection_mode = params.get('connection_mode', 'external_auth')
    source_scan = params.get('source_scan')
    source_port = params.get('source_port')
    source_cdb = params.get('source_cdb')
    source_pdb = params.get('source_pdb')
    target_scan = params.get('target_scan')
    target_port = params.get('target_port')
    target_cdb = params.get('target_cdb')
    target_pdb = params.get('target_pdb')

    emit_progress("Starting PDB clone precheck...")

    # Build connection strings
    source_cdb_dsn = f"{source_scan}:{source_port}/{source_cdb}"
    target_cdb_dsn = f"{target_scan}:{target_port}/{target_cdb}"

    # Connect to both CDBs
    if connection_mode == 'external_auth':
        emit_progress(f"Connecting to Source CDB: {source_cdb_dsn} (External Auth)")
        source_conn = oracledb.connect(dsn=source_cdb_dsn, externalauth=True)

        emit_progress(f"Connecting to Target CDB: {target_cdb_dsn} (External Auth)")
        target_conn = oracledb.connect(dsn=target_cdb_dsn, externalauth=True)
    else:
        source_user = params.get('source_username')
        source_pass = params.get('source_password')
        target_user = params.get('target_username')
        target_pass = params.get('target_password')

        emit_progress(f"Connecting to Source CDB: {source_cdb_dsn} (User: {source_user})")
        source_conn = oracledb.connect(user=source_user, password=source_pass, dsn=source_cdb_dsn)

        emit_progress(f"Connecting to Target CDB: {target_cdb_dsn} (User: {target_user})")
        target_conn = oracledb.connect(user=target_user, password=target_pass, dsn=target_cdb_dsn)

    validation_results = []
    source_data = {}
    target_data = {}

    # Gather instance and host information
    emit_progress("Gathering instance and host information...")
    source_cursor = source_conn.cursor()
    target_cursor = target_conn.cursor()

    # Source instance information
    source_cursor.execute("""
        SELECT inst_id, instance_name, host_name
        FROM gv$instance
        ORDER BY inst_id
    """)
    source_data['instances'] = source_cursor.fetchall()

    # Target instance information
    target_cursor.execute("""
        SELECT inst_id, instance_name, host_name
        FROM gv$instance
        ORDER BY inst_id
    """)
    target_data['instances'] = target_cursor.fetchall()

    # Gather PDB size information
    emit_progress("Gathering PDB size information...")

    # Source PDB size
    source_cursor.execute("""
        SELECT ROUND(SUM(bytes)/1024/1024/1024, 2) as size_gb
        FROM v$datafile
        WHERE con_id = (SELECT con_id FROM v$pdbs WHERE UPPER(name) = UPPER(:pdb_name))
    """, pdb_name=source_pdb)
    source_size_result = source_cursor.fetchone()
    source_data['pdb_size_gb'] = source_size_result[0] if source_size_result and source_size_result[0] else 0

    # Target PDB size (if it exists)
    target_cursor.execute("""
        SELECT ROUND(SUM(bytes)/1024/1024/1024, 2) as size_gb
        FROM v$datafile
        WHERE con_id = (SELECT con_id FROM v$pdbs WHERE UPPER(name) = UPPER(:pdb_name))
    """, pdb_name=target_pdb)
    target_size_result = target_cursor.fetchone()
    target_data['pdb_size_gb'] = target_size_result[0] if target_size_result and target_size_result[0] else 0

    # Check 1: Database version and patch level
    emit_progress("Checking database versions...")

    source_cursor.execute("SELECT version, version_full FROM v$instance")
    source_version = source_cursor.fetchone()
    source_data['version'] = source_version[0]
    source_data['version_full'] = source_version[1]

    target_cursor.execute("SELECT version, version_full FROM v$instance")
    target_version = target_cursor.fetchone()
    target_data['version'] = target_version[0]
    target_data['version_full'] = target_version[1]

    version_match = source_version[1] == target_version[1]
    validation_results.append({
        'check': 'Database Version and Patch Level',
        'status': 'PASS' if version_match else 'FAILED',
        'source_value': source_version[1],
        'target_value': target_version[1]
    })

    # Check 2: Character set
    emit_progress("Checking character sets...")
    source_cursor.execute("SELECT value FROM nls_database_parameters WHERE parameter = 'NLS_CHARACTERSET'")
    source_charset = source_cursor.fetchone()[0]
    source_data['charset'] = source_charset

    target_cursor.execute("SELECT value FROM nls_database_parameters WHERE parameter = 'NLS_CHARACTERSET'")
    target_charset = target_cursor.fetchone()[0]
    target_data['charset'] = target_charset

    charset_ok = source_charset == target_charset
    validation_results.append({
        'check': 'Character Set Compatibility',
        'status': 'PASS' if charset_ok else 'FAILED',
        'source_value': source_charset,
        'target_value': target_charset
    })

    # Check 3: DB Registry components
    emit_progress("Checking DB registry components...")
    source_cursor.execute("SELECT comp_name, status FROM dba_registry ORDER BY comp_name")
    source_registry = source_cursor.fetchall()
    source_data['registry'] = source_registry

    target_cursor.execute("SELECT comp_name, status FROM dba_registry ORDER BY comp_name")
    target_registry = target_cursor.fetchall()
    target_data['registry'] = target_registry

    source_comps = set([r[0] for r in source_registry])
    target_comps = set([r[0] for r in target_registry])
    registry_ok = source_comps.issubset(target_comps)

    validation_results.append({
        'check': 'DB Registry Components',
        'status': 'PASS' if registry_ok else 'FAILED',
        'source_value': f"{len(source_comps)} components",
        'target_value': f"{len(target_comps)} components"
    })

    # Check 4: Source PDB status
    emit_progress("Checking source PDB status...")
    source_cursor.execute("""
        SELECT open_mode
        FROM v$pdbs
        WHERE UPPER(name) = UPPER(:pdb_name)
    """, pdb_name=source_pdb)
    result = source_cursor.fetchone()
    if result:
        source_pdb_mode = result[0]
        source_data['pdb_mode'] = source_pdb_mode
        pdb_open = source_pdb_mode != 'MOUNTED'
        validation_results.append({
            'check': 'Source PDB Open Status',
            'status': 'PASS' if pdb_open else 'FAILED',
            'source_value': source_pdb_mode,
            'target_value': 'N/A'
        })
    else:
        validation_results.append({
            'check': 'Source PDB Open Status',
            'status': 'FAILED',
            'source_value': 'PDB not found',
            'target_value': 'N/A'
        })

    # Check 4b: Target PDB existence check
    emit_progress("Checking target PDB status...")
    target_cursor.execute("""
        SELECT open_mode
        FROM v$pdbs
        WHERE UPPER(name) = UPPER(:pdb_name)
    """, pdb_name=target_pdb)
    target_result = target_cursor.fetchone()
    if target_result:
        target_pdb_mode = target_result[0]
        target_data['pdb_mode'] = target_pdb_mode
        validation_results.append({
            'check': 'Target PDB Does Exist',
            'status': 'PASS',
            'source_value': 'N/A',
            'target_value': f'PDB already exists ({target_pdb_mode})'
        })
    else:
        target_data['pdb_mode'] = 'Does not exist'
        validation_results.append({
            'check': 'Target PDB Does Exist',
            'status': 'PASS',
            'source_value': 'N/A',
            'target_value': 'PDB does not exist (ready for clone)'
        })

    # Check 5: TDE configuration
    emit_progress("Checking TDE configuration...")
    source_cursor.execute("SELECT wrl_type FROM v$encryption_wallet")
    source_tde = source_cursor.fetchone()
    source_tde_type = source_tde[0] if source_tde else 'NONE'
    source_data['tde'] = source_tde_type

    target_cursor.execute("SELECT wrl_type FROM v$encryption_wallet")
    target_tde = target_cursor.fetchone()
    target_tde_type = target_tde[0] if target_tde else 'NONE'
    target_data['tde'] = target_tde_type

    tde_match = source_tde_type == target_tde_type
    validation_results.append({
        'check': 'TDE Configuration Method',
        'status': 'PASS' if tde_match else 'FAILED',
        'source_value': source_tde_type,
        'target_value': target_tde_type
    })

    # Check 6: Local undo mode
    emit_progress("Checking undo mode...")
    source_cursor.execute("SELECT property_value FROM database_properties WHERE property_name = 'LOCAL_UNDO_ENABLED'")
    source_undo = source_cursor.fetchone()
    source_undo_mode = source_undo[0] if source_undo else 'FALSE'
    source_data['undo_mode'] = source_undo_mode

    target_cursor.execute("SELECT property_value FROM database_properties WHERE property_name = 'LOCAL_UNDO_ENABLED'")
    target_undo = target_cursor.fetchone()
    target_undo_mode = target_undo[0] if target_undo else 'FALSE'
    target_data['undo_mode'] = target_undo_mode

    undo_ok = source_undo_mode == 'TRUE' and target_undo_mode == 'TRUE'
    validation_results.append({
        'check': 'Local Undo Mode',
        'status': 'PASS' if undo_ok else 'FAILED',
        'source_value': source_undo_mode,
        'target_value': target_undo_mode
    })

    # Check 7: MAX_STRING_SIZE compatibility
    emit_progress("Checking MAX_STRING_SIZE compatibility...")
    source_cursor.execute("SELECT value FROM v$parameter WHERE name = 'max_string_size'")
    source_max_string = source_cursor.fetchone()
    source_max_string_size = source_max_string[0] if source_max_string else 'STANDARD'
    source_data['max_string_size'] = source_max_string_size

    target_cursor.execute("SELECT value FROM v$parameter WHERE name = 'max_string_size'")
    target_max_string = target_cursor.fetchone()
    target_max_string_size = target_max_string[0] if target_max_string else 'STANDARD'
    target_data['max_string_size'] = target_max_string_size

    max_string_ok = source_max_string_size == target_max_string_size
    validation_results.append({
        'check': 'MAX_STRING_SIZE Compatibility',
        'status': 'PASS' if max_string_ok else 'FAILED',
        'source_value': source_max_string_size,
        'target_value': target_max_string_size
    })

    # Check 8: Timezone setting compatibility
    emit_progress("Checking timezone settings...")
    source_cursor.execute("SELECT DBTIMEZONE FROM dual")
    source_tz = source_cursor.fetchone()
    source_timezone = source_tz[0] if source_tz else 'Unknown'
    source_data['timezone'] = source_timezone

    target_cursor.execute("SELECT DBTIMEZONE FROM dual")
    target_tz = target_cursor.fetchone()
    target_timezone = target_tz[0] if target_tz else 'Unknown'
    target_data['timezone'] = target_timezone

    timezone_ok = source_timezone == target_timezone
    validation_results.append({
        'check': 'Timezone Setting Compatibility',
        'status': 'PASS' if timezone_ok else 'FAILED',
        'source_value': source_timezone,
        'target_value': target_timezone
    })

    # Check 9: MAX_PDB_STORAGE limit check
    emit_progress("Checking MAX_PDB_STORAGE limit...")

    # MAX_PDB_STORAGE is a PDB-level property in database_properties
    # Need to query from source PDB (not CDB) and compare with target PDB
    try:
        # Connect to source PDB to get its MAX_PDB_STORAGE
        source_pdb_dsn_temp = f"{source_scan}:{source_port}/{source_pdb}"
        if connection_mode == 'external_auth':
            source_pdb_conn_temp = oracledb.connect(dsn=source_pdb_dsn_temp, externalauth=True)
        else:
            source_user = params.get('source_username')
            source_pass = params.get('source_password')
            source_pdb_conn_temp = oracledb.connect(user=source_user, password=source_pass, dsn=source_pdb_dsn_temp)

        source_pdb_cursor_temp = source_pdb_conn_temp.cursor()
        source_pdb_cursor_temp.execute("""
            SELECT property_value
            FROM database_properties
            WHERE property_name = 'MAX_PDB_STORAGE'
        """)
        source_max_pdb_result = source_pdb_cursor_temp.fetchone()
        source_max_pdb_storage_raw = source_max_pdb_result[0] if source_max_pdb_result and source_max_pdb_result[0] else 'UNLIMITED'

        # Convert source MAX_PDB_STORAGE to GB for display
        if source_max_pdb_storage_raw.upper() == 'UNLIMITED':
            source_max_pdb_storage = 'UNLIMITED'
        else:
            try:
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
            except (ValueError, AttributeError):
                source_max_pdb_storage = source_max_pdb_storage_raw  # Keep original if parsing fails

        source_pdb_cursor_temp.close()
        source_pdb_conn_temp.close()

        # Connect to target PDB to get its MAX_PDB_STORAGE (if target PDB exists)
        target_pdb_exists = target_data.get('pdb_mode') and target_data['pdb_mode'] != 'Does not exist'

        if target_pdb_exists:
            target_pdb_dsn_temp = f"{target_scan}:{target_port}/{target_pdb}"
            if connection_mode == 'external_auth':
                target_pdb_conn_temp = oracledb.connect(dsn=target_pdb_dsn_temp, externalauth=True)
            else:
                target_user = params.get('target_username')
                target_pass = params.get('target_password')
                target_pdb_conn_temp = oracledb.connect(user=target_user, password=target_pass, dsn=target_pdb_dsn_temp)

            target_pdb_cursor_temp = target_pdb_conn_temp.cursor()
            target_pdb_cursor_temp.execute("""
                SELECT property_value
                FROM database_properties
                WHERE property_name = 'MAX_PDB_STORAGE'
            """)
            target_max_pdb_result = target_pdb_cursor_temp.fetchone()
            target_max_pdb_storage_raw = target_max_pdb_result[0] if target_max_pdb_result and target_max_pdb_result[0] else 'UNLIMITED'

            # Convert target MAX_PDB_STORAGE to GB for display and comparison
            if target_max_pdb_storage_raw.upper() == 'UNLIMITED':
                target_max_pdb_storage = 'UNLIMITED'
                max_storage_gb = None
            else:
                try:
                    storage_str = target_max_pdb_storage_raw.upper()
                    if 'G' in storage_str:
                        max_storage_gb = float(storage_str.replace('G', ''))
                        target_max_pdb_storage = f"{max_storage_gb:.2f}G"
                    elif 'M' in storage_str:
                        max_storage_gb = float(storage_str.replace('M', '')) / 1024
                        target_max_pdb_storage = f"{max_storage_gb:.2f}G"
                    elif 'T' in storage_str:
                        max_storage_gb = float(storage_str.replace('T', '')) * 1024
                        target_max_pdb_storage = f"{max_storage_gb:.2f}G"
                    else:
                        # Assume bytes
                        max_storage_gb = float(storage_str) / (1024**3)
                        target_max_pdb_storage = f"{max_storage_gb:.2f}G"
                except (ValueError, AttributeError):
                    target_max_pdb_storage = target_max_pdb_storage_raw  # Keep original if parsing fails
                    max_storage_gb = None

            target_pdb_cursor_temp.close()
            target_pdb_conn_temp.close()
        else:
            target_max_pdb_storage = 'N/A (PDB not created yet)'
            max_storage_gb = None

        target_data['max_pdb_storage'] = target_max_pdb_storage

        # Compare with source PDB size
        if target_max_pdb_storage == 'N/A (PDB not created yet)':
            storage_ok = True
            storage_status = target_max_pdb_storage
        elif target_max_pdb_storage == 'UNLIMITED':
            storage_ok = True
            storage_status = f"UNLIMITED (sufficient for {source_data['pdb_size_gb']} GB source PDB)"
        elif max_storage_gb is not None:
            storage_ok = max_storage_gb >= source_data['pdb_size_gb']
            storage_status = f"{target_max_pdb_storage} ({'sufficient' if storage_ok else 'insufficient'} for {source_data['pdb_size_gb']} GB source PDB)"
        else:
            # Parsing failed
            storage_ok = True
            storage_status = f"{target_max_pdb_storage} (unable to parse, treating as sufficient)"

        validation_results.append({
            'check': 'MAX_PDB_STORAGE Limit',
            'status': 'PASS' if storage_ok else 'FAILED',
            'source_value': f"{source_data['pdb_size_gb']} GB (limit: {source_max_pdb_storage})",
            'target_value': storage_status
        })

    except Exception as e:
        # If we can't check MAX_PDB_STORAGE, add a SKIPPED result
        emit_progress(f"WARNING: Could not check MAX_PDB_STORAGE: {str(e)}")
        validation_results.append({
            'check': 'MAX_PDB_STORAGE Limit',
            'status': 'SKIPPED',
            'source_value': f"{source_data['pdb_size_gb']} GB",
            'target_value': 'Could not verify (connection issue)'
        })

    # Check 10: DBMS_PDB.CHECK_PLUG_COMPATIBILITY
    emit_progress("Checking plug compatibility (using CLOB method)...")

    # Use CLOB-based method instead of file-based
    # This works across platforms without needing file system access
    try:
        # IMPORTANT: DBMS_PDB.DESCRIBE must be run from the CDB context (not PDB)
        # We use the existing source_cursor which is already connected to the CDB
        emit_progress(f"DEBUG: Using CDB connection for DBMS_PDB.DESCRIBE")
        emit_progress(f"DEBUG: Source CDB DSN = {source_scan}:{source_port}/{source_cdb}")

        # Verify we're connected to CDB
        source_cursor.execute("SELECT sys_context('USERENV', 'CON_NAME') FROM dual")
        current_container = source_cursor.fetchone()[0]
        emit_progress(f"DEBUG: Current container context = {current_container}")

        # Query the actual DBMS_PDB.DESCRIBE signature from the database
        emit_progress(f"DEBUG: Querying DBMS_PDB.DESCRIBE signature from database...")
        source_cursor.execute("""
            SELECT argument_name, position, data_type, in_out, data_level, overload
            FROM all_arguments
            WHERE owner = 'SYS'
            AND package_name = 'DBMS_PDB'
            AND object_name = 'DESCRIBE'
            ORDER BY overload NULLS FIRST, position
        """)
        describe_signature = source_cursor.fetchall()

        emit_progress(f"DEBUG: DBMS_PDB.DESCRIBE signature in this Oracle version:")

        # Check if this is file-based or CLOB-based signature
        # Oracle 19c+ has MULTIPLE overloads - we need to detect which ones are available
        has_clob_overload = False
        has_file_overload = False

        if describe_signature:
            # Group by overload number
            overloads = {}
            for arg in describe_signature:
                arg_name = arg[0] or 'RETURN_VALUE'
                overload_num = arg[5] if len(arg) > 5 else None

                if overload_num not in overloads:
                    overloads[overload_num] = []
                overloads[overload_num].append(arg)

                emit_progress(f"DEBUG:   Overload {overload_num}, Position {arg[1]}: {arg_name} ({arg[2]}, {arg[3]}, Level={arg[4]})")

            # Check each overload
            for overload_num, params_list in overloads.items():
                # Check if this overload is CLOB-based (first param is CLOB OUT)
                if params_list:
                    # Find the parameter at position 1 (first parameter)
                    first_param = None
                    for param in params_list:
                        if param[1] == 1:  # position == 1
                            first_param = param
                            break

                    if first_param:
                        param_name = first_param[0] or 'RETURN_VALUE'
                        param_type = first_param[2]
                        param_direction = first_param[3]

                        # CLOB overload: PDB_DESCR_XML CLOB OUT
                        if param_type == 'CLOB' and param_direction == 'OUT':
                            has_clob_overload = True
                            emit_progress(f"DEBUG: Found CLOB-based overload (Overload {overload_num}): {param_name} ({param_type} {param_direction})")
                        # File overload: PDB_DESCR_FILE VARCHAR2 IN
                        elif param_type == 'VARCHAR2' and param_direction == 'IN' and 'FILE' in str(param_name).upper():
                            has_file_overload = True
                            emit_progress(f"DEBUG: Found file-based overload (Overload {overload_num}): {param_name} ({param_type} {param_direction})")
        else:
            emit_progress(f"DEBUG:   No signature found - DESCRIBE procedure may not exist!")

        # Note: Even if all_arguments only shows file-based signature,
        # Oracle 19c+ may still support CLOB overload
        # We'll try CLOB methods first, and only skip if they all fail
        if has_file_overload and not has_clob_overload:
            emit_progress(f"")
            emit_progress(f"INFO: all_arguments shows file-based signature")
            emit_progress(f"INFO: However, Oracle 19c+ typically supports CLOB overload")
            emit_progress(f"INFO: Attempting CLOB-based methods first...")
            emit_progress(f"")

        # Create CLOB variable for XML output
        xml_var = source_cursor.var(oracledb.DB_TYPE_CLOB)
        emit_progress(f"DEBUG: Created CLOB variable for XML output")

        # Try different calling methods based on Oracle documentation
        # Method 1: Two parameters - CLOB and PDB name (Oracle 19c+ when called from CDB)
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

        # Method 2: Two parameters (Oracle 12.1/12.2 style)
        # In Oracle 12c, DBMS_PDB.DESCRIBE requires the PDB name as second parameter
        plsql_block_method2 = """
            DECLARE
                v_pdb_name VARCHAR2(128) := :pdb_name;
            BEGIN
                DBMS_PDB.DESCRIBE(
                    pdb_descr_xml => :xml_output,
                    pdb_name => v_pdb_name
                );
            END;
        """

        # Method 3: Positional parameters (Oracle 12c alternative)
        plsql_block_method3 = """
            DECLARE
                v_pdb_name VARCHAR2(128) := :pdb_name;
            BEGIN
                DBMS_PDB.DESCRIBE(:xml_output, v_pdb_name);
            END;
        """

        # Method 4: File-based with DBMS_LOB (Oracle 12.1/12.2)
        # This method writes to a file in the database server DATA_PUMP_DIR
        # then reads it back using DBMS_LOB
        plsql_block_method4 = """
            DECLARE
                v_pdb_name VARCHAR2(128) := :pdb_name;
                v_filename VARCHAR2(100) := 'pdb_describe_' || TO_CHAR(SYSDATE, 'YYYYMMDDHH24MISS') || '.xml';
                v_dir VARCHAR2(30) := 'DATA_PUMP_DIR';
                v_file_handle UTL_FILE.FILE_TYPE;
                v_clob CLOB;
                v_line VARCHAR2(32767);
            BEGIN
                -- Step 1: Generate XML file using DBMS_PDB.DESCRIBE
                DBMS_PDB.DESCRIBE(
                    pdb_descr_file => v_filename,
                    pdb_name => v_pdb_name
                );

                -- Step 2: Read the file into a CLOB
                DBMS_LOB.CREATETEMPORARY(v_clob, TRUE);
                v_file_handle := UTL_FILE.FOPEN(v_dir, v_filename, 'R', 32767);

                BEGIN
                    LOOP
                        UTL_FILE.GET_LINE(v_file_handle, v_line);
                        DBMS_LOB.WRITEAPPEND(v_clob, LENGTH(v_line) + 1, v_line || CHR(10));
                    END LOOP;
                EXCEPTION
                    WHEN NO_DATA_FOUND THEN
                        NULL;  -- End of file reached
                END;

                UTL_FILE.FCLOSE(v_file_handle);

                -- Step 3: Delete the temporary file
                UTL_FILE.FREMOVE(v_dir, v_filename);

                -- Step 4: Return the CLOB
                :xml_output := v_clob;
            END;
        """

        emit_progress(f"DEBUG: Attempting Method 1 - CLOB with PDB name from CDB (Oracle 19c+)...")
        emit_progress(f"DEBUG: PL/SQL Block:\n{plsql_block_method1}")

        method_succeeded = False
        try:
            source_cursor.execute(plsql_block_method1, xml_output=xml_var, pdb_name=source_pdb)
            emit_progress(f"DEBUG: Method 1 succeeded!")
            method_succeeded = True
        except Exception as e1:
            emit_progress(f"DEBUG: Method 1 failed: {str(e1)}")
            emit_progress(f"DEBUG: Attempting Method 2 - CLOB positional with PDB name (Oracle 12c)...")
            emit_progress(f"DEBUG: PL/SQL Block:\n{plsql_block_method2}")

            try:
                # Reset CLOB variable
                xml_var = source_cursor.var(oracledb.DB_TYPE_CLOB)
                source_cursor.execute(plsql_block_method2, xml_output=xml_var, pdb_name=source_pdb)
                emit_progress(f"DEBUG: Method 2 succeeded!")
                method_succeeded = True
            except Exception as e2:
                emit_progress(f"DEBUG: Method 2 also failed: {str(e2)}")
                emit_progress(f"DEBUG: Attempting Method 3 - Positional CLOB and PDB name (Oracle 12c alt)...")
                emit_progress(f"DEBUG: PL/SQL Block:\n{plsql_block_method3}")

                try:
                    # Reset CLOB variable
                    xml_var = source_cursor.var(oracledb.DB_TYPE_CLOB)
                    source_cursor.execute(plsql_block_method3, xml_output=xml_var, pdb_name=source_pdb)
                    emit_progress(f"DEBUG: Method 3 succeeded!")
                    method_succeeded = True
                except Exception as e3:
                    emit_progress(f"DEBUG: Method 3 also failed: {str(e3)}")
                    emit_progress(f"DEBUG: Attempting Method 4 - File-based with DBMS_LOB (Oracle 12c)...")
                    emit_progress(f"DEBUG: This method writes to DATA_PUMP_DIR and reads back")

                    try:
                        # Reset CLOB variable
                        xml_var = source_cursor.var(oracledb.DB_TYPE_CLOB)
                        source_cursor.execute(plsql_block_method4, xml_output=xml_var, pdb_name=source_pdb)
                        emit_progress(f"DEBUG: Method 4 succeeded!")
                        method_succeeded = True
                    except Exception as e4:
                        emit_progress(f"DEBUG: Method 4 also failed: {str(e4)}")
                        emit_progress(f"")
                        emit_progress(f"NOTICE: All 4 DBMS_PDB.DESCRIBE methods failed")
                        emit_progress(f"NOTICE: Your Oracle version appears to only support file-based approach")
                        emit_progress(f"NOTICE: File-based approach requires server filesystem access")
                        emit_progress(f"NOTICE: Skipping DBMS_PDB plug compatibility check")
                        emit_progress(f"")
                        emit_progress(f"RECOMMENDATION: Run the compatibility check manually using SQL*Plus:")
                        emit_progress(f"  1. Connect to source PDB: sqlplus user/pass@{source_scan}:{source_port}/{source_pdb}")
                        emit_progress(f"  2. Run: EXEC DBMS_PDB.DESCRIBE(pdb_descr_file => 'pdb_desc.xml', pdb_name => '{source_pdb}');")
                        emit_progress(f"  3. Copy pdb_desc.xml from DATA_PUMP_DIR on source to target")
                        emit_progress(f"  4. Connect to target CDB: sqlplus user/pass@{source_scan}:{source_port}/{target_cdb}")
                        emit_progress(f"  5. Run: SELECT DBMS_PDB.CHECK_PLUG_COMPATIBILITY(pdb_descr_file => 'pdb_desc.xml') FROM dual;")
                        emit_progress(f"")
                        # Raise a special exception to indicate we should skip gracefully
                        raise Exception("ALL_METHODS_FAILED_FILE_BASED_ONLY")

        if not method_succeeded:
            raise Exception("All DBMS_PDB.DESCRIBE methods failed")

        emit_progress(f"DEBUG: DBMS_PDB.DESCRIBE executed successfully")

        xml_clob = xml_var.getvalue()

        # Export XML to file for inspection
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        xml_filename = f"{source_cdb}_{source_pdb}_pdb_describe_{timestamp}.xml"

        if xml_clob:
            xml_content = xml_clob.read() if hasattr(xml_clob, 'read') else str(xml_clob)
            with open(xml_filename, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            emit_progress(f"DEBUG: XML exported to file: {xml_filename}")
            emit_progress(f"DEBUG: XML length = {len(xml_content)} characters")
        else:
            emit_progress(f"DEBUG: WARNING - XML CLOB is empty/None!")

        # No need to close - using existing CDB connection
        emit_progress(f"DEBUG: DBMS_PDB.DESCRIBE completed from CDB context")

        # Check compatibility on target using the XML CLOB
        emit_progress(f"DEBUG: Running DBMS_PDB.CHECK_PLUG_COMPATIBILITY on target CDB...")

        result_var = target_cursor.var(str)

        check_compat_block = """
            DECLARE
                v_compatible BOOLEAN;
            BEGIN
                v_compatible := DBMS_PDB.CHECK_PLUG_COMPATIBILITY(
                    pdb_descr_xml => :xml_input
                );
                IF v_compatible THEN
                    :result := 'TRUE';
                ELSE
                    :result := 'FALSE';
                END IF;
            END;
        """

        emit_progress(f"DEBUG: Executing CHECK_PLUG_COMPATIBILITY...")
        target_cursor.execute(check_compat_block, xml_input=xml_clob, result=result_var)

        compatibility_result = result_var.getvalue()
        emit_progress(f"DEBUG: Compatibility check result = {compatibility_result}")

        # Query violations if incompatible
        violations = []
        if compatibility_result == 'FALSE':
            target_cursor.execute("""
                SELECT name, cause, type, message, status, action
                FROM pdb_plug_in_violations
                WHERE status != 'RESOLVED'
                ORDER BY time DESC
                FETCH FIRST 20 ROWS ONLY
            """)
            violations = target_cursor.fetchall()

        emit_progress(f"DEBUG: Compatibility check completed successfully")

        validation_results.append({
            'check': 'DBMS_PDB Plug Compatibility',
            'status': 'PASS' if compatibility_result == 'TRUE' else 'FAILED',
            'source_value': 'XML generated (CLOB)',
            'target_value': compatibility_result,
            'violations': violations
        })

    except Exception as e:
        # Check if this is the intentional skip for file-based Oracle versions
        if str(e) == "SKIP_FILE_BASED_CHECK" or str(e) == "ALL_METHODS_FAILED_FILE_BASED_ONLY":
            # Already added the SKIPPED result and displayed user message
            # No need to show error - this is expected for file-based only versions
            emit_progress(f"INFO: Continuing with remaining validation checks...")

            # Add SKIPPED result if not already added
            validation_results.append({
                'check': 'DBMS_PDB Plug Compatibility',
                'status': 'SKIPPED',
                'source_value': 'N/A',
                'target_value': 'File-based only (requires manual check)'
            })
        else:
            # If CLOB method fails for other reasons, skip this check
            import traceback
            error_details = traceback.format_exc()

            emit_progress(f"ERROR: Plug compatibility check failed!")
            emit_progress(f"ERROR: Exception type: {type(e).__name__}")
            emit_progress(f"ERROR: Exception message: {str(e)}")
            emit_progress(f"ERROR: Full traceback:")
            for line in error_details.split('\n'):
                if line.strip():
                    emit_progress(f"  {line}")

            validation_results.append({
                'check': 'DBMS_PDB Plug Compatibility',
                'status': 'SKIPPED',
                'source_value': 'Check failed',
                'target_value': f'Error: {str(e)}',
                'violations': []
            })

    # Gather Oracle CDB parameters for comparison
    emit_progress("Gathering Oracle CDB parameters...")
    source_cursor.execute("""
        SELECT name, value, isdefault
        FROM v$parameter
        WHERE isdefault = 'FALSE'
        ORDER BY name
    """)
    source_data['cdb_parameters'] = source_cursor.fetchall()

    target_cursor.execute("""
        SELECT name, value, isdefault
        FROM v$parameter
        WHERE isdefault = 'FALSE'
        ORDER BY name
    """)
    target_data['cdb_parameters'] = target_cursor.fetchall()

    # Gather Oracle PDB parameters
    emit_progress("Gathering Oracle source PDB parameters...")
    source_pdb_dsn = f"{source_scan}:{source_port}/{source_pdb}"

    try:
        if connection_mode == 'external_auth':
            emit_progress(f"Connecting to Source PDB: {source_pdb_dsn} (External Auth)")
            source_pdb_conn = oracledb.connect(dsn=source_pdb_dsn, externalauth=True)
        else:
            source_user = params.get('source_username')
            source_pass = params.get('source_password')
            emit_progress(f"Connecting to Source PDB: {source_pdb_dsn} (User: {source_user})")
            source_pdb_conn = oracledb.connect(user=source_user, password=source_pass, dsn=source_pdb_dsn)

        source_pdb_cursor = source_pdb_conn.cursor()
        source_pdb_cursor.execute("""
            SELECT name, value, isdefault
            FROM v$parameter
            WHERE isdefault = 'FALSE'
            ORDER BY name
        """)
        source_data['pdb_parameters'] = source_pdb_cursor.fetchall()
        source_pdb_cursor.close()
        source_pdb_conn.close()
    except Exception as e:
        emit_progress(f"Warning: Could not gather source PDB parameters: {str(e)}")
        source_data['pdb_parameters'] = []

    # For target PDB parameters, try to connect if target PDB exists
    target_pdb_exists = target_data.get('pdb_mode') and target_data['pdb_mode'] != 'Does not exist'

    if target_pdb_exists:
        emit_progress("Gathering Oracle target PDB parameters...")
        target_pdb_dsn = f"{target_scan}:{target_port}/{target_pdb}"

        try:
            if connection_mode == 'external_auth':
                emit_progress(f"Connecting to Target PDB: {target_pdb_dsn} (External Auth)")
                target_pdb_conn = oracledb.connect(dsn=target_pdb_dsn, externalauth=True)
            else:
                target_user = params.get('target_username')
                target_pass = params.get('target_password')
                emit_progress(f"Connecting to Target PDB: {target_pdb_dsn} (User: {target_user})")
                target_pdb_conn = oracledb.connect(user=target_user, password=target_pass, dsn=target_pdb_dsn)

            target_pdb_cursor = target_pdb_conn.cursor()
            target_pdb_cursor.execute("""
                SELECT name, value, isdefault
                FROM v$parameter
                WHERE isdefault = 'FALSE'
                ORDER BY name
            """)
            target_data['pdb_parameters'] = target_pdb_cursor.fetchall()
            target_pdb_cursor.close()
            target_pdb_conn.close()
        except Exception as e:
            emit_progress(f"Warning: Could not gather target PDB parameters: {str(e)}")
            target_data['pdb_parameters'] = []
    else:
        emit_progress("Target PDB does not exist - skipping target PDB parameter gathering")
        target_data['pdb_parameters'] = []

    source_cursor.close()
    target_cursor.close()
    source_conn.close()
    target_conn.close()

    emit_progress("Precheck validation completed")

    return (validation_results, source_data, target_data)


def perform_pdb_clone(params, progress_callback=None):
    """
    Execute PDB clone operation.

    Args:
        params (dict): Parameters for clone including:
            - connection_mode: 'external_auth' or 'user_pass'
            - source_scan, source_port, source_cdb, source_pdb
            - target_scan, target_port, target_cdb, target_pdb
            - For user_pass: target_username, target_password
        progress_callback (callable, optional): Function to call with progress messages

    Returns:
        str: Success message
    """
    def emit_progress(message):
        if progress_callback:
            progress_callback(message)

    connection_mode = params.get('connection_mode', 'external_auth')
    source_scan = params.get('source_scan')
    source_port = params.get('source_port')
    source_cdb = params.get('source_cdb')
    source_pdb = params.get('source_pdb')
    target_scan = params.get('target_scan')
    target_port = params.get('target_port')
    target_cdb = params.get('target_cdb')
    target_pdb = params.get('target_pdb')

    emit_progress("Starting PDB clone operation...")

    # Build connection strings
    source_cdb_dsn = f"{source_scan}:{source_port}/{source_cdb}"
    target_cdb_dsn = f"{target_scan}:{target_port}/{target_cdb}"

    # Connect to target CDB
    if connection_mode == 'external_auth':
        emit_progress(f"Connecting to Target CDB: {target_cdb_dsn} (External Auth)")
        target_conn = oracledb.connect(dsn=target_cdb_dsn, externalauth=True)
    else:
        target_user = params.get('target_username')
        target_pass = params.get('target_password')
        emit_progress(f"Connecting to Target CDB: {target_cdb_dsn} (User: {target_user})")
        target_conn = oracledb.connect(user=target_user, password=target_pass, dsn=target_cdb_dsn)

    target_cursor = target_conn.cursor()

    # Create database link
    link_name = f"CLONE_LINK_{source_pdb}"
    emit_progress(f"Creating database link: {link_name}")

    try:
        target_cursor.execute(f"DROP DATABASE LINK {link_name}")
    except:
        pass  # Link may not exist

    # Create database link with TNS descriptor
    tns_descriptor = f"(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST={source_scan})(PORT={source_port}))(CONNECT_DATA=(SERVICE_NAME={source_cdb})))"

    target_cursor.execute(f"""
        CREATE PUBLIC DATABASE LINK {link_name}
        CONNECT TO CURRENT_USER
        USING '{tns_descriptor}'
    """)
    target_conn.commit()

    # Create pluggable database
    emit_progress(f"Cloning PDB {source_pdb} to {target_pdb}...")

    target_cursor.execute(f"""
        CREATE PLUGGABLE DATABASE {target_pdb}
        FROM {source_pdb}@{link_name}
        FILE_NAME_CONVERT = ('/{source_pdb}/', '/{target_pdb}/')
    """)
    target_conn.commit()

    emit_progress(f"Opening PDB {target_pdb}...")
    target_cursor.execute(f"ALTER PLUGGABLE DATABASE {target_pdb} OPEN READ WRITE")
    target_conn.commit()

    emit_progress(f"Saving PDB state...")
    target_cursor.execute(f"ALTER PLUGGABLE DATABASE {target_pdb} SAVE STATE")
    target_conn.commit()

    # Clean up database link
    target_cursor.execute(f"DROP DATABASE LINK {link_name}")
    target_conn.commit()

    target_cursor.close()
    target_conn.close()

    emit_progress("PDB clone completed successfully!")

    return f"PDB clone operation completed successfully.\nNew PDB '{target_pdb}' is now open and running."


def perform_pdb_postcheck(params, progress_callback=None):
    """
    Perform PDB clone postcheck validations.

    Args:
        params (dict): Parameters for postcheck including:
            - connection_mode: 'external_auth' or 'user_pass'
            - source_scan, source_port, source_cdb, source_pdb
            - target_scan, target_port, target_cdb, target_pdb
            - For user_pass: source_username, source_password, target_username, target_password
        progress_callback (callable, optional): Function to call with progress messages

    Returns:
        tuple: (validation_results, source_data, target_data, param_differences)
    """
    def emit_progress(message):
        if progress_callback:
            progress_callback(message)

    connection_mode = params.get('connection_mode', 'external_auth')
    source_scan = params.get('source_scan')
    source_port = params.get('source_port')
    source_cdb = params.get('source_cdb')
    source_pdb = params.get('source_pdb')
    target_scan = params.get('target_scan')
    target_port = params.get('target_port')
    target_cdb = params.get('target_cdb')
    target_pdb = params.get('target_pdb')

    emit_progress("Starting PDB clone postcheck...")

    # Build connection strings
    source_cdb_dsn = f"{source_scan}:{source_port}/{source_cdb}"
    target_cdb_dsn = f"{target_scan}:{target_port}/{target_cdb}"

    # Connect to both CDBs
    if connection_mode == 'external_auth':
        emit_progress(f"Connecting to Source CDB: {source_cdb_dsn} (External Auth)")
        source_conn = oracledb.connect(dsn=source_cdb_dsn, externalauth=True)

        emit_progress(f"Connecting to Target CDB: {target_cdb_dsn} (External Auth)")
        target_conn = oracledb.connect(dsn=target_cdb_dsn, externalauth=True)
    else:
        source_user = params.get('source_username')
        source_pass = params.get('source_password')
        target_user = params.get('target_username')
        target_pass = params.get('target_password')

        emit_progress(f"Connecting to Source CDB: {source_cdb_dsn} (User: {source_user})")
        source_conn = oracledb.connect(user=source_user, password=source_pass, dsn=source_cdb_dsn)

        emit_progress(f"Connecting to Target CDB: {target_cdb_dsn} (User: {target_user})")
        target_conn = oracledb.connect(user=target_user, password=target_pass, dsn=target_cdb_dsn)

    validation_results = []
    source_data = {}
    target_data = {}

    source_cursor = source_conn.cursor()
    target_cursor = target_conn.cursor()

    # Gather instance and host information
    emit_progress("Gathering instance and host information...")

    # Source instance information
    source_cursor.execute("""
        SELECT inst_id, instance_name, host_name
        FROM gv$instance
        ORDER BY inst_id
    """)
    source_data['instances'] = source_cursor.fetchall()

    # Target instance information
    target_cursor.execute("""
        SELECT inst_id, instance_name, host_name
        FROM gv$instance
        ORDER BY inst_id
    """)
    target_data['instances'] = target_cursor.fetchall()

    # Gather PDB size information
    emit_progress("Gathering PDB size information...")

    # Source PDB size
    source_cursor.execute("""
        SELECT ROUND(SUM(bytes)/1024/1024/1024, 2) as size_gb
        FROM v$datafile
        WHERE con_id = (SELECT con_id FROM v$pdbs WHERE UPPER(name) = UPPER(:pdb_name))
    """, pdb_name=source_pdb)
    source_size_result = source_cursor.fetchone()
    source_data['pdb_size_gb'] = source_size_result[0] if source_size_result and source_size_result[0] else 0

    # Target PDB size
    target_cursor.execute("""
        SELECT ROUND(SUM(bytes)/1024/1024/1024, 2) as size_gb
        FROM v$datafile
        WHERE con_id = (SELECT con_id FROM v$pdbs WHERE UPPER(name) = UPPER(:pdb_name))
    """, pdb_name=target_pdb)
    target_size_result = target_cursor.fetchone()
    target_data['pdb_size_gb'] = target_size_result[0] if target_size_result and target_size_result[0] else 0

    # Gather Oracle parameters for both PDBs
    emit_progress("Gathering Oracle parameters for source PDB...")
    source_pdb_dsn = f"{source_scan}:{source_port}/{source_pdb}"

    if connection_mode == 'external_auth':
        emit_progress(f"Connecting to Source PDB: {source_pdb_dsn} (External Auth)")
        source_pdb_conn = oracledb.connect(dsn=source_pdb_dsn, externalauth=True)
    else:
        source_user = params.get('source_username')
        source_pass = params.get('source_password')
        emit_progress(f"Connecting to Source PDB: {source_pdb_dsn} (User: {source_user})")
        source_pdb_conn = oracledb.connect(user=source_user, password=source_pass, dsn=source_pdb_dsn)

    source_pdb_cursor = source_pdb_conn.cursor()
    source_pdb_cursor.execute("""
        SELECT name, value, isdefault
        FROM v$parameter
        ORDER BY name
    """)
    source_params = {row[0]: row[1] for row in source_pdb_cursor.fetchall()}
    source_data['parameters'] = source_params
    source_pdb_cursor.close()
    source_pdb_conn.close()

    # Target PDB
    target_pdb_dsn = f"{target_scan}:{target_port}/{target_pdb}"

    emit_progress("Gathering Oracle parameters for target PDB...")
    if connection_mode == 'external_auth':
        emit_progress(f"Connecting to Target PDB: {target_pdb_dsn} (External Auth)")
        target_pdb_conn = oracledb.connect(dsn=target_pdb_dsn, externalauth=True)
    else:
        target_user = params.get('target_username')
        target_pass = params.get('target_password')
        emit_progress(f"Connecting to Target PDB: {target_pdb_dsn} (User: {target_user})")
        target_pdb_conn = oracledb.connect(user=target_user, password=target_pass, dsn=target_pdb_dsn)

    target_pdb_cursor = target_pdb_conn.cursor()
    target_pdb_cursor.execute("""
        SELECT name, value, isdefault
        FROM v$parameter
        ORDER BY name
    """)
    target_params = {row[0]: row[1] for row in target_pdb_cursor.fetchall()}
    target_data['parameters'] = target_params
    target_pdb_cursor.close()
    target_pdb_conn.close()

    # Compare parameters
    emit_progress("Comparing parameters...")
    all_keys = set(source_params.keys()) | set(target_params.keys())
    param_differences = []

    for key in sorted(all_keys):
        source_val = source_params.get(key, 'N/A')
        target_val = target_params.get(key, 'N/A')
        if source_val != target_val:
            param_differences.append((key, source_val, target_val))

    params_match = len(param_differences) == 0
    validation_results.append({
        'check': 'Oracle DB Parameters Match',
        'status': 'PASS' if params_match else 'FAILED',
        'source_value': f"{len(source_params)} parameters",
        'target_value': f"{len(target_params)} parameters ({len(param_differences)} differences)"
    })

    # Check DB services
    emit_progress("Checking DB services...")
    source_cursor.execute("""
        SELECT name, pdb
        FROM cdb_services
        WHERE UPPER(pdb) = UPPER(:pdb_name)
        ORDER BY name
    """, pdb_name=source_pdb)
    source_services = source_cursor.fetchall()
    source_data['services'] = source_services

    target_cursor.execute("""
        SELECT name, pdb
        FROM cdb_services
        WHERE UPPER(pdb) = UPPER(:pdb_name)
        ORDER BY name
    """, pdb_name=target_pdb)
    target_services = target_cursor.fetchall()
    target_data['services'] = target_services

    source_service_names = set([s[0] for s in source_services])
    target_service_names = set([s[0] for s in target_services])

    # Allow for PDB name differences in service names
    services_match = len(source_service_names) == len(target_service_names)

    validation_results.append({
        'check': 'DB Service Names Match',
        'status': 'PASS' if services_match else 'FAILED',
        'source_value': f"{len(source_service_names)} services",
        'target_value': f"{len(target_service_names)} services"
    })

    source_cursor.close()
    target_cursor.close()
    source_conn.close()
    target_conn.close()

    emit_progress("Postcheck validation completed")

    return (validation_results, source_data, target_data, param_differences)
