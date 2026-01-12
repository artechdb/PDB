"""
Oracle PDB Toolkit - Database Health Check Module
Version: 2.0.0

This module performs comprehensive database health checks including:
- Database information and version
- Session statistics
- Tablespace usage
- PDB information
- Wait events analysis
- Database load (AAS)
- Top SQL queries by CPU and disk reads
- Invalid objects
- Alert log errors
- Long-running queries
- Temporary tablespace usage
- RAC-specific checks (6 checks for RAC environments)
"""

import oracledb
from utils.db_connection import create_connection


def perform_health_check(connection_params, progress_callback=None):
    """
    Perform comprehensive database health check.

    Args:
        connection_params (dict): Database connection parameters
            For external auth:
                - connection_mode: 'external_auth'
                - db_name: TNS alias or DSN string
                - hostname: (optional) For direct connection
                - port: (optional) For direct connection
            For user/pass:
                - connection_mode: 'user_pass'
                - hostname: Database hostname
                - port: Database port
                - service: Service name
                - username: Database username
                - password: Database password
        progress_callback (callable, optional): Callback function for progress updates

    Returns:
        dict: Dictionary containing all health check results with keys:
            - db_name, open_mode, role, version
            - instances (list of instance info)
            - db_size_gb
            - max_pdb_storage, storage_pct
            - sessions, tablespaces, pdbs
            - wait_events
            - aas (Average Active Sessions)
            - service_sessions, top_sql_cpu, top_sql_disk
            - invalid_objects, alert_log_errors, long_queries
            - temp_usage
            - RAC metrics: instance_load, rac_gc_waits, rac_gc_waits_by_instance,
              rac_interconnect, rac_ges_blocking, rac_cpu_util, rac_ges_contention
    """
    def emit_progress(message):
        """Helper to emit progress if callback is provided"""
        if progress_callback:
            progress_callback(message)

    # Create connection
    connection = create_connection(connection_params)
    cursor = connection.get_cursor()

    emit_progress("Gathering database health metrics...")

    # Collect health metrics
    health_data = {}

    # 1. Database version
    cursor.execute("SELECT banner FROM v$version WHERE ROWNUM = 1")
    health_data['version'] = cursor.fetchone()[0]

    # 2. Database status
    cursor.execute("SELECT name, open_mode, database_role FROM v$database")
    db_info = cursor.fetchone()
    health_data['db_name'] = db_info[0]
    health_data['open_mode'] = db_info[1]
    health_data['role'] = db_info[2]

    # 3. Instance information (all instances for RAC)
    cursor.execute("""
        SELECT inst_id, instance_name, host_name
        FROM gv$instance
        ORDER BY inst_id
    """)
    health_data['instances'] = cursor.fetchall()

    # 4. Database size (total size of all datafiles)
    cursor.execute("""
        SELECT ROUND(SUM(bytes)/1024/1024/1024, 2) as size_gb
        FROM v$datafile
    """)
    db_size_result = cursor.fetchone()
    health_data['db_size_gb'] = db_size_result[0] if db_size_result and db_size_result[0] else 0

    # 5. MAX_PDB_STORAGE (if this is a CDB, query from a PDB; if not, mark as N/A)
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
                health_data['max_pdb_storage'] = max_pdb_result[0] if max_pdb_result and max_pdb_result[0] else 'UNLIMITED'

                # Calculate percentage if MAX_PDB_STORAGE is set and not UNLIMITED
                if health_data['max_pdb_storage'] != 'UNLIMITED':
                    storage_str = health_data['max_pdb_storage'].upper()
                    try:
                        if 'G' in storage_str:
                            max_storage_gb = float(storage_str.replace('G', ''))
                        elif 'M' in storage_str:
                            max_storage_gb = float(storage_str.replace('M', '')) / 1024
                        elif 'T' in storage_str:
                            max_storage_gb = float(storage_str.replace('T', '')) * 1024
                        else:
                            max_storage_gb = float(storage_str) / (1024**3)

                        health_data['storage_pct'] = round((health_data['db_size_gb'] / max_storage_gb) * 100, 2)
                    except (ValueError, ZeroDivisionError):
                        health_data['storage_pct'] = None
                else:
                    health_data['storage_pct'] = None

                # Switch back to CDB$ROOT
                cursor.execute("ALTER SESSION SET CONTAINER = CDB$ROOT")
            else:
                health_data['max_pdb_storage'] = 'N/A (No PDBs)'
                health_data['storage_pct'] = None
        else:
            health_data['max_pdb_storage'] = 'N/A (Non-CDB)'
            health_data['storage_pct'] = None
    except Exception:
        health_data['max_pdb_storage'] = 'Unable to query'
        health_data['storage_pct'] = None

    # 6. Tablespace usage
    cursor.execute("""
        SELECT tablespace_name,
               ROUND(used_space * 8192 / 1024 / 1024 / 1024, 2) as used_gb,
               ROUND(tablespace_size * 8192 / 1024 / 1024 / 1024, 2) as total_gb,
               ROUND(used_percent, 2) as pct_used
        FROM dba_tablespace_usage_metrics
        ORDER BY used_percent DESC
    """)
    health_data['tablespaces'] = cursor.fetchall()

    # 7. Session count
    cursor.execute("SELECT status, COUNT(*) FROM v$session GROUP BY status")
    health_data['sessions'] = cursor.fetchall()

    # 8. PDB information
    cursor.execute("""
        SELECT name, open_mode, restricted, open_time, total_size/1024/1024/1024 as size_gb
        FROM v$pdbs
        ORDER BY name
    """)
    health_data['pdbs'] = cursor.fetchall()

    # 9. Top wait events
    cursor.execute("""
        SELECT event, total_waits, time_waited, average_wait
        FROM v$system_event
        WHERE wait_class != 'Idle'
        ORDER BY time_waited DESC
        FETCH FIRST 10 ROWS ONLY
    """)
    health_data['wait_events'] = cursor.fetchall()

    # 10. Active sessions by service
    try:
        cursor.execute("""
            SELECT service_name,
                   COUNT(CASE WHEN status = 'ACTIVE' THEN 1 END) as active_sessions,
                   COUNT(CASE WHEN status = 'INACTIVE' THEN 1 END) as inactive_sessions,
                   COUNT(*) as total_sessions
            FROM gv$session
            WHERE type = 'USER'
              AND service_name NOT IN ('SYS$BACKGROUND', 'SYS$USERS')
            GROUP BY service_name
            ORDER BY active_sessions DESC, total_sessions DESC
        """)
        health_data['service_sessions'] = cursor.fetchall()
    except Exception:
        health_data['service_sessions'] = []

    # 11. Database Load (AAS - Average Active Sessions)
    try:
        cursor.execute("""
            SELECT ROUND(COUNT(*) / 5, 2) as aas
            FROM gv$active_session_history
            WHERE sample_time > SYSDATE - INTERVAL '5' MINUTE
        """)
        aas_result = cursor.fetchone()
        health_data['aas'] = aas_result[0] if aas_result and aas_result[0] else 0
    except Exception:
        health_data['aas'] = 0

    # 12. Top SQL by CPU
    try:
        cursor.execute("""
            SELECT sql_id,
                   ROUND(cpu_time / 1000000, 2) as cpu_seconds,
                   executions,
                   ROUND(cpu_time / 1000000 / NULLIF(executions, 0), 2) as cpu_per_exec
            FROM v$sql
            WHERE cpu_time > 0
            ORDER BY cpu_time DESC
            FETCH FIRST 10 ROWS ONLY
        """)
        health_data['top_sql_cpu'] = cursor.fetchall()
    except Exception:
        health_data['top_sql_cpu'] = []

    # 13. Top SQL by Disk Reads
    try:
        cursor.execute("""
            SELECT sql_id,
                   disk_reads,
                   executions,
                   ROUND(disk_reads / NULLIF(executions, 0), 2) as reads_per_exec
            FROM v$sql
            WHERE disk_reads > 0
            ORDER BY disk_reads DESC
            FETCH FIRST 10 ROWS ONLY
        """)
        health_data['top_sql_disk'] = cursor.fetchall()
    except Exception:
        health_data['top_sql_disk'] = []

    # 14. Invalid Objects
    try:
        cursor.execute("""
            SELECT owner,
                   object_type,
                   COUNT(*) as invalid_count
            FROM dba_objects
            WHERE status = 'INVALID'
              AND owner NOT IN ('SYS', 'SYSTEM', 'AUDSYS', 'LBACSYS', 'XDB')
            GROUP BY owner, object_type
            ORDER BY invalid_count DESC
        """)
        health_data['invalid_objects'] = cursor.fetchall()
    except Exception:
        health_data['invalid_objects'] = []

    # 15. Alert Log Errors (recent ORA- errors from alert log view if available)
    try:
        cursor.execute("""
            SELECT TO_CHAR(originating_timestamp, 'YYYY-MM-DD HH24:MI:SS') as error_time,
                   message_text
            FROM v$diag_alert_ext
            WHERE originating_timestamp > SYSDATE - 1/24
              AND message_text LIKE '%ORA-%'
            ORDER BY originating_timestamp DESC
            FETCH FIRST 20 ROWS ONLY
        """)
        health_data['alert_log_errors'] = cursor.fetchall()
    except Exception:
        health_data['alert_log_errors'] = []

    # 16. RAC-specific: Instance load distribution (if RAC)
    try:
        cursor.execute("""
            SELECT inst_id,
                   instance_name,
                   ROUND(value / 1000000, 2) as db_time_seconds
            FROM gv$sys_time_model
            WHERE stat_name = 'DB time'
            ORDER BY inst_id
        """)
        instance_load = cursor.fetchall()
        if len(instance_load) > 1:  # Only add if RAC (multiple instances)
            health_data['instance_load'] = instance_load
        else:
            health_data['instance_load'] = []
    except Exception:
        health_data['instance_load'] = []

    # 17. Long Running Queries (running > 5 minutes)
    try:
        cursor.execute("""
            SELECT s.inst_id,
                   s.sid,
                   s.serial#,
                   s.username,
                   s.sql_id,
                   ROUND((SYSDATE - s.sql_exec_start) * 24 * 60, 2) as elapsed_minutes,
                   s.status
            FROM gv$session s
            WHERE s.status = 'ACTIVE'
              AND s.type = 'USER'
              AND s.sql_exec_start IS NOT NULL
              AND (SYSDATE - s.sql_exec_start) * 24 * 60 > 5
            ORDER BY elapsed_minutes DESC
        """)
        health_data['long_queries'] = cursor.fetchall()
    except Exception:
        health_data['long_queries'] = []

    # 18. Temp Tablespace Usage
    try:
        cursor.execute("""
            SELECT tablespace_name,
                   ROUND(SUM(bytes_used) / 1024 / 1024 / 1024, 2) as used_gb,
                   ROUND(SUM(bytes_free) / 1024 / 1024 / 1024, 2) as free_gb,
                   ROUND(SUM(bytes_used) * 100 / NULLIF(SUM(bytes_used + bytes_free), 0), 2) as pct_used
            FROM v$temp_space_header
            GROUP BY tablespace_name
            ORDER BY pct_used DESC
        """)
        health_data['temp_usage'] = cursor.fetchall()
    except Exception:
        health_data['temp_usage'] = []

    # 19. RAC-specific: Global Cache Waits (Top GC Events)
    try:
        cursor.execute("""
            SELECT event,
                   COUNT(*) as samples,
                   ROUND(COUNT(*) * 100 / SUM(COUNT(*)) OVER (), 2) as pct
            FROM gv$active_session_history
            WHERE event LIKE 'gc%'
              AND sample_time > SYSDATE - INTERVAL '1' HOUR
            GROUP BY event
            ORDER BY samples DESC
            FETCH FIRST 10 ROWS ONLY
        """)
        gc_waits = cursor.fetchall()
        if gc_waits and len(health_data.get('instances', [])) > 1:  # Only add if RAC
            health_data['rac_gc_waits'] = gc_waits
        else:
            health_data['rac_gc_waits'] = []
    except Exception:
        health_data['rac_gc_waits'] = []

    # 20. RAC-specific: GC Waits by Instance
    try:
        cursor.execute("""
            SELECT inst_id,
                   event,
                   COUNT(*) as wait_count
            FROM gv$active_session_history
            WHERE event LIKE 'gc%'
              AND sample_time > SYSDATE - INTERVAL '1' HOUR
            GROUP BY inst_id, event
            ORDER BY inst_id, wait_count DESC
        """)
        gc_waits_inst = cursor.fetchall()
        if gc_waits_inst and len(health_data.get('instances', [])) > 1:
            health_data['rac_gc_waits_by_instance'] = gc_waits_inst
        else:
            health_data['rac_gc_waits_by_instance'] = []
    except Exception:
        health_data['rac_gc_waits_by_instance'] = []

    # 21. RAC-specific: Interconnect Activity
    try:
        cursor.execute("""
            SELECT inst_id,
                   name,
                   ROUND(value / 1024 / 1024, 2) as mb
            FROM gv$sysstat
            WHERE name IN (
                'gc current blocks received',
                'gc cr blocks received',
                'gc current blocks served',
                'gc cr blocks served'
            )
            ORDER BY inst_id, name
        """)
        interconnect = cursor.fetchall()
        if interconnect and len(health_data.get('instances', [])) > 1:
            health_data['rac_interconnect'] = interconnect
        else:
            health_data['rac_interconnect'] = []
    except Exception:
        health_data['rac_interconnect'] = []

    # 22. RAC-specific: GES Blocking Sessions
    try:
        cursor.execute("""
            SELECT blocking_session,
                   blocking_inst_id,
                   COUNT(*) as blocks,
                   TO_CHAR(MIN(sample_time), 'YYYY-MM-DD HH24:MI') as first_seen,
                   TO_CHAR(MAX(sample_time), 'YYYY-MM-DD HH24:MI') as last_seen
            FROM gv$active_session_history
            WHERE blocking_session IS NOT NULL
              AND sample_time > SYSDATE - INTERVAL '1' HOUR
            GROUP BY blocking_session, blocking_inst_id
            ORDER BY blocks DESC
            FETCH FIRST 10 ROWS ONLY
        """)
        ges_blocking = cursor.fetchall()
        if ges_blocking and len(health_data.get('instances', [])) > 1:
            health_data['rac_ges_blocking'] = ges_blocking
        else:
            health_data['rac_ges_blocking'] = []
    except Exception:
        health_data['rac_ges_blocking'] = []

    # 23. RAC-specific: CPU Utilization per Instance
    try:
        cursor.execute("""
            WITH os_stat AS (
                SELECT inst_id,
                       MAX(CASE WHEN stat_name = 'BUSY_TIME' THEN value END) as busy_time,
                       MAX(CASE WHEN stat_name = 'IDLE_TIME' THEN value END) as idle_time
                FROM gv$osstat
                WHERE stat_name IN ('BUSY_TIME', 'IDLE_TIME')
                GROUP BY inst_id
            )
            SELECT inst_id,
                   ROUND(busy_time / 100, 2) as cpu_busy_secs,
                   ROUND((busy_time + idle_time) / 100, 2) as total_cpu_secs,
                   ROUND((busy_time / NULLIF(busy_time + idle_time, 0)) * 100, 2) as cpu_util_pct
            FROM os_stat
            ORDER BY inst_id
        """)
        cpu_util = cursor.fetchall()
        if cpu_util and len(health_data.get('instances', [])) > 1:
            health_data['rac_cpu_util'] = cpu_util
        else:
            health_data['rac_cpu_util'] = []
    except Exception:
        health_data['rac_cpu_util'] = []

    # 24. RAC-specific: Global Enqueue Contention
    try:
        cursor.execute("""
            SELECT event,
                   COUNT(*) as samples
            FROM gv$active_session_history
            WHERE event LIKE 'ges%'
              AND sample_time > SYSDATE - INTERVAL '1' HOUR
            GROUP BY event
            ORDER BY samples DESC
        """)
        ges_contention = cursor.fetchall()
        if ges_contention and len(health_data.get('instances', [])) > 1:
            health_data['rac_ges_contention'] = ges_contention
        else:
            health_data['rac_ges_contention'] = []
    except Exception:
        health_data['rac_ges_contention'] = []

    cursor.close()
    connection.close()

    emit_progress("Health check data collection completed")

    return health_data
