"""
Oracle PDB Toolkit - Report Generator Module
Version: 2.0.0

This module provides HTML report generation functions for:
- Database health check reports
- PDB clone precheck validation reports
- PDB clone postcheck validation reports

All reports use the report_styles.css file and auto-open in the default browser.
Reports are saved to the outputs/ directory.
"""

import os
import webbrowser
from datetime import datetime


def generate_health_report(health_data, output_dir='outputs'):
    """
    Generate HTML health check report from health data dictionary.

    Args:
        health_data (dict): Dictionary containing all health check results
        output_dir (str): Directory to save report (default: 'outputs')

    Returns:
        str: Absolute path to generated HTML report

    The health_data dictionary should contain:
        - db_name, open_mode, role, version
        - instances (list of tuples)
        - db_size_gb
        - max_pdb_storage, storage_pct
        - sessions (list of status/count tuples)
        - tablespaces (list of tablespace data)
        - pdbs (list of PDB information)
        - wait_events (top 10 wait events)
        - aas (Average Active Sessions)
        - service_sessions, top_sql_cpu, top_sql_disk
        - invalid_objects, alert_log_errors, long_queries
        - temp_usage
        - RAC metrics: instance_load, rac_gc_waits, rac_gc_waits_by_instance,
          rac_interconnect, rac_ges_blocking, rac_cpu_util, rac_ges_contention
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    db_name = health_data.get('db_name', 'UNKNOWN').replace(':', '_').replace('/', '_')
    filename = os.path.join(output_dir, f"{db_name}_db_health_report_{timestamp}.html")

    # Get CSS file path
    css_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'report_styles.css')

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Database Health Check Report</title>
    <link rel="stylesheet" href="../report_styles.css">
</head>
<body>
    <h1>Oracle Database Health Check Report</h1>
    <div class="timestamp">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>

    <h2>Database Information</h2>
    <div class="info-box">
        <p><strong>Database Name:</strong> {health_data['db_name']}</p>
        <p><strong>Open Mode:</strong> {health_data['open_mode']}</p>
        <p><strong>Role:</strong> {health_data['role']}</p>
        <p><strong>Version:</strong> {health_data['version']}</p>
"""

    # Add instance information
    instances = health_data.get('instances', [])
    if instances:
        for inst in instances:
            html += f"        <p><strong>Instance {inst[0]}:</strong> {inst[1]} @ {inst[2]}</p>\n"

    # Add DB size
    db_size_gb = health_data.get('db_size_gb', 0)
    html += f"        <p><strong>Database Size:</strong> {db_size_gb} GB</p>\n"

    # Add MAX_PDB_STORAGE and percentage
    max_pdb_storage = health_data.get('max_pdb_storage', 'N/A')
    storage_pct = health_data.get('storage_pct', None)

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
    for status, count in health_data['sessions']:
        html += f"        <tr><td>{status}</td><td>{count}</td></tr>\n"

    html += """
    </table>

    <h2>Tablespace Usage</h2>
    <table>
        <tr><th>Tablespace</th><th>Used (GB)</th><th>Total (GB)</th><th>% Used</th></tr>
"""
    for ts_name, used, total, pct in health_data['tablespaces']:
        html += f"        <tr><td>{ts_name}</td><td>{used}</td><td>{total}</td><td>{pct}%</td></tr>\n"

    html += """
    </table>

    <h2>Pluggable Databases</h2>
    <table>
        <tr><th>PDB Name</th><th>Open Mode</th><th>Restricted</th><th>Open Time</th><th>Size (GB)</th></tr>
"""
    for pdb in health_data['pdbs']:
        open_time = pdb[3].strftime("%Y-%m-%d %H:%M:%S") if pdb[3] else 'N/A'
        size = round(pdb[4], 2) if pdb[4] else 0
        html += f"        <tr><td>{pdb[0]}</td><td>{pdb[1]}</td><td>{pdb[2]}</td><td>{open_time}</td><td>{size}</td></tr>\n"

    html += """
    </table>

    <h2>Top 10 Wait Events</h2>
    <table>
        <tr><th>Event</th><th>Total Waits</th><th>Time Waited (cs)</th><th>Avg Wait (cs)</th></tr>
"""
    for event, total_waits, time_waited, avg_wait in health_data['wait_events']:
        html += f"        <tr><td>{event}</td><td>{total_waits}</td><td>{time_waited}</td><td>{round(avg_wait, 2)}</td></tr>\n"

    html += """
    </table>
"""

    # Database Load (AAS)
    aas = health_data.get('aas', 0)
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
    service_sessions = health_data.get('service_sessions', [])
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
    top_sql_cpu = health_data.get('top_sql_cpu', [])
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
    top_sql_disk = health_data.get('top_sql_disk', [])
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
    invalid_objects = health_data.get('invalid_objects', [])
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
    alert_log_errors = health_data.get('alert_log_errors', [])
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
    long_queries = health_data.get('long_queries', [])
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
    temp_usage = health_data.get('temp_usage', [])
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
    instance_load = health_data.get('instance_load', [])
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
    rac_gc_waits = health_data.get('rac_gc_waits', [])
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
    rac_gc_waits_inst = health_data.get('rac_gc_waits_by_instance', [])
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
    rac_interconnect = health_data.get('rac_interconnect', [])
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
    rac_ges_blocking = health_data.get('rac_ges_blocking', [])
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
    elif len(health_data.get('instances', [])) > 1:
        html += """
    <h2>RAC: GES Blocking Sessions (Last Hour)</h2>
    <div class="info-box">
        <p class="pass">✓ No blocking sessions detected</p>
    </div>
"""

    # RAC CPU Utilization per Instance
    rac_cpu_util = health_data.get('rac_cpu_util', [])
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
    rac_ges_contention = health_data.get('rac_ges_contention', [])
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


def generate_precheck_report(source_cdb, source_pdb, target_cdb, target_pdb,
                             validation_results, source_data, target_data, output_dir='outputs'):
    """
    Generate PDB validation HTML report with 4 sections.

    Args:
        source_cdb (str): Source CDB name
        source_pdb (str): Source PDB name
        target_cdb (str): Target CDB name
        target_pdb (str): Target PDB name
        validation_results (list): List of validation check dictionaries
        source_data (dict): Source database metadata
        target_data (dict): Target database metadata
        output_dir (str): Directory to save report (default: 'outputs')

    Returns:
        str: Absolute path to generated HTML report
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(output_dir, f"{source_cdb}_{source_pdb}_{target_cdb}_{target_pdb}_pdb_validation_report_{timestamp}.html")

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
    <link rel="stylesheet" href="../report_styles.css">
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


def generate_postcheck_report(source_cdb, source_pdb, target_cdb, target_pdb,
                              validation_results, source_data, target_data, param_diffs, output_dir='outputs'):
    """
    Generate PDB postcheck HTML report.

    Args:
        source_cdb (str): Source CDB name
        source_pdb (str): Source PDB name
        target_cdb (str): Target CDB name
        target_pdb (str): Target PDB name
        validation_results (list): List of validation check dictionaries
        source_data (dict): Source database metadata
        target_data (dict): Target database metadata
        param_diffs (list): List of parameter differences
        output_dir (str): Directory to save report (default: 'outputs')

    Returns:
        str: Absolute path to generated HTML report
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(output_dir, f"{source_cdb}_{source_pdb}_{target_cdb}_{target_pdb}_pdb_postcheck_report_{timestamp}.html")

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDB Clone Postcheck Report</title>
    <link rel="stylesheet" href="../report_styles.css">
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
