# Oracle PDB Toolkit - Version History

**Current Version**: 1.2.8
**Last Updated**: January 10, 2026

---

## Version 1.2.8 (January 10, 2026) - RAC Health Checks

### Summary
Added 6 comprehensive RAC-specific health checks extracted from health_check.sh with automatic detection and color-coded thresholds.

### New Features
1. **RAC: Global Cache Waits (Top GC Events)**
   - Monitors inter-instance block transfer contention
   - Threshold: > 100 samples = CRITICAL
   - Shows percentage distribution of GC wait events

2. **RAC: GC Waits by Instance**
   - Per-instance breakdown of Global Cache waits
   - Thresholds: > 500 waits = CRITICAL, 200-500 = WARNING
   - Identifies which RAC nodes have the most contention

3. **RAC: Interconnect Activity**
   - Monitors inter-instance block transfer volume
   - Threshold: > 500 MB = CRITICAL
   - Tracks gc current/cr blocks received/served

4. **RAC: GES Blocking Sessions**
   - Detects cross-instance blocking sessions
   - Threshold: > 20 blocking occurrences = CRITICAL
   - Shows first/last seen timestamps

5. **RAC: CPU Utilization per Instance**
   - Per-node CPU monitoring
   - Thresholds: > 90% = CRITICAL, 75-90% = WARNING
   - Identifies CPU imbalance between nodes

6. **RAC: Global Enqueue Contention**
   - Monitors GES wait events
   - Threshold: > 50 samples = CRITICAL
   - Identifies global resource bottlenecks

### Technical Details
- **Auto-Detection**: RAC sections only appear when multiple instances detected
- **Smart Queries**: All use gv$ views for multi-instance support
- **Color Coding**: Red (critical), yellow (warning), green (OK)
- **Error Handling**: Graceful fallback if RAC queries fail

### Files Modified
- `oracle_pdb_toolkit.py`: Lines 409-539 (data gathering), 1901-1984 (HTML report)
- `RAC_ENHANCEMENTS.md`: Complete documentation with diagnostic guide

### Documentation
See [RAC_ENHANCEMENTS.md](RAC_ENHANCEMENTS.md) for:
- Detailed SQL queries
- Threshold explanations
- RAC issue diagnosis guide
- Troubleshooting recommendations

---

## Version 1.2.7 (January 10, 2026) - Enhanced Health Checks

### Summary
Extracted and merged 10 key health checks from the 4,213-line health_check.sh bash script into the Python DB Health Check feature.

### New Features
1. **Active Sessions by Service**
   - Monitor session distribution across application services
   - Identify services with high activity
   - Detect connection pooling issues

2. **Database Load (AAS - Average Active Sessions)**
   - Real-time database load measurement (last 5 minutes)
   - Thresholds: > 10 = CRITICAL, > 5 = WARNING, ≤ 5 = OK
   - Color-coded status indicator

3. **Top 10 SQL by CPU Time**
   - Identify CPU-intensive SQL statements
   - Shows CPU seconds, executions, CPU per execution
   - Helps optimize high-CPU queries

4. **Top 10 SQL by Disk Reads**
   - Identify I/O-intensive queries
   - Shows disk reads, executions, reads per execution
   - Optimize storage-intensive operations

5. **Invalid Objects**
   - Detect compilation errors in database objects
   - Grouped by owner and object type
   - Prevents application failures

6. **Alert Log Errors (Last Hour)**
   - Monitor critical database errors
   - Shows ORA- errors from v$diag_alert_ext
   - Early detection for proactive troubleshooting

7. **Long Running Queries (> 5 Minutes)**
   - Identify stuck or long-running queries
   - Shows elapsed time, SQL_ID, username
   - Monitor batch job execution

8. **Temporary Tablespace Usage**
   - Monitor temp space consumption
   - Thresholds: > 90% = CRITICAL, 75-90% = WARNING
   - Detect queries using excessive temp space

9. **RAC Instance Load Distribution**
   - RAC-specific: Detect load imbalance across nodes
   - Shows DB time per instance
   - Only displayed if multiple instances detected

10. **Enhanced Top Wait Events** (existing feature maintained)
    - Shows top database bottlenecks
    - Time-based ordering for performance tuning

### Technical Details
- **Production-Proven**: All queries extracted from battle-tested health_check.sh
- **Conditional Display**: Sections only shown when data is available
- **Friendly Messages**: "✓ No issues found" when clean
- **Color-Coded**: Instant visual identification of problems

### Files Modified
- `oracle_pdb_toolkit.py`: Lines 263-408 (data gathering), 1638-1767 (HTML report)
- `HEALTH_CHECK_ENHANCEMENTS.md`: Complete documentation

### Documentation
See [HEALTH_CHECK_ENHANCEMENTS.md](HEALTH_CHECK_ENHANCEMENTS.md) for:
- SQL query details
- Purpose and thresholds for each check
- Report display examples
- Testing recommendations

---

## Version 1.2.6 (January 10, 2026) - UX & Reporting Enhancements

### Summary
Three user-requested enhancements to improve user experience and reporting capabilities.

### New Features

#### 1. Auto-Open HTML Reports
- All HTML reports automatically open in default browser after generation
- Works for: DB Health Check, PDB Precheck, PDB Postcheck
- Graceful fallback if browser launch fails
- Cross-platform support (Windows, Linux, macOS)

**Implementation**:
```python
import webbrowser
webbrowser.open('file://' + report_path)
```

#### 2. Enhanced DB Health Check Report
Added to "Database Information" section:
- **Instance Name/Hostname**: Shows all instances (supports RAC) using gv$instance
- **Database Size**: Total size of all datafiles in GB
- **MAX_PDB_STORAGE**: Shows limit and usage percentage (if set)

**Display Example** (RAC):
```
Instance 1: FREE1 @ rac1.artechdb.com
Instance 2: FREE2 @ rac2.artechdb.com
Database Size: 125.73 GB
MAX_PDB_STORAGE: 200G (62.87% used)
```

**Technical Note**: Queries MAX_PDB_STORAGE by switching to PDB context (ALTER SESSION SET CONTAINER), then switches back to CDB$ROOT

#### 3. Standardized MAX_PDB_STORAGE Display (GB Only)
All MAX_PDB_STORAGE values converted to GB for consistency:

| Database Value | Displayed As | Calculation |
|----------------|--------------|-------------|
| UNLIMITED | UNLIMITED | No conversion |
| 50G | 50.00G | Already in GB |
| 2048M | 2.00G | 2048 / 1024 = 2.00 |
| 51200M | 50.00G | 51200 / 1024 = 50.00 |
| 1T | 1024.00G | 1 * 1024 = 1024.00 |
| 2T | 2048.00G | 2 * 1024 = 2048.00 |

### Files Modified
- `oracle_pdb_toolkit.py`:
  - Lines 6-18: Added webbrowser import
  - Lines 154-228: Instance info, DB size, MAX_PDB_STORAGE gathering
  - Lines 568-633: GB conversion for MAX_PDB_STORAGE
  - Lines 1370-1387, 1578-1592, 1692-1706: Auto-open for all reports
  - Lines 1572-1590: Enhanced Database Information section
- `ENHANCEMENTS_V1.2.6.md`: Complete documentation

### Upgrade Notes
- No configuration changes required
- Uses Python `webbrowser` module (built-in, no installation needed)
- CDB context switching happens transparently
- Compatible with Oracle 19c, 21c, 23ai, 26ai

### Documentation
See [ENHANCEMENTS_V1.2.6.md](ENHANCEMENTS_V1.2.6.md) for detailed implementation and testing instructions.

---

## Version 1.2.5 and Earlier

### Key Features (Historical)
- PDB Clone operations (Precheck, Clone, Postcheck)
- Basic DB Health Check
- External authentication support
- Three flexible connection options:
  1. External Auth + TNS Alias
  2. External Auth + Hostname/Port
  3. Username/Password + Hostname/Port
- HTML report generation
- PyQt6 GUI
- Background processing with QThread
- Comprehensive error handling

---

## Upgrade Path

### From 1.2.5 → 1.2.6
- **Breaking Changes**: None
- **New Dependencies**: None (webbrowser is built-in)
- **Configuration**: No changes required
- **Reports**: Auto-open feature added, otherwise identical format

### From 1.2.6 → 1.2.7
- **Breaking Changes**: None
- **New Dependencies**: None
- **Configuration**: No changes required
- **Reports**: 10 new sections added to health check report

### From 1.2.7 → 1.2.8
- **Breaking Changes**: None
- **New Dependencies**: None
- **Configuration**: No changes required
- **Reports**: 6 new RAC sections added (auto-hidden for single-instance)

---

## Total Health Checks

The DB Health Check feature now includes **21 comprehensive checks**:

### Original Checks (5)
1. Database Information (enhanced in v1.2.6)
2. Session Statistics
3. Tablespace Usage
4. Pluggable Databases
5. Top 10 Wait Events

### Added in v1.2.7 (10)
6. Database Load (AAS)
7. Active Sessions by Service
8. Top 10 SQL by CPU Time
9. Top 10 SQL by Disk Reads
10. Invalid Objects
11. Alert Log Errors (Last Hour)
12. Long Running Queries (> 5 Minutes)
13. Temporary Tablespace Usage
14. RAC Instance Load Distribution (RAC only)

### Added in v1.2.8 (6 RAC-specific)
15. RAC: Global Cache Waits (Top GC Events)
16. RAC: GC Waits by Instance
17. RAC: Interconnect Activity
18. RAC: GES Blocking Sessions
19. RAC: CPU Utilization per Instance
20. RAC: Global Enqueue Contention

---

## Statistics

### Lines of Code Added
- v1.2.6: ~150 lines (webbrowser, enhanced DB info, GB conversion)
- v1.2.7: ~270 lines (10 health checks + HTML sections)
- v1.2.8: ~215 lines (6 RAC checks + HTML sections)
- **Total**: ~635 lines of production-ready code

### Health Checks Extracted
- From health_check.sh (4,213 lines): **16 health checks** extracted and ported to Python
- Streamlined from 4,213 lines of bash to ~635 lines of Python

### Features Added
- ✅ Auto-open HTML reports
- ✅ Enhanced database information
- ✅ GB standardization
- ✅ 10 general health checks
- ✅ 6 RAC-specific health checks
- ✅ Color-coded thresholds
- ✅ Auto-detection (RAC vs single-instance)
- ✅ Comprehensive diagnostic guides

---

## Support

For version-specific questions or issues:
1. Check the corresponding enhancement documentation (ENHANCEMENTS_V*.md)
2. Review the version's section in this document
3. Consult your Oracle DBA team

---

**Last Updated**: January 10, 2026
**Current Version**: 1.2.8
