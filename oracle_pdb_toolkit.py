"""
Oracle PDB Management Toolkit
A comprehensive GUI application for Oracle Pluggable Database administration
Supports DB Health Check and PDB Clone operations with external authentication
"""

import sys
import os
import traceback
import signal
import webbrowser
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QLineEdit,
                             QTextEdit, QGroupBox, QMessageBox, QTabWidget,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QRadioButton, QButtonGroup)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
import oracledb

# Initialize Oracle Client in Thick Mode (required for DB Links and external auth)
# CRITICAL: This must be called before any connection attempts
try:
    # Try to initialize thick mode with common Oracle Client locations
    import platform
    if platform.system() == 'Windows':
        # Check ORACLE_HOME environment variable first
        import os
        oracle_home = os.environ.get('ORACLE_HOME')

        # Common Windows locations for Oracle Instant Client and Full Client
        possible_paths = []

        # Add ORACLE_HOME if set
        if oracle_home:
            possible_paths.append(oracle_home)
            # Also try bin subdirectory for full client installations
            possible_paths.append(os.path.join(oracle_home, 'bin'))

        # Add common instant client locations
        possible_paths.extend([
            r"C:\oracle\instantclient_19_8",
            r"C:\oracle\instantclient_21_3",
            r"C:\instantclient_19_8",
            r"C:\instantclient_21_3",
            r"C:\Users\user\Downloads\WINDOWS.X64_213000_client_home",
            r"C:\Users\user\Downloads\WINDOWS.X64_213000_client_home\bin"
        ])

        # Finally try auto-detect
        possible_paths.append(None)

        initialized = False
        last_error = None
        for lib_dir in possible_paths:
            try:
                if lib_dir:
                    oracledb.init_oracle_client(lib_dir=lib_dir)
                    print(f"Oracle Client initialized in Thick Mode: {lib_dir}")
                else:
                    oracledb.init_oracle_client()
                    print("Oracle Client initialized in Thick Mode: auto-detected")
                initialized = True
                break
            except Exception as e:
                last_error = e
                continue

        if not initialized:
            raise Exception(f"Could not initialize Oracle Client. Last error: {last_error}")
    else:
        oracledb.init_oracle_client()
        print("Oracle Client initialized in Thick Mode")
except Exception as e:
    print(f"WARNING: Oracle Client initialization failed: {e}")
    print("Thick mode is required for external authentication and database links.")
    print(f"ORACLE_HOME is set to: {os.environ.get('ORACLE_HOME', 'Not Set')}")
    print("Please ensure Oracle Client libraries are accessible.")


class DatabaseWorker(QThread):
    """Background worker thread for database operations"""
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(str)

    def __init__(self, operation, params):
        super().__init__()
        self.operation = operation
        self.params = params

    def run(self):
        try:
            if self.operation == "health_check":
                result = self.perform_health_check()
            elif self.operation == "pdb_precheck":
                result = self.perform_pdb_precheck()
            elif self.operation == "pdb_clone":
                result = self.perform_pdb_clone()
            elif self.operation == "pdb_postcheck":
                result = self.perform_pdb_postcheck()
            else:
                self.finished.emit(False, "Unknown operation")
                return

            self.finished.emit(True, result)
        except Exception as e:
            self.finished.emit(False, f"Error: {str(e)}\n{traceback.format_exc()}")

    def perform_health_check(self):
        """Generate database performance health HTML report"""
        connection_mode = self.params.get('connection_mode', 'external_auth')

        # Connect based on mode
        if connection_mode == 'external_auth':
            db_name = self.params.get('db_name')

            # Check if hostname/port was provided (vs TNS alias)
            hostname = self.params.get('hostname')
            if hostname:
                # Direct connection with hostname/port using external auth
                self.progress.emit(f"Connecting to database: {db_name} (External Auth)")
                connection = oracledb.connect(dsn=db_name, externalauth=True)
            else:
                # TNS alias connection
                self.progress.emit(f"Connecting to database: {db_name} (External Auth - TNS)")
                connection = oracledb.connect(dsn=db_name, externalauth=True)

        else:  # user_pass mode
            hostname = self.params.get('hostname')
            port = self.params.get('port')
            service = self.params.get('service')
            username = self.params.get('username')
            password = self.params.get('password')

            self.progress.emit(f"Connecting to {service} at {hostname}:{port}")

            # Build DSN string
            dsn = f"{hostname}:{port}/{service}"
            connection = oracledb.connect(user=username, password=password, dsn=dsn)

        cursor = connection.cursor()

        self.progress.emit("Gathering database health metrics...")

        # Collect health metrics
        health_data = {}

        # Database version
        cursor.execute("SELECT banner FROM v$version WHERE ROWNUM = 1")
        health_data['version'] = cursor.fetchone()[0]

        # Database status
        cursor.execute("SELECT name, open_mode, database_role FROM v$database")
        db_info = cursor.fetchone()
        health_data['db_name'] = db_info[0]
        health_data['open_mode'] = db_info[1]
        health_data['role'] = db_info[2]

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
        health_data['db_size_gb'] = db_size_result[0] if db_size_result and db_size_result[0] else 0

        # MAX_PDB_STORAGE (if this is a CDB, query from a PDB; if not, mark as N/A)
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

        # Tablespace usage
        cursor.execute("""
            SELECT tablespace_name,
                   ROUND(used_space * 8192 / 1024 / 1024 / 1024, 2) as used_gb,
                   ROUND(tablespace_size * 8192 / 1024 / 1024 / 1024, 2) as total_gb,
                   ROUND(used_percent, 2) as pct_used
            FROM dba_tablespace_usage_metrics
            ORDER BY used_percent DESC
        """)
        health_data['tablespaces'] = cursor.fetchall()

        # Session count
        cursor.execute("SELECT status, COUNT(*) FROM v$session GROUP BY status")
        health_data['sessions'] = cursor.fetchall()

        # PDB information
        cursor.execute("""
            SELECT name, open_mode, restricted, open_time, total_size/1024/1024/1024 as size_gb
            FROM v$pdbs
            ORDER BY name
        """)
        health_data['pdbs'] = cursor.fetchall()

        # Top wait events
        cursor.execute("""
            SELECT event, total_waits, time_waited, average_wait
            FROM v$system_event
            WHERE wait_class != 'Idle'
            ORDER BY time_waited DESC
            FETCH FIRST 10 ROWS ONLY
        """)
        health_data['wait_events'] = cursor.fetchall()

        # Active sessions by service (from health_check.sh)
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

        # Database Load (AAS - Average Active Sessions)
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

        # Top SQL by CPU
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

        # Top SQL by Disk Reads
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

        # Invalid Objects
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

        # Alert Log Errors (recent ORA- errors from alert log view if available)
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

        # RAC-specific: Instance load distribution (if RAC)
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

        # Long Running Queries (running > 5 minutes)
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

        # Temp Tablespace Usage
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

        # RAC-specific: Global Cache Waits (Top GC Events)
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

        # RAC-specific: GC Waits by Instance
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

        # RAC-specific: Interconnect Activity
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

        # RAC-specific: GES Blocking Sessions
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

        # RAC-specific: CPU Utilization per Instance
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

        # RAC-specific: Global Enqueue Contention
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

        # Generate HTML report
        report_path = self.generate_health_report_html(health_data)
        self.progress.emit(f"Report generated: {report_path}")

        return f"Health check completed successfully.\nReport: {report_path}"

    def perform_pdb_precheck(self):
        """Perform PDB clone precheck validations"""
        connection_mode = self.params.get('connection_mode', 'external_auth')
        source_scan = self.params.get('source_scan')
        source_port = self.params.get('source_port')
        source_cdb = self.params.get('source_cdb')
        source_pdb = self.params.get('source_pdb')
        target_scan = self.params.get('target_scan')
        target_port = self.params.get('target_port')
        target_cdb = self.params.get('target_cdb')
        target_pdb = self.params.get('target_pdb')

        self.progress.emit("Starting PDB clone precheck...")

        # Build connection strings
        source_cdb_dsn = f"{source_scan}:{source_port}/{source_cdb}"
        target_cdb_dsn = f"{target_scan}:{target_port}/{target_cdb}"

        # Connect to both CDBs
        if connection_mode == 'external_auth':
            self.progress.emit(f"Connecting to Source CDB: {source_cdb_dsn} (External Auth)")
            source_conn = oracledb.connect(dsn=source_cdb_dsn, externalauth=True)

            self.progress.emit(f"Connecting to Target CDB: {target_cdb_dsn} (External Auth)")
            target_conn = oracledb.connect(dsn=target_cdb_dsn, externalauth=True)
        else:
            source_user = self.params.get('source_username')
            source_pass = self.params.get('source_password')
            target_user = self.params.get('target_username')
            target_pass = self.params.get('target_password')

            self.progress.emit(f"Connecting to Source CDB: {source_cdb_dsn} (User: {source_user})")
            source_conn = oracledb.connect(user=source_user, password=source_pass, dsn=source_cdb_dsn)

            self.progress.emit(f"Connecting to Target CDB: {target_cdb_dsn} (User: {target_user})")
            target_conn = oracledb.connect(user=target_user, password=target_pass, dsn=target_cdb_dsn)

        validation_results = []
        source_data = {}
        target_data = {}

        # Gather instance and host information using gv$ views
        self.progress.emit("Gathering instance and host information...")
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
        self.progress.emit("Gathering PDB size information...")

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
        self.progress.emit("Checking database versions...")

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
        self.progress.emit("Checking character sets...")
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
        self.progress.emit("Checking DB registry components...")
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
        self.progress.emit("Checking source PDB status...")
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
        self.progress.emit("Checking target PDB status...")
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
        self.progress.emit("Checking TDE configuration...")
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
        self.progress.emit("Checking undo mode...")
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
        self.progress.emit("Checking MAX_STRING_SIZE compatibility...")
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
        self.progress.emit("Checking timezone settings...")
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
        self.progress.emit("Checking MAX_PDB_STORAGE limit...")

        # MAX_PDB_STORAGE is a PDB-level property in database_properties
        # Need to query from source PDB (not CDB) and compare with target PDB
        try:
            # Connect to source PDB to get its MAX_PDB_STORAGE
            source_pdb_dsn_temp = f"{source_scan}:{source_port}/{source_pdb}"
            if connection_mode == 'external_auth':
                source_pdb_conn_temp = oracledb.connect(dsn=source_pdb_dsn_temp, externalauth=True)
            else:
                source_user = self.params.get('source_username')
                source_pass = self.params.get('source_password')
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
                    target_user = self.params.get('target_username')
                    target_pass = self.params.get('target_password')
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
            self.progress.emit(f"WARNING: Could not check MAX_PDB_STORAGE: {str(e)}")
            validation_results.append({
                'check': 'MAX_PDB_STORAGE Limit',
                'status': 'SKIPPED',
                'source_value': f"{source_data['pdb_size_gb']} GB",
                'target_value': 'Could not verify (connection issue)'
            })

        # Check 10: DBMS_PDB.CHECK_PLUG_COMPATIBILITY
        self.progress.emit("Checking plug compatibility (using CLOB method)...")

        # Use CLOB-based method instead of file-based
        # This works across platforms without needing file system access
        try:
            # IMPORTANT: DBMS_PDB.DESCRIBE must be run from the CDB context (not PDB)
            # We use the existing source_cursor which is already connected to the CDB
            self.progress.emit(f"DEBUG: Using CDB connection for DBMS_PDB.DESCRIBE")
            self.progress.emit(f"DEBUG: Source CDB DSN = {source_scan}:{source_port}/{source_cdb}")

            # Verify we're connected to CDB
            source_cursor.execute("SELECT sys_context('USERENV', 'CON_NAME') FROM dual")
            current_container = source_cursor.fetchone()[0]
            self.progress.emit(f"DEBUG: Current container context = {current_container}")

            # Query the actual DBMS_PDB.DESCRIBE signature from the database
            self.progress.emit(f"DEBUG: Querying DBMS_PDB.DESCRIBE signature from database...")
            source_cursor.execute("""
                SELECT argument_name, position, data_type, in_out, data_level, overload
                FROM all_arguments
                WHERE owner = 'SYS'
                AND package_name = 'DBMS_PDB'
                AND object_name = 'DESCRIBE'
                ORDER BY overload NULLS FIRST, position
            """)
            describe_signature = source_cursor.fetchall()

            self.progress.emit(f"DEBUG: DBMS_PDB.DESCRIBE signature in this Oracle version:")

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

                    self.progress.emit(f"DEBUG:   Overload {overload_num}, Position {arg[1]}: {arg_name} ({arg[2]}, {arg[3]}, Level={arg[4]})")

                # Check each overload
                for overload_num, params in overloads.items():
                    # Check if this overload is CLOB-based (first param is CLOB OUT)
                    if params:
                        # Find the parameter at position 1 (first parameter)
                        first_param = None
                        for param in params:
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
                                self.progress.emit(f"DEBUG: Found CLOB-based overload (Overload {overload_num}): {param_name} ({param_type} {param_direction})")
                            # File overload: PDB_DESCR_FILE VARCHAR2 IN
                            elif param_type == 'VARCHAR2' and param_direction == 'IN' and 'FILE' in str(param_name).upper():
                                has_file_overload = True
                                self.progress.emit(f"DEBUG: Found file-based overload (Overload {overload_num}): {param_name} ({param_type} {param_direction})")
            else:
                self.progress.emit(f"DEBUG:   No signature found - DESCRIBE procedure may not exist!")

            # Note: Even if all_arguments only shows file-based signature,
            # Oracle 19c+ may still support CLOB overload
            # We'll try CLOB methods first, and only skip if they all fail
            if has_file_overload and not has_clob_overload:
                self.progress.emit(f"")
                self.progress.emit(f"INFO: all_arguments shows file-based signature")
                self.progress.emit(f"INFO: However, Oracle 19c+ typically supports CLOB overload")
                self.progress.emit(f"INFO: Attempting CLOB-based methods first...")
                self.progress.emit(f"")

            # Create CLOB variable for XML output
            xml_var = source_cursor.var(oracledb.DB_TYPE_CLOB)
            self.progress.emit(f"DEBUG: Created CLOB variable for XML output")

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

            self.progress.emit(f"DEBUG: Attempting Method 1 - CLOB with PDB name from CDB (Oracle 19c+)...")
            self.progress.emit(f"DEBUG: PL/SQL Block:\n{plsql_block_method1}")

            method_succeeded = False
            try:
                source_cursor.execute(plsql_block_method1, xml_output=xml_var, pdb_name=source_pdb)
                self.progress.emit(f"DEBUG: Method 1 succeeded!")
                method_succeeded = True
            except Exception as e1:
                self.progress.emit(f"DEBUG: Method 1 failed: {str(e1)}")
                self.progress.emit(f"DEBUG: Attempting Method 2 - CLOB positional with PDB name (Oracle 12c)...")
                self.progress.emit(f"DEBUG: PL/SQL Block:\n{plsql_block_method2}")

                try:
                    # Reset CLOB variable
                    xml_var = source_cursor.var(oracledb.DB_TYPE_CLOB)
                    source_cursor.execute(plsql_block_method2, xml_output=xml_var, pdb_name=source_pdb)
                    self.progress.emit(f"DEBUG: Method 2 succeeded!")
                    method_succeeded = True
                except Exception as e2:
                    self.progress.emit(f"DEBUG: Method 2 also failed: {str(e2)}")
                    self.progress.emit(f"DEBUG: Attempting Method 3 - Positional CLOB and PDB name (Oracle 12c alt)...")
                    self.progress.emit(f"DEBUG: PL/SQL Block:\n{plsql_block_method3}")

                    try:
                        # Reset CLOB variable
                        xml_var = source_cursor.var(oracledb.DB_TYPE_CLOB)
                        source_cursor.execute(plsql_block_method3, xml_output=xml_var, pdb_name=source_pdb)
                        self.progress.emit(f"DEBUG: Method 3 succeeded!")
                        method_succeeded = True
                    except Exception as e3:
                        self.progress.emit(f"DEBUG: Method 3 also failed: {str(e3)}")
                        self.progress.emit(f"DEBUG: Attempting Method 4 - File-based with DBMS_LOB (Oracle 12c)...")
                        self.progress.emit(f"DEBUG: This method writes to DATA_PUMP_DIR and reads back")

                        try:
                            # Reset CLOB variable
                            xml_var = source_cursor.var(oracledb.DB_TYPE_CLOB)
                            source_cursor.execute(plsql_block_method4, xml_output=xml_var, pdb_name=source_pdb)
                            self.progress.emit(f"DEBUG: Method 4 succeeded!")
                            method_succeeded = True
                        except Exception as e4:
                            self.progress.emit(f"DEBUG: Method 4 also failed: {str(e4)}")
                            self.progress.emit(f"")
                            self.progress.emit(f"NOTICE: All 4 DBMS_PDB.DESCRIBE methods failed")
                            self.progress.emit(f"NOTICE: Your Oracle version appears to only support file-based approach")
                            self.progress.emit(f"NOTICE: File-based approach requires server filesystem access")
                            self.progress.emit(f"NOTICE: Skipping DBMS_PDB plug compatibility check")
                            self.progress.emit(f"")
                            self.progress.emit(f"RECOMMENDATION: Run the compatibility check manually using SQL*Plus:")
                            self.progress.emit(f"  1. Connect to source PDB: sqlplus user/pass@{source_scan}:{source_port}/{source_pdb}")
                            self.progress.emit(f"  2. Run: EXEC DBMS_PDB.DESCRIBE(pdb_descr_file => 'pdb_desc.xml', pdb_name => '{source_pdb}');")
                            self.progress.emit(f"  3. Copy pdb_desc.xml from DATA_PUMP_DIR on source to target")
                            self.progress.emit(f"  4. Connect to target CDB: sqlplus user/pass@{source_scan}:{source_port}/{target_cdb}")
                            self.progress.emit(f"  5. Run: SELECT DBMS_PDB.CHECK_PLUG_COMPATIBILITY(pdb_descr_file => 'pdb_desc.xml') FROM dual;")
                            self.progress.emit(f"")
                            # Raise a special exception to indicate we should skip gracefully
                            raise Exception("ALL_METHODS_FAILED_FILE_BASED_ONLY")

            if not method_succeeded:
                raise Exception("All DBMS_PDB.DESCRIBE methods failed")

            self.progress.emit(f"DEBUG: DBMS_PDB.DESCRIBE executed successfully")

            xml_clob = xml_var.getvalue()

            # Export XML to file for inspection
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            xml_filename = f"{source_cdb}_{source_pdb}_pdb_describe_{timestamp}.xml"

            if xml_clob:
                xml_content = xml_clob.read() if hasattr(xml_clob, 'read') else str(xml_clob)
                with open(xml_filename, 'w', encoding='utf-8') as f:
                    f.write(xml_content)
                self.progress.emit(f"DEBUG: XML exported to file: {xml_filename}")
                self.progress.emit(f"DEBUG: XML length = {len(xml_content)} characters")
            else:
                self.progress.emit(f"DEBUG: WARNING - XML CLOB is empty/None!")

            # No need to close - using existing CDB connection
            self.progress.emit(f"DEBUG: DBMS_PDB.DESCRIBE completed from CDB context")

            # Check compatibility on target using the XML CLOB
            self.progress.emit(f"DEBUG: Running DBMS_PDB.CHECK_PLUG_COMPATIBILITY on target CDB...")

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

            self.progress.emit(f"DEBUG: Executing CHECK_PLUG_COMPATIBILITY...")
            target_cursor.execute(check_compat_block, xml_input=xml_clob, result=result_var)

            compatibility_result = result_var.getvalue()
            self.progress.emit(f"DEBUG: Compatibility check result = {compatibility_result}")

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

            self.progress.emit(f"DEBUG: Compatibility check completed successfully")

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
                self.progress.emit(f"INFO: Continuing with remaining validation checks...")

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

                self.progress.emit(f"ERROR: Plug compatibility check failed!")
                self.progress.emit(f"ERROR: Exception type: {type(e).__name__}")
                self.progress.emit(f"ERROR: Exception message: {str(e)}")
                self.progress.emit(f"ERROR: Full traceback:")
                for line in error_details.split('\n'):
                    if line.strip():
                        self.progress.emit(f"  {line}")

                validation_results.append({
                    'check': 'DBMS_PDB Plug Compatibility',
                    'status': 'SKIPPED',
                    'source_value': 'Check failed',
                    'target_value': f'Error: {str(e)}',
                    'violations': []
                })

        # Gather Oracle CDB parameters for comparison
        self.progress.emit("Gathering Oracle CDB parameters...")
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

        # Gather Oracle PDB parameters for comparison
        # Note: During precheck, target PDB doesn't exist yet, so we can only gather from source PDB
        self.progress.emit("Gathering Oracle source PDB parameters...")

        # Connect directly to source PDB using hostname:port/pdb_name format
        source_pdb_dsn = f"{source_scan}:{source_port}/{source_pdb}"

        try:
            if connection_mode == 'external_auth':
                self.progress.emit(f"Connecting to Source PDB: {source_pdb_dsn} (External Auth)")
                source_pdb_conn = oracledb.connect(dsn=source_pdb_dsn, externalauth=True)
            else:
                source_user = self.params.get('source_username')
                source_pass = self.params.get('source_password')
                self.progress.emit(f"Connecting to Source PDB: {source_pdb_dsn} (User: {source_user})")
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
            self.progress.emit(f"Warning: Could not gather source PDB parameters: {str(e)}")
            source_data['pdb_parameters'] = []

        # For target PDB parameters, try to connect if target PDB exists
        # Check if target PDB exists from earlier validation
        target_pdb_exists = target_data.get('pdb_mode') and target_data['pdb_mode'] != 'Does not exist'

        if target_pdb_exists:
            # Target PDB exists, gather its parameters
            self.progress.emit("Gathering Oracle target PDB parameters...")
            target_pdb_dsn = f"{target_scan}:{target_port}/{target_pdb}"

            try:
                if connection_mode == 'external_auth':
                    self.progress.emit(f"Connecting to Target PDB: {target_pdb_dsn} (External Auth)")
                    target_pdb_conn = oracledb.connect(dsn=target_pdb_dsn, externalauth=True)
                else:
                    target_user = self.params.get('target_username')
                    target_pass = self.params.get('target_password')
                    self.progress.emit(f"Connecting to Target PDB: {target_pdb_dsn} (User: {target_user})")
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
                self.progress.emit(f"Warning: Could not gather target PDB parameters: {str(e)}")
                target_data['pdb_parameters'] = []
        else:
            # Target PDB doesn't exist yet - use empty parameters
            self.progress.emit("Target PDB does not exist - skipping target PDB parameter gathering")
            target_data['pdb_parameters'] = []

        source_cursor.close()
        target_cursor.close()
        source_conn.close()
        target_conn.close()

        # Generate HTML report
        report_path = self.generate_precheck_report_html(
            source_cdb, source_pdb, target_cdb, target_pdb,
            validation_results, source_data, target_data
        )

        self.progress.emit(f"Precheck report generated: {report_path}")

        all_passed = all(r['status'] == 'PASS' for r in validation_results)
        status = "All checks PASSED" if all_passed else "Some checks FAILED"

        return f"PDB clone precheck completed.\nStatus: {status}\nReport: {report_path}"

    def perform_pdb_clone(self):
        """Execute PDB clone operation"""
        connection_mode = self.params.get('connection_mode', 'external_auth')
        source_scan = self.params.get('source_scan')
        source_port = self.params.get('source_port')
        source_cdb = self.params.get('source_cdb')
        source_pdb = self.params.get('source_pdb')
        target_scan = self.params.get('target_scan')
        target_port = self.params.get('target_port')
        target_cdb = self.params.get('target_cdb')
        target_pdb = self.params.get('target_pdb')

        self.progress.emit("Starting PDB clone operation...")

        # Build connection strings
        source_cdb_dsn = f"{source_scan}:{source_port}/{source_cdb}"
        target_cdb_dsn = f"{target_scan}:{target_port}/{target_cdb}"

        # Connect to target CDB
        if connection_mode == 'external_auth':
            self.progress.emit(f"Connecting to Target CDB: {target_cdb_dsn} (External Auth)")
            target_conn = oracledb.connect(dsn=target_cdb_dsn, externalauth=True)
        else:
            target_user = self.params.get('target_username')
            target_pass = self.params.get('target_password')
            self.progress.emit(f"Connecting to Target CDB: {target_cdb_dsn} (User: {target_user})")
            target_conn = oracledb.connect(user=target_user, password=target_pass, dsn=target_cdb_dsn)

        target_cursor = target_conn.cursor()

        # Create database link
        link_name = f"CLONE_LINK_{source_pdb}"
        self.progress.emit(f"Creating database link: {link_name}")

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
        self.progress.emit(f"Cloning PDB {source_pdb} to {target_pdb}...")

        target_cursor.execute(f"""
            CREATE PLUGGABLE DATABASE {target_pdb}
            FROM {source_pdb}@{link_name}
            FILE_NAME_CONVERT = ('/{source_pdb}/', '/{target_pdb}/')
        """)
        target_conn.commit()

        self.progress.emit(f"Opening PDB {target_pdb}...")
        target_cursor.execute(f"ALTER PLUGGABLE DATABASE {target_pdb} OPEN READ WRITE")
        target_conn.commit()

        self.progress.emit(f"Saving PDB state...")
        target_cursor.execute(f"ALTER PLUGGABLE DATABASE {target_pdb} SAVE STATE")
        target_conn.commit()

        # Clean up database link
        target_cursor.execute(f"DROP DATABASE LINK {link_name}")
        target_conn.commit()

        target_cursor.close()
        target_conn.close()

        self.progress.emit("PDB clone completed successfully!")

        return f"PDB clone operation completed successfully.\nNew PDB '{target_pdb}' is now open and running."

    def perform_pdb_postcheck(self):
        """Perform PDB clone postcheck validations"""
        connection_mode = self.params.get('connection_mode', 'external_auth')
        source_scan = self.params.get('source_scan')
        source_port = self.params.get('source_port')
        source_cdb = self.params.get('source_cdb')
        source_pdb = self.params.get('source_pdb')
        target_scan = self.params.get('target_scan')
        target_port = self.params.get('target_port')
        target_cdb = self.params.get('target_cdb')
        target_pdb = self.params.get('target_pdb')

        self.progress.emit("Starting PDB clone postcheck...")

        # Build connection strings
        source_cdb_dsn = f"{source_scan}:{source_port}/{source_cdb}"
        target_cdb_dsn = f"{target_scan}:{target_port}/{target_cdb}"

        # Connect to both CDBs
        if connection_mode == 'external_auth':
            self.progress.emit(f"Connecting to Source CDB: {source_cdb_dsn} (External Auth)")
            source_conn = oracledb.connect(dsn=source_cdb_dsn, externalauth=True)

            self.progress.emit(f"Connecting to Target CDB: {target_cdb_dsn} (External Auth)")
            target_conn = oracledb.connect(dsn=target_cdb_dsn, externalauth=True)
        else:
            source_user = self.params.get('source_username')
            source_pass = self.params.get('source_password')
            target_user = self.params.get('target_username')
            target_pass = self.params.get('target_password')

            self.progress.emit(f"Connecting to Source CDB: {source_cdb_dsn} (User: {source_user})")
            source_conn = oracledb.connect(user=source_user, password=source_pass, dsn=source_cdb_dsn)

            self.progress.emit(f"Connecting to Target CDB: {target_cdb_dsn} (User: {target_user})")
            target_conn = oracledb.connect(user=target_user, password=target_pass, dsn=target_cdb_dsn)

        validation_results = []
        source_data = {}
        target_data = {}

        source_cursor = source_conn.cursor()
        target_cursor = target_conn.cursor()

        # Gather instance and host information using gv$ views
        self.progress.emit("Gathering instance and host information...")

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

        # Gather PDB size information for postcheck
        self.progress.emit("Gathering PDB size information...")

        # Source PDB size
        source_cursor.execute("""
            SELECT ROUND(SUM(bytes)/1024/1024/1024, 2) as size_gb
            FROM v$datafile
            WHERE con_id = (SELECT con_id FROM v$pdbs WHERE UPPER(name) = UPPER(:pdb_name))
        """, pdb_name=source_pdb)
        source_size_result = source_cursor.fetchone()
        source_data['pdb_size_gb'] = source_size_result[0] if source_size_result and source_size_result[0] else 0

        # Target PDB size (should exist for postcheck)
        target_cursor.execute("""
            SELECT ROUND(SUM(bytes)/1024/1024/1024, 2) as size_gb
            FROM v$datafile
            WHERE con_id = (SELECT con_id FROM v$pdbs WHERE UPPER(name) = UPPER(:pdb_name))
        """, pdb_name=target_pdb)
        target_size_result = target_cursor.fetchone()
        target_data['pdb_size_gb'] = target_size_result[0] if target_size_result and target_size_result[0] else 0

        # Gather Oracle parameters for both PDBs using direct PDB connections
        self.progress.emit("Gathering Oracle parameters for source PDB...")

        # Connect directly to source PDB using hostname:port/pdb_name format
        source_pdb_dsn = f"{source_scan}:{source_port}/{source_pdb}"

        if connection_mode == 'external_auth':
            self.progress.emit(f"Connecting to Source PDB: {source_pdb_dsn} (External Auth)")
            source_pdb_conn = oracledb.connect(dsn=source_pdb_dsn, externalauth=True)
        else:
            source_user = self.params.get('source_username')
            source_pass = self.params.get('source_password')
            self.progress.emit(f"Connecting to Source PDB: {source_pdb_dsn} (User: {source_user})")
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

        # Connect directly to target PDB using hostname:port/pdb_name format
        target_pdb_dsn = f"{target_scan}:{target_port}/{target_pdb}"

        self.progress.emit("Gathering Oracle parameters for target PDB...")
        if connection_mode == 'external_auth':
            self.progress.emit(f"Connecting to Target PDB: {target_pdb_dsn} (External Auth)")
            target_pdb_conn = oracledb.connect(dsn=target_pdb_dsn, externalauth=True)
        else:
            target_user = self.params.get('target_username')
            target_pass = self.params.get('target_password')
            self.progress.emit(f"Connecting to Target PDB: {target_pdb_dsn} (User: {target_user})")
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
        self.progress.emit("Comparing parameters...")
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
        self.progress.emit("Checking DB services...")
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

        # Generate HTML report
        report_path = self.generate_postcheck_report_html(
            source_cdb, source_pdb, target_cdb, target_pdb,
            validation_results, source_data, target_data, param_differences
        )

        self.progress.emit(f"Postcheck report generated: {report_path}")

        all_passed = all(r['status'] == 'PASS' for r in validation_results)
        status = "All checks PASSED" if all_passed else "Some checks FAILED"

        return f"PDB clone postcheck completed.\nStatus: {status}\nReport: {report_path}"

    def generate_health_report_html(self, data):
        """Generate HTML health check report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        db_name = data.get('db_name', 'UNKNOWN').replace(':', '_').replace('/', '_')
        filename = f"{db_name}_db_health_report_{timestamp}.html"

        # Get CSS file path
        css_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'report_styles.css')

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Database Health Check Report</title>
    <link rel="stylesheet" href="report_styles.css">
</head>
<body>
    <h1>Oracle Database Health Check Report</h1>
    <div class="timestamp">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>

    <h2>Database Information</h2>
    <div class="info-box">
        <p><strong>Database Name:</strong> {data['db_name']}</p>
        <p><strong>Open Mode:</strong> {data['open_mode']}</p>
        <p><strong>Role:</strong> {data['role']}</p>
        <p><strong>Version:</strong> {data['version']}</p>
"""

        # Add instance information
        instances = data.get('instances', [])
        if instances:
            for inst in instances:
                html += f"        <p><strong>Instance {inst[0]}:</strong> {inst[1]} @ {inst[2]}</p>\n"

        # Add DB size
        db_size_gb = data.get('db_size_gb', 0)
        html += f"        <p><strong>Database Size:</strong> {db_size_gb} GB</p>\n"

        # Add MAX_PDB_STORAGE and percentage
        max_pdb_storage = data.get('max_pdb_storage', 'N/A')
        storage_pct = data.get('storage_pct', None)

        if max_pdb_storage != 'N/A':
            html += f"        <p><strong>MAX_PDB_STORAGE:</strong> {max_pdb_storage}"
            if storage_pct is not None:
                html += f" ({storage_pct}% used)"
            html += "</p>\n"

        html += """
    </div>

    <h2>Session Statistics</h2>
    <table>
        <tr><th>Status</th><th>Count</th></tr>
"""
        for status, count in data['sessions']:
            html += f"        <tr><td>{status}</td><td>{count}</td></tr>\n"

        html += """
    </table>

    <h2>Tablespace Usage</h2>
    <table>
        <tr><th>Tablespace</th><th>Used (GB)</th><th>Total (GB)</th><th>% Used</th></tr>
"""
        for ts_name, used, total, pct in data['tablespaces']:
            html += f"        <tr><td>{ts_name}</td><td>{used}</td><td>{total}</td><td>{pct}%</td></tr>\n"

        html += """
    </table>

    <h2>Pluggable Databases</h2>
    <table>
        <tr><th>PDB Name</th><th>Open Mode</th><th>Restricted</th><th>Open Time</th><th>Size (GB)</th></tr>
"""
        for pdb in data['pdbs']:
            open_time = pdb[3].strftime("%Y-%m-%d %H:%M:%S") if pdb[3] else 'N/A'
            size = round(pdb[4], 2) if pdb[4] else 0
            html += f"        <tr><td>{pdb[0]}</td><td>{pdb[1]}</td><td>{pdb[2]}</td><td>{open_time}</td><td>{size}</td></tr>\n"

        html += """
    </table>

    <h2>Top 10 Wait Events</h2>
    <table>
        <tr><th>Event</th><th>Total Waits</th><th>Time Waited (cs)</th><th>Avg Wait (cs)</th></tr>
"""
        for event, total_waits, time_waited, avg_wait in data['wait_events']:
            html += f"        <tr><td>{event}</td><td>{total_waits}</td><td>{time_waited}</td><td>{round(avg_wait, 2)}</td></tr>\n"

        html += """
    </table>
"""

        # Database Load (AAS)
        aas = data.get('aas', 0)
        if aas > 0:
            aas_status = 'CRITICAL' if aas > 10 else ('WARNING' if aas > 5 else 'OK')
            aas_class = 'fail' if aas > 10 else ('diff' if aas > 5 else 'pass')
            html += f"""
    <h2>Database Load (AAS - Last 5 Minutes)</h2>
    <div class="info-box">
        <p><strong>Average Active Sessions:</strong> <span class="{aas_class}">{aas}</span> ({aas_status})</p>
        <p><em>AAS > 10 = CRITICAL, AAS > 5 = WARNING, AAS ≤ 5 = OK</em></p>
    </div>
"""

        # Active Sessions by Service
        service_sessions = data.get('service_sessions', [])
        if service_sessions:
            html += """
    <h2>Active Sessions by Service</h2>
    <table>
        <tr><th>Service Name</th><th>Active</th><th>Inactive</th><th>Total</th></tr>
"""
            for service, active, inactive, total in service_sessions:
                html += f"        <tr><td>{service}</td><td>{active}</td><td>{inactive}</td><td>{total}</td></tr>\n"
            html += "    </table>\n"

        # Top SQL by CPU
        top_sql_cpu = data.get('top_sql_cpu', [])
        if top_sql_cpu:
            html += """
    <h2>Top 10 SQL by CPU Time</h2>
    <table>
        <tr><th>SQL ID</th><th>CPU (Seconds)</th><th>Executions</th><th>CPU per Exec (s)</th></tr>
"""
            for sql_id, cpu_secs, execs, cpu_per_exec in top_sql_cpu:
                html += f"        <tr><td>{sql_id}</td><td>{cpu_secs}</td><td>{execs}</td><td>{cpu_per_exec if cpu_per_exec else 'N/A'}</td></tr>\n"
            html += "    </table>\n"

        # Top SQL by Disk Reads
        top_sql_disk = data.get('top_sql_disk', [])
        if top_sql_disk:
            html += """
    <h2>Top 10 SQL by Disk Reads</h2>
    <table>
        <tr><th>SQL ID</th><th>Disk Reads</th><th>Executions</th><th>Reads per Exec</th></tr>
"""
            for sql_id, disk_reads, execs, reads_per_exec in top_sql_disk:
                html += f"        <tr><td>{sql_id}</td><td>{disk_reads}</td><td>{execs}</td><td>{reads_per_exec if reads_per_exec else 'N/A'}</td></tr>\n"
            html += "    </table>\n"

        # Invalid Objects
        invalid_objects = data.get('invalid_objects', [])
        if invalid_objects:
            html += """
    <h2>Invalid Objects</h2>
    <table>
        <tr><th>Owner</th><th>Object Type</th><th>Count</th></tr>
"""
            for owner, obj_type, count in invalid_objects:
                html += f"        <tr class='diff'><td>{owner}</td><td>{obj_type}</td><td>{count}</td></tr>\n"
            html += "    </table>\n"
        else:
            html += """
    <h2>Invalid Objects</h2>
    <div class="info-box">
        <p class="pass">✓ No invalid objects found</p>
    </div>
"""

        # Alert Log Errors
        alert_log_errors = data.get('alert_log_errors', [])
        if alert_log_errors:
            html += """
    <h2>Alert Log Errors (Last Hour)</h2>
    <table>
        <tr><th>Error Time</th><th>Message</th></tr>
"""
            for error_time, message in alert_log_errors:
                html += f"        <tr class='fail'><td>{error_time}</td><td>{message[:200]}</td></tr>\n"
            html += "    </table>\n"
        else:
            html += """
    <h2>Alert Log Errors (Last Hour)</h2>
    <div class="info-box">
        <p class="pass">✓ No ORA- errors in alert log (last hour)</p>
    </div>
"""

        # Long Running Queries
        long_queries = data.get('long_queries', [])
        if long_queries:
            html += """
    <h2>Long Running Queries (> 5 Minutes)</h2>
    <table>
        <tr><th>Instance</th><th>SID</th><th>Serial#</th><th>Username</th><th>SQL ID</th><th>Elapsed (min)</th><th>Status</th></tr>
"""
            for inst_id, sid, serial, username, sql_id, elapsed, status in long_queries:
                html += f"        <tr class='diff'><td>{inst_id}</td><td>{sid}</td><td>{serial}</td><td>{username}</td><td>{sql_id}</td><td>{elapsed}</td><td>{status}</td></tr>\n"
            html += "    </table>\n"
        else:
            html += """
    <h2>Long Running Queries (> 5 Minutes)</h2>
    <div class="info-box">
        <p class="pass">✓ No long-running queries detected</p>
    </div>
"""

        # Temp Tablespace Usage
        temp_usage = data.get('temp_usage', [])
        if temp_usage:
            html += """
    <h2>Temporary Tablespace Usage</h2>
    <table>
        <tr><th>Tablespace</th><th>Used (GB)</th><th>Free (GB)</th><th>% Used</th></tr>
"""
            for ts_name, used_gb, free_gb, pct_used in temp_usage:
                row_class = 'fail' if pct_used > 90 else ('diff' if pct_used > 75 else '')
                html += f"        <tr class='{row_class}'><td>{ts_name}</td><td>{used_gb}</td><td>{free_gb}</td><td>{pct_used}%</td></tr>\n"
            html += "    </table>\n"

        # RAC Instance Load Distribution
        instance_load = data.get('instance_load', [])
        if instance_load:
            html += """
    <h2>RAC Instance Load Distribution</h2>
    <table>
        <tr><th>Instance ID</th><th>Instance Name</th><th>DB Time (Seconds)</th></tr>
"""
            for inst_id, inst_name, db_time in instance_load:
                html += f"        <tr><td>{inst_id}</td><td>{inst_name}</td><td>{db_time}</td></tr>\n"
            html += "    </table>\n"

        # RAC Global Cache Waits
        rac_gc_waits = data.get('rac_gc_waits', [])
        if rac_gc_waits:
            html += """
    <h2>RAC: Global Cache Waits (Last Hour)</h2>
    <table>
        <tr><th>Event</th><th>Samples</th><th>% of Total</th></tr>
"""
            for event, samples, pct in rac_gc_waits:
                row_class = 'fail' if samples > 100 else ''
                html += f"        <tr class='{row_class}'><td>{event}</td><td>{samples}</td><td>{pct}%</td></tr>\n"
            html += "    </table>\n"

        # RAC GC Waits by Instance
        rac_gc_waits_inst = data.get('rac_gc_waits_by_instance', [])
        if rac_gc_waits_inst:
            html += """
    <h2>RAC: GC Waits by Instance (Last Hour)</h2>
    <table>
        <tr><th>Instance ID</th><th>Event</th><th>Wait Count</th></tr>
"""
            for inst_id, event, wait_count in rac_gc_waits_inst:
                row_class = 'fail' if wait_count > 500 else ('diff' if wait_count > 200 else '')
                html += f"        <tr class='{row_class}'><td>{inst_id}</td><td>{event}</td><td>{wait_count}</td></tr>\n"
            html += "    </table>\n"

        # RAC Interconnect Activity
        rac_interconnect = data.get('rac_interconnect', [])
        if rac_interconnect:
            html += """
    <h2>RAC: Interconnect Activity</h2>
    <table>
        <tr><th>Instance ID</th><th>Metric</th><th>MB</th></tr>
"""
            for inst_id, name, mb in rac_interconnect:
                row_class = 'fail' if mb > 500 else ''
                html += f"        <tr class='{row_class}'><td>{inst_id}</td><td>{name}</td><td>{mb}</td></tr>\n"
            html += "    </table>\n"

        # RAC GES Blocking Sessions
        rac_ges_blocking = data.get('rac_ges_blocking', [])
        if rac_ges_blocking:
            html += """
    <h2>RAC: GES Blocking Sessions (Last Hour)</h2>
    <table>
        <tr><th>Blocking Session</th><th>Blocking Instance</th><th>Blocks</th><th>First Seen</th><th>Last Seen</th></tr>
"""
            for blocking_sess, blocking_inst, blocks, first_seen, last_seen in rac_ges_blocking:
                row_class = 'fail' if blocks > 20 else ''
                html += f"        <tr class='{row_class}'><td>{blocking_sess}</td><td>{blocking_inst}</td><td>{blocks}</td><td>{first_seen}</td><td>{last_seen}</td></tr>\n"
            html += "    </table>\n"
        elif len(data.get('instances', [])) > 1:
            html += """
    <h2>RAC: GES Blocking Sessions (Last Hour)</h2>
    <div class="info-box">
        <p class="pass">✓ No blocking sessions detected</p>
    </div>
"""

        # RAC CPU Utilization per Instance
        rac_cpu_util = data.get('rac_cpu_util', [])
        if rac_cpu_util:
            html += """
    <h2>RAC: CPU Utilization per Instance</h2>
    <table>
        <tr><th>Instance ID</th><th>CPU Busy (secs)</th><th>Total CPU (secs)</th><th>CPU Util %</th></tr>
"""
            for inst_id, cpu_busy, total_cpu, cpu_pct in rac_cpu_util:
                row_class = 'fail' if cpu_pct > 90 else ('diff' if cpu_pct > 75 else '')
                html += f"        <tr class='{row_class}'><td>{inst_id}</td><td>{cpu_busy}</td><td>{total_cpu}</td><td>{cpu_pct}%</td></tr>\n"
            html += "    </table>\n"

        # RAC Global Enqueue Contention
        rac_ges_contention = data.get('rac_ges_contention', [])
        if rac_ges_contention:
            html += """
    <h2>RAC: Global Enqueue Contention (Last Hour)</h2>
    <table>
        <tr><th>Event</th><th>Samples</th></tr>
"""
            for event, samples in rac_ges_contention:
                row_class = 'fail' if samples > 50 else ''
                html += f"        <tr class='{row_class}'><td>{event}</td><td>{samples}</td></tr>\n"
            html += "    </table>\n"

        html += """
    <div class="footer">
        <p>Generated by Oracle PDB Management Toolkit</p>
    </div>
</body>
</html>
"""

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)

        report_path = os.path.abspath(filename)

        # Auto-open the HTML report in default browser
        try:
            webbrowser.open('file://' + report_path)
        except Exception:
            # If auto-open fails, just continue (report is still saved)
            pass

        return report_path

    def generate_precheck_report_html(self, source_cdb, source_pdb, target_cdb, target_pdb,
                                     validation_results, source_data, target_data):
        """Generate PDB validation HTML report with 3 sections"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{source_cdb}_{source_pdb}_{target_cdb}_{target_pdb}_pdb_validation_report_{timestamp}.html"

        # Calculate overall status
        overall_pass = all(r['status'] == 'PASS' for r in validation_results if r['status'] != 'SKIPPED')
        overall_status = 'PASS' if overall_pass else 'FAIL'
        overall_class = 'pass' if overall_pass else 'fail'

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDB Clone Validation Report</title>
    <link rel="stylesheet" href="report_styles.css">
</head>
<body>
    <h1>PDB Clone Validation Report (Precheck) - <span class="{overall_class}">{overall_status}</span></h1>
    <div class="timestamp">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>

    <h2>Section 1: Connection Metadata</h2>
    <table>
        <tr><th>Component</th><th>Source</th><th>Target</th></tr>
        <tr><td>CDB</td><td>{source_cdb}</td><td>{target_cdb}</td></tr>
        <tr><td>PDB</td><td>{source_pdb}</td><td>{target_pdb}</td></tr>
"""

        # Add instance information
        source_instances = source_data.get('instances', [])
        target_instances = target_data.get('instances', [])

        if source_instances or target_instances:
            html += "        <tr><td colspan='3' style='background-color: #f0f0f0; font-weight: bold;'>Instance Information</td></tr>\n"

        max_instances = max(len(source_instances), len(target_instances))
        for i in range(max_instances):
            if i < len(source_instances):
                src_inst = source_instances[i]
                source_info = f"Instance {src_inst[0]}: {src_inst[1]} @ {src_inst[2]}"
            else:
                source_info = "N/A"

            if i < len(target_instances):
                tgt_inst = target_instances[i]
                target_info = f"Instance {tgt_inst[0]}: {tgt_inst[1]} @ {tgt_inst[2]}"
            else:
                target_info = "N/A"

            html += f"        <tr><td>Instance {i+1}</td><td>{source_info}</td><td>{target_info}</td></tr>\n"

        # Add PDB size information
        source_pdb_size = source_data.get('pdb_size_gb', 0)
        target_pdb_size = target_data.get('pdb_size_gb', 0)

        html += "        <tr><td colspan='3' style='background-color: #f0f0f0; font-weight: bold;'>PDB Size Information</td></tr>\n"
        html += f"        <tr><td>PDB Total Size (GB)</td><td>{source_pdb_size} GB</td><td>{target_pdb_size if target_pdb_size > 0 else 'N/A (PDB not created yet)'}</td></tr>\n"

        html += """
    </table>

    <h2>Section 2: Verification Checks</h2>
    <table>
        <tr><th>Check</th><th>Status</th><th>Source Value</th><th>Target Value</th></tr>
"""

        for result in validation_results:
            status_class = 'pass' if result['status'] == 'PASS' else 'fail'
            html += f"""        <tr>
            <td>{result['check']}</td>
            <td class="{status_class}">{result['status']}</td>
            <td>{result['source_value']}</td>
            <td>{result['target_value']}</td>
        </tr>\n"""

            # Add violation details if present
            if 'violations' in result and result['violations']:
                html += """        <tr><td colspan="4"><div class="violations">
                <strong>Plug-In Violations Detected:</strong><br>
"""
                for v in result['violations']:
                    html += f"                &bull; {v[0]} - {v[3]}<br>\n"
                html += "            </div></td></tr>\n"

        html += """
    </table>

    <h2>Section 3: ORACLE CDB Parameters Comparison (Non-Default)</h2>
    <table>
        <tr><th>Parameter Name</th><th>Source Value</th><th>Target Value</th><th>Status</th></tr>
"""

        # Build CDB parameter comparison
        source_cdb_params = {p[0]: p[1] for p in source_data.get('cdb_parameters', [])}
        target_cdb_params = {p[0]: p[1] for p in target_data.get('cdb_parameters', [])}

        all_cdb_params = sorted(set(source_cdb_params.keys()) | set(target_cdb_params.keys()))

        for param in all_cdb_params:
            source_val = source_cdb_params.get(param, 'N/A')
            target_val = target_cdb_params.get(param, 'N/A')

            if source_val == target_val:
                row_class = 'match'
                status = 'SAME'
            else:
                row_class = 'diff'
                status = 'DIFF'

            html += f"""        <tr class="{row_class}">
            <td>{param}</td>
            <td>{source_val}</td>
            <td>{target_val}</td>
            <td>{status}</td>
        </tr>\n"""

        html += """
    </table>

    <h2>Section 4: ORACLE PDB Parameters Comparison (Non-Default)</h2>
"""

        # Build PDB parameter comparison
        source_pdb_params = {p[0]: p[1] for p in source_data.get('pdb_parameters', [])}
        target_pdb_params = {p[0]: p[1] for p in target_data.get('pdb_parameters', [])}

        all_pdb_params = sorted(set(source_pdb_params.keys()) | set(target_pdb_params.keys()))

        # Check if target PDB exists (has parameters)
        target_pdb_exists = len(target_pdb_params) > 0
        target_pdb_mode = target_data.get('pdb_mode', 'Unknown')

        if not target_pdb_exists:
            html += """
    <p style="background-color: #fff3cd; padding: 10px; border-left: 4px solid #ffc107; margin: 10px 0;">
        <strong>Note:</strong> Target PDB does not exist yet.
        The table below shows source PDB parameters that will be inherited after cloning.
        Run postcheck after cloning to compare actual parameter values.
    </p>
"""
        else:
            html += f"""
    <p style="background-color: #d1ecf1; padding: 10px; border-left: 4px solid #0c5460; margin: 10px 0;">
        <strong>Note:</strong> Target PDB exists ({target_pdb_mode}).
        Comparing current parameter values between source and target PDBs.
    </p>
"""

        html += """
    <table>
        <tr><th>Parameter Name</th><th>Source PDB Value</th><th>Target PDB Value</th><th>Status</th></tr>
"""

        if all_pdb_params:
            for param in all_pdb_params:
                source_val = source_pdb_params.get(param, 'Not Set')
                target_val = target_pdb_params.get(param, 'Not Set' if target_pdb_exists else 'PDB not created yet')

                if source_val == target_val and target_pdb_exists:
                    row_class = 'match'
                    status = 'SAME'
                elif not target_pdb_exists:
                    row_class = ''  # No color for pending parameters
                    status = 'Pending'
                else:
                    row_class = 'diff'
                    status = 'DIFF'

                html += f"""        <tr class="{row_class}">
            <td>{param}</td>
            <td>{source_val}</td>
            <td>{target_val}</td>
            <td>{status}</td>
        </tr>\n"""
        else:
            html += """        <tr>
            <td colspan="4" style="text-align: center; font-style: italic;">No non-default PDB parameters found on either source or target</td>
        </tr>\n"""

        html += """
    </table>

    <div class="footer">
        <p>Generated by Oracle PDB Management Toolkit</p>
    </div>
</body>
</html>
"""

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)

        report_path = os.path.abspath(filename)

        # Auto-open the HTML report in default browser
        try:
            webbrowser.open('file://' + report_path)
        except Exception:
            # If auto-open fails, just continue (report is still saved)
            pass

        return report_path

    def generate_postcheck_report_html(self, source_cdb, source_pdb, target_cdb, target_pdb,
                                      validation_results, source_data, target_data, param_diffs):
        """Generate PDB postcheck HTML report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{source_cdb}_{source_pdb}_{target_cdb}_{target_pdb}_pdb_postcheck_report_{timestamp}.html"

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDB Clone Postcheck Report</title>
    <link rel="stylesheet" href="report_styles.css">
</head>
<body>
    <h1>PDB Clone Postcheck Report</h1>
    <div class="timestamp">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>

    <h2>Section 1: Connection Metadata</h2>
    <table>
        <tr><th>Component</th><th>Source</th><th>Target</th></tr>
        <tr><td>CDB</td><td>{source_cdb}</td><td>{target_cdb}</td></tr>
        <tr><td>PDB</td><td>{source_pdb}</td><td>{target_pdb}</td></tr>
"""

        # Add instance information
        source_instances = source_data.get('instances', [])
        target_instances = target_data.get('instances', [])

        if source_instances or target_instances:
            html += "        <tr><td colspan='3' style='background-color: #f0f0f0; font-weight: bold;'>Instance Information</td></tr>\n"

        max_instances = max(len(source_instances), len(target_instances))
        for i in range(max_instances):
            if i < len(source_instances):
                src_inst = source_instances[i]
                source_info = f"Instance {src_inst[0]}: {src_inst[1]} @ {src_inst[2]}"
            else:
                source_info = "N/A"

            if i < len(target_instances):
                tgt_inst = target_instances[i]
                target_info = f"Instance {tgt_inst[0]}: {tgt_inst[1]} @ {tgt_inst[2]}"
            else:
                target_info = "N/A"

            html += f"        <tr><td>Instance {i+1}</td><td>{source_info}</td><td>{target_info}</td></tr>\n"

        # Add PDB size information
        source_pdb_size = source_data.get('pdb_size_gb', 0)
        target_pdb_size = target_data.get('pdb_size_gb', 0)

        html += "        <tr><td colspan='3' style='background-color: #f0f0f0; font-weight: bold;'>PDB Size Information</td></tr>\n"
        html += f"        <tr><td>PDB Total Size (GB)</td><td>{source_pdb_size} GB</td><td>{target_pdb_size} GB</td></tr>\n"

        html += """
    </table>

    <h2>Section 2: Postcheck Verification</h2>
    <table>
        <tr><th>Check</th><th>Status</th><th>Source Value</th><th>Target Value</th></tr>
"""

        for result in validation_results:
            status_class = 'pass' if result['status'] == 'PASS' else 'fail'
            html += f"""        <tr>
            <td>{result['check']}</td>
            <td class="{status_class}">{result['status']}</td>
            <td>{result['source_value']}</td>
            <td>{result['target_value']}</td>
        </tr>\n"""

        html += """
    </table>

    <h2>Section 3: Parameter Differences</h2>
"""

        if param_diffs:
            html += """    <table>
        <tr><th>Parameter Name</th><th>Source Value</th><th>Target Value</th></tr>
"""
            for param, source_val, target_val in param_diffs:
                html += f"""        <tr class="diff">
            <td>{param}</td>
            <td>{source_val}</td>
            <td>{target_val}</td>
        </tr>\n"""
            html += "    </table>\n"
        else:
            html += "    <div class='alert-success'>All parameters match!</div>\n"

        html += """
    <div class="footer">
        <p>Generated by Oracle PDB Management Toolkit</p>
    </div>
</body>
</html>
"""

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)

        report_path = os.path.abspath(filename)

        # Auto-open the HTML report in default browser
        try:
            webbrowser.open('file://' + report_path)
        except Exception:
            # If auto-open fails, just continue (report is still saved)
            pass

        return report_path


class OraclePDBToolkit(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.worker = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Oracle PDB Management Toolkit")
        self.setGeometry(100, 100, 900, 700)

        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Title
        title = QLabel("Oracle DBA Admin Toolbox")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)

        # Tab widget for main menu
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab 1: DB Health Check
        self.health_tab = QWidget()
        self.setup_health_tab()
        self.tabs.addTab(self.health_tab, "DB Health Check")

        # Tab 2: PDB Clone
        self.clone_tab = QWidget()
        self.setup_clone_tab()
        self.tabs.addTab(self.clone_tab, "PDB Clone")

        # Output area
        output_group = QGroupBox("Output / Progress")
        output_layout = QVBoxLayout()
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        output_layout.addWidget(self.output_text)
        output_group.setLayout(output_layout)
        main_layout.addWidget(output_group)

        self.log("Oracle PDB Toolkit initialized successfully")
        self.log("Note: Supports both external authentication and username/password")

    def setup_health_tab(self):
        """Setup DB Health Check tab"""
        layout = QVBoxLayout(self.health_tab)

        # Connection method selection
        method_group = QGroupBox("Connection Method")
        method_layout = QVBoxLayout()

        self.health_conn_method = QButtonGroup()

        self.health_external_auth_radio = QRadioButton("External Authentication (OS Auth / Wallet)")
        self.health_external_auth_radio.setChecked(True)
        self.health_conn_method.addButton(self.health_external_auth_radio, 1)
        method_layout.addWidget(self.health_external_auth_radio)

        self.health_user_pass_radio = QRadioButton("Username / Password")
        self.health_conn_method.addButton(self.health_user_pass_radio, 2)
        method_layout.addWidget(self.health_user_pass_radio)

        method_group.setLayout(method_layout)
        layout.addWidget(method_group)

        # Connection configuration
        input_group = QGroupBox("Connection Configuration")
        input_layout = QVBoxLayout()

        # External Authentication fields (TNS or Hostname/Port)
        self.health_ext_auth_widget = QWidget()
        ext_auth_layout = QVBoxLayout(self.health_ext_auth_widget)
        ext_auth_layout.setContentsMargins(0, 0, 0, 0)

        # Option 1: TNS Alias
        tns_row = QHBoxLayout()
        tns_row.addWidget(QLabel("TNS Alias:"))
        self.health_ext_tns = QLineEdit()
        self.health_ext_tns.setPlaceholderText("e.g., ORCL or orcl_high (leave empty to use hostname/port)")
        tns_row.addWidget(self.health_ext_tns)
        ext_auth_layout.addLayout(tns_row)

        # Separator
        or_label = QLabel("— OR —")
        or_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        or_label.setStyleSheet("color: #666; font-style: italic; margin: 5px 0;")
        ext_auth_layout.addWidget(or_label)

        # Option 2: Hostname/Port/Service
        ext_host_row = QHBoxLayout()
        ext_host_row.addWidget(QLabel("Hostname:"))
        self.health_ext_hostname = QLineEdit()
        self.health_ext_hostname.setPlaceholderText("e.g., dbserver.example.com")
        ext_host_row.addWidget(self.health_ext_hostname)
        ext_auth_layout.addLayout(ext_host_row)

        ext_port_row = QHBoxLayout()
        ext_port_row.addWidget(QLabel("Port:"))
        self.health_ext_port = QLineEdit()
        self.health_ext_port.setPlaceholderText("1521")
        self.health_ext_port.setText("1521")
        self.health_ext_port.setMaximumWidth(100)
        ext_port_row.addWidget(self.health_ext_port)
        ext_port_row.addStretch()
        ext_auth_layout.addLayout(ext_port_row)

        ext_service_row = QHBoxLayout()
        ext_service_row.addWidget(QLabel("Service Name:"))
        self.health_ext_service = QLineEdit()
        self.health_ext_service.setPlaceholderText("e.g., ORCL or orcl_high")
        ext_service_row.addWidget(self.health_ext_service)
        ext_auth_layout.addLayout(ext_service_row)

        input_layout.addWidget(self.health_ext_auth_widget)

        # Hostname/Port/Service (for username/password)
        self.health_host_widget = QWidget()
        host_layout = QVBoxLayout(self.health_host_widget)
        host_layout.setContentsMargins(0, 0, 0, 0)

        host_row = QHBoxLayout()
        host_row.addWidget(QLabel("Hostname:"))
        self.health_hostname = QLineEdit()
        self.health_hostname.setPlaceholderText("e.g., dbserver.example.com")
        host_row.addWidget(self.health_hostname)
        host_layout.addLayout(host_row)

        port_row = QHBoxLayout()
        port_row.addWidget(QLabel("Port:"))
        self.health_port = QLineEdit()
        self.health_port.setPlaceholderText("1521")
        self.health_port.setText("1521")
        self.health_port.setMaximumWidth(100)
        port_row.addWidget(self.health_port)
        port_row.addStretch()
        host_layout.addLayout(port_row)

        service_row = QHBoxLayout()
        service_row.addWidget(QLabel("Service Name:"))
        self.health_service = QLineEdit()
        self.health_service.setPlaceholderText("e.g., ORCL or orcl_high")
        service_row.addWidget(self.health_service)
        host_layout.addLayout(service_row)

        user_row = QHBoxLayout()
        user_row.addWidget(QLabel("Username:"))
        self.health_username = QLineEdit()
        self.health_username.setPlaceholderText("e.g., system or admin")
        user_row.addWidget(self.health_username)
        host_layout.addLayout(user_row)

        pass_row = QHBoxLayout()
        pass_row.addWidget(QLabel("Password:"))
        self.health_password = QLineEdit()
        self.health_password.setPlaceholderText("Password")
        self.health_password.setEchoMode(QLineEdit.EchoMode.Password)
        pass_row.addWidget(self.health_password)
        host_layout.addLayout(pass_row)

        self.health_host_widget.setVisible(False)
        input_layout.addWidget(self.health_host_widget)

        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # Connect radio button signals
        self.health_external_auth_radio.toggled.connect(self.toggle_health_connection_fields)
        self.health_user_pass_radio.toggled.connect(self.toggle_health_connection_fields)

        # Run button
        self.health_run_btn = QPushButton("Generate Health Report")
        self.health_run_btn.setStyleSheet("background-color: #0066cc; color: white; padding: 10px; font-weight: bold;")
        self.health_run_btn.clicked.connect(self.run_health_check)
        layout.addWidget(self.health_run_btn)

        layout.addStretch()

    def toggle_health_connection_fields(self):
        """Toggle between external auth and username/password fields"""
        if self.health_external_auth_radio.isChecked():
            self.health_ext_auth_widget.setVisible(True)
            self.health_host_widget.setVisible(False)
        else:
            self.health_ext_auth_widget.setVisible(False)
            self.health_host_widget.setVisible(True)

    def toggle_clone_connection_fields(self):
        """Toggle between external auth and username/password fields for PDB Clone"""
        if self.clone_external_auth_radio.isChecked():
            self.source_credentials_widget.setVisible(False)
            self.target_credentials_widget.setVisible(False)
        else:
            self.source_credentials_widget.setVisible(True)
            self.target_credentials_widget.setVisible(True)

    def setup_clone_tab(self):
        """Setup PDB Clone tab"""
        layout = QVBoxLayout(self.clone_tab)

        # Connection method selection
        method_group = QGroupBox("Connection Method")
        method_layout = QVBoxLayout()

        self.clone_conn_method = QButtonGroup()

        self.clone_external_auth_radio = QRadioButton("External Authentication (OS Auth / Wallet)")
        self.clone_external_auth_radio.setChecked(True)
        self.clone_conn_method.addButton(self.clone_external_auth_radio, 1)
        method_layout.addWidget(self.clone_external_auth_radio)

        self.clone_user_pass_radio = QRadioButton("Username / Password")
        self.clone_conn_method.addButton(self.clone_user_pass_radio, 2)
        method_layout.addWidget(self.clone_user_pass_radio)

        method_group.setLayout(method_layout)
        layout.addWidget(method_group)

        # Input fields
        input_group = QGroupBox("PDB Clone Configuration")
        input_layout = QVBoxLayout()

        # Source configuration
        source_label = QLabel("Source Configuration")
        source_label.setStyleSheet("font-weight: bold; color: #0066cc;")
        input_layout.addWidget(source_label)

        source_host_layout = QHBoxLayout()
        source_host_layout.addWidget(QLabel("Source SCAN Host:"))
        self.source_scan = QLineEdit()
        self.source_scan.setPlaceholderText("e.g., prod-scan.example.com")
        source_host_layout.addWidget(self.source_scan)
        input_layout.addLayout(source_host_layout)

        source_port_layout = QHBoxLayout()
        source_port_layout.addWidget(QLabel("Port:"))
        self.source_port = QLineEdit()
        self.source_port.setPlaceholderText("1521")
        self.source_port.setText("1521")
        self.source_port.setMaximumWidth(100)
        source_port_layout.addWidget(self.source_port)
        source_port_layout.addStretch()
        input_layout.addLayout(source_port_layout)

        source_cdb_layout = QHBoxLayout()
        source_cdb_layout.addWidget(QLabel("Source CDB:"))
        self.source_cdb = QLineEdit()
        self.source_cdb.setPlaceholderText("Source CDB service name")
        source_cdb_layout.addWidget(self.source_cdb)
        input_layout.addLayout(source_cdb_layout)

        source_pdb_layout = QHBoxLayout()
        source_pdb_layout.addWidget(QLabel("Source PDB:"))
        self.source_pdb = QLineEdit()
        self.source_pdb.setPlaceholderText("Source PDB name/service (e.g., PRODPDB)")
        source_pdb_layout.addWidget(self.source_pdb)
        input_layout.addLayout(source_pdb_layout)

        # Credentials for username/password mode (source)
        self.source_credentials_widget = QWidget()
        source_cred_layout = QVBoxLayout(self.source_credentials_widget)
        source_cred_layout.setContentsMargins(0, 0, 0, 0)

        source_user_layout = QHBoxLayout()
        source_user_layout.addWidget(QLabel("Username:"))
        self.source_username = QLineEdit()
        self.source_username.setPlaceholderText("Source database username")
        source_user_layout.addWidget(self.source_username)
        source_cred_layout.addLayout(source_user_layout)

        source_pass_layout = QHBoxLayout()
        source_pass_layout.addWidget(QLabel("Password:"))
        self.source_password = QLineEdit()
        self.source_password.setPlaceholderText("Password")
        self.source_password.setEchoMode(QLineEdit.EchoMode.Password)
        source_pass_layout.addWidget(self.source_password)
        source_cred_layout.addLayout(source_pass_layout)

        self.source_credentials_widget.setVisible(False)
        input_layout.addWidget(self.source_credentials_widget)

        # Target configuration
        target_label = QLabel("Target Configuration")
        target_label.setStyleSheet("font-weight: bold; color: #0066cc; margin-top: 15px;")
        input_layout.addWidget(target_label)

        target_host_layout = QHBoxLayout()
        target_host_layout.addWidget(QLabel("Target SCAN Host:"))
        self.target_scan = QLineEdit()
        self.target_scan.setPlaceholderText("e.g., dev-scan.example.com")
        target_host_layout.addWidget(self.target_scan)
        input_layout.addLayout(target_host_layout)

        target_port_layout = QHBoxLayout()
        target_port_layout.addWidget(QLabel("Port:"))
        self.target_port = QLineEdit()
        self.target_port.setPlaceholderText("1521")
        self.target_port.setText("1521")
        self.target_port.setMaximumWidth(100)
        target_port_layout.addWidget(self.target_port)
        target_port_layout.addStretch()
        input_layout.addLayout(target_port_layout)

        target_cdb_layout = QHBoxLayout()
        target_cdb_layout.addWidget(QLabel("Target CDB:"))
        self.target_cdb = QLineEdit()
        self.target_cdb.setPlaceholderText("Target CDB service name")
        target_cdb_layout.addWidget(self.target_cdb)
        input_layout.addLayout(target_cdb_layout)

        target_pdb_layout = QHBoxLayout()
        target_pdb_layout.addWidget(QLabel("Target PDB:"))
        self.target_pdb = QLineEdit()
        self.target_pdb.setPlaceholderText("New PDB name/service (e.g., DEVPDB)")
        target_pdb_layout.addWidget(self.target_pdb)
        input_layout.addLayout(target_pdb_layout)

        # Credentials for username/password mode (target)
        self.target_credentials_widget = QWidget()
        target_cred_layout = QVBoxLayout(self.target_credentials_widget)
        target_cred_layout.setContentsMargins(0, 0, 0, 0)

        target_user_layout = QHBoxLayout()
        target_user_layout.addWidget(QLabel("Username:"))
        self.target_username = QLineEdit()
        self.target_username.setPlaceholderText("Target database username")
        target_user_layout.addWidget(self.target_username)
        target_cred_layout.addLayout(target_user_layout)

        target_pass_layout = QHBoxLayout()
        target_pass_layout.addWidget(QLabel("Password:"))
        self.target_password = QLineEdit()
        self.target_password.setPlaceholderText("Password")
        self.target_password.setEchoMode(QLineEdit.EchoMode.Password)
        target_pass_layout.addWidget(self.target_password)
        target_cred_layout.addLayout(target_pass_layout)

        self.target_credentials_widget.setVisible(False)
        input_layout.addWidget(self.target_credentials_widget)

        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # Connect radio button signals
        self.clone_external_auth_radio.toggled.connect(self.toggle_clone_connection_fields)
        self.clone_user_pass_radio.toggled.connect(self.toggle_clone_connection_fields)

        # Action buttons
        button_layout = QHBoxLayout()

        self.precheck_btn = QPushButton("Run Precheck")
        self.precheck_btn.setStyleSheet("background-color: #28a745; color: white; padding: 10px; font-weight: bold;")
        self.precheck_btn.clicked.connect(self.run_precheck)
        button_layout.addWidget(self.precheck_btn)

        self.clone_btn = QPushButton("Execute PDB Clone")
        self.clone_btn.setStyleSheet("background-color: #ffc107; color: black; padding: 10px; font-weight: bold;")
        self.clone_btn.clicked.connect(self.run_clone)
        button_layout.addWidget(self.clone_btn)

        self.postcheck_btn = QPushButton("Run Postcheck")
        self.postcheck_btn.setStyleSheet("background-color: #17a2b8; color: white; padding: 10px; font-weight: bold;")
        self.postcheck_btn.clicked.connect(self.run_postcheck)
        button_layout.addWidget(self.postcheck_btn)

        layout.addLayout(button_layout)
        layout.addStretch()

    def log(self, message):
        """Add message to output area"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.output_text.append(f"[{timestamp}] {message}")
        QApplication.processEvents()

    def disable_buttons(self):
        """Disable all action buttons during operations"""
        self.health_run_btn.setEnabled(False)
        self.precheck_btn.setEnabled(False)
        self.clone_btn.setEnabled(False)
        self.postcheck_btn.setEnabled(False)

    def enable_buttons(self):
        """Enable all action buttons after operations"""
        self.health_run_btn.setEnabled(True)
        self.precheck_btn.setEnabled(True)
        self.clone_btn.setEnabled(True)
        self.postcheck_btn.setEnabled(True)

    def run_health_check(self):
        """Run database health check"""
        params = {}

        if self.health_external_auth_radio.isChecked():
            # External authentication mode
            tns_alias = self.health_ext_tns.text().strip()
            hostname = self.health_ext_hostname.text().strip()
            port = self.health_ext_port.text().strip()
            service = self.health_ext_service.text().strip()

            params['connection_mode'] = 'external_auth'

            # Check if TNS alias is provided
            if tns_alias:
                params['db_name'] = tns_alias
                self.log(f"Starting health check for database: {tns_alias} (External Auth - TNS)")
            elif hostname and port and service:
                # Use hostname/port/service
                params['hostname'] = hostname
                params['port'] = port
                params['service'] = service
                params['db_name'] = f"{hostname}:{port}/{service}"
                self.log(f"Starting health check for {service} at {hostname}:{port} (External Auth - Direct)")
            else:
                QMessageBox.warning(self, "Input Required",
                                  "Please provide either:\n"
                                  "- TNS Alias, OR\n"
                                  "- Hostname + Port + Service Name")
                return

        else:
            # Username/password mode
            hostname = self.health_hostname.text().strip()
            port = self.health_port.text().strip()
            service = self.health_service.text().strip()
            username = self.health_username.text().strip()
            password = self.health_password.text().strip()

            if not all([hostname, port, service, username, password]):
                QMessageBox.warning(self, "Input Required",
                                  "Please provide all connection details:\n"
                                  "- Hostname\n- Port\n- Service Name\n- Username\n- Password")
                return

            params['connection_mode'] = 'user_pass'
            params['hostname'] = hostname
            params['port'] = port
            params['service'] = service
            params['username'] = username
            params['password'] = password
            self.log(f"Starting health check for {service} at {hostname}:{port} (User: {username})")

        self.disable_buttons()

        self.worker = DatabaseWorker("health_check", params)
        self.worker.progress.connect(self.log)
        self.worker.finished.connect(self.on_operation_finished)
        self.worker.start()

    def run_precheck(self):
        """Run PDB clone precheck"""
        source_scan = self.source_scan.text().strip()
        source_port = self.source_port.text().strip()
        source_cdb = self.source_cdb.text().strip()
        source_pdb = self.source_pdb.text().strip()
        target_scan = self.target_scan.text().strip()
        target_port = self.target_port.text().strip()
        target_cdb = self.target_cdb.text().strip()
        target_pdb = self.target_pdb.text().strip()

        # Validate required fields
        if not all([source_scan, source_port, source_cdb, source_pdb, target_scan, target_port, target_cdb, target_pdb]):
            QMessageBox.warning(self, "Input Required",
                              "Please provide all required fields:\n"
                              "- Source and Target SCAN hosts\n"
                              "- Ports\n"
                              "- CDB and PDB names")
            return

        params = {
            'connection_mode': 'external_auth' if self.clone_external_auth_radio.isChecked() else 'user_pass',
            'source_scan': source_scan,
            'source_port': source_port,
            'source_cdb': source_cdb,
            'source_pdb': source_pdb,
            'target_scan': target_scan,
            'target_port': target_port,
            'target_cdb': target_cdb,
            'target_pdb': target_pdb
        }

        # Add credentials if username/password mode
        if self.clone_user_pass_radio.isChecked():
            source_user = self.source_username.text().strip()
            source_pass = self.source_password.text().strip()
            target_user = self.target_username.text().strip()
            target_pass = self.target_password.text().strip()

            if not all([source_user, source_pass, target_user, target_pass]):
                QMessageBox.warning(self, "Credentials Required",
                                  "Please provide username and password for both source and target databases")
                return

            params['source_username'] = source_user
            params['source_password'] = source_pass
            params['target_username'] = target_user
            params['target_password'] = target_pass

        self.log("Starting PDB clone precheck...")
        self.disable_buttons()

        self.worker = DatabaseWorker("pdb_precheck", params)
        self.worker.progress.connect(self.log)
        self.worker.finished.connect(self.on_operation_finished)
        self.worker.start()

    def run_clone(self):
        """Execute PDB clone"""
        source_scan = self.source_scan.text().strip()
        source_port = self.source_port.text().strip()
        source_cdb = self.source_cdb.text().strip()
        source_pdb = self.source_pdb.text().strip()
        target_scan = self.target_scan.text().strip()
        target_port = self.target_port.text().strip()
        target_cdb = self.target_cdb.text().strip()
        target_pdb = self.target_pdb.text().strip()

        if not all([source_scan, source_port, source_cdb, source_pdb, target_scan, target_port, target_cdb, target_pdb]):
            QMessageBox.warning(self, "Input Required",
                              "Please provide all required fields")
            return

        # Confirmation dialog
        reply = QMessageBox.question(self, 'Confirm Clone Operation',
                                    f"Are you sure you want to clone:\n\n"
                                    f"Source: {source_pdb}@{source_scan}:{source_port}/{source_cdb}\n"
                                    f"Target: {target_pdb}@{target_scan}:{target_port}/{target_cdb}\n\n"
                                    f"This operation will create a new PDB.",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.No:
            return

        params = {
            'connection_mode': 'external_auth' if self.clone_external_auth_radio.isChecked() else 'user_pass',
            'source_scan': source_scan,
            'source_port': source_port,
            'source_cdb': source_cdb,
            'source_pdb': source_pdb,
            'target_scan': target_scan,
            'target_port': target_port,
            'target_cdb': target_cdb,
            'target_pdb': target_pdb
        }

        # Add credentials if username/password mode
        if self.clone_user_pass_radio.isChecked():
            source_user = self.source_username.text().strip()
            source_pass = self.source_password.text().strip()
            target_user = self.target_username.text().strip()
            target_pass = self.target_password.text().strip()

            if not all([source_user, source_pass, target_user, target_pass]):
                QMessageBox.warning(self, "Credentials Required",
                                  "Please provide username and password for both source and target databases")
                return

            params['source_username'] = source_user
            params['source_password'] = source_pass
            params['target_username'] = target_user
            params['target_password'] = target_pass

        self.log("Starting PDB clone operation...")
        self.disable_buttons()

        self.worker = DatabaseWorker("pdb_clone", params)
        self.worker.progress.connect(self.log)
        self.worker.finished.connect(self.on_operation_finished)
        self.worker.start()

    def run_postcheck(self):
        """Run PDB clone postcheck"""
        source_scan = self.source_scan.text().strip()
        source_port = self.source_port.text().strip()
        source_cdb = self.source_cdb.text().strip()
        source_pdb = self.source_pdb.text().strip()
        target_scan = self.target_scan.text().strip()
        target_port = self.target_port.text().strip()
        target_cdb = self.target_cdb.text().strip()
        target_pdb = self.target_pdb.text().strip()

        if not all([source_scan, source_port, source_cdb, source_pdb, target_scan, target_port, target_cdb, target_pdb]):
            QMessageBox.warning(self, "Input Required",
                              "Please provide all required fields")
            return

        params = {
            'connection_mode': 'external_auth' if self.clone_external_auth_radio.isChecked() else 'user_pass',
            'source_scan': source_scan,
            'source_port': source_port,
            'source_cdb': source_cdb,
            'source_pdb': source_pdb,
            'target_scan': target_scan,
            'target_port': target_port,
            'target_cdb': target_cdb,
            'target_pdb': target_pdb
        }

        # Add credentials if username/password mode
        if self.clone_user_pass_radio.isChecked():
            source_user = self.source_username.text().strip()
            source_pass = self.source_password.text().strip()
            target_user = self.target_username.text().strip()
            target_pass = self.target_password.text().strip()

            if not all([source_user, source_pass, target_user, target_pass]):
                QMessageBox.warning(self, "Credentials Required",
                                  "Please provide username and password for both source and target databases")
                return

            params['source_username'] = source_user
            params['source_password'] = source_pass
            params['target_username'] = target_user
            params['target_password'] = target_pass

        self.log("Starting PDB clone postcheck...")
        self.disable_buttons()

        self.worker = DatabaseWorker("pdb_postcheck", params)
        self.worker.progress.connect(self.log)
        self.worker.finished.connect(self.on_operation_finished)
        self.worker.start()

    def on_operation_finished(self, success, message):
        """Handle operation completion"""
        self.enable_buttons()

        if success:
            self.log(f"SUCCESS: {message}")
            QMessageBox.information(self, "Operation Complete", message)
        else:
            self.log(f"ERROR: {message}")
            QMessageBox.critical(self, "Operation Failed", message)


def signal_handler(sig, frame):
    """Handle Ctrl+C (SIGINT) gracefully"""
    print("\n[INFO] Shutdown signal received. Closing application gracefully...")
    QApplication.quit()


def main():
    # Register signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    app = QApplication(sys.argv)

    # Create a QTimer that fires periodically to allow Python to process signals
    # This is necessary because Qt's event loop blocks Python's signal handling
    timer = QTimer()
    timer.start(500)  # Fire every 500ms
    timer.timeout.connect(lambda: None)  # No-op, just allows Python signal processing

    window = OraclePDBToolkit()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
