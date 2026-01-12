# RAC-Specific Health Checks - Extracted from health_check.sh

**Date**: January 10, 2026
**Version**: 1.2.8
**Status**: ✅ COMPLETE

---

## Summary

Extracted and implemented **6 RAC-specific health checks** from health_check.sh into the Python DB Health Check feature. These checks provide comprehensive Real Application Clusters (RAC) monitoring for Global Cache, Interconnect, GES, and CPU utilization across all instances.

**Auto-Detection**: RAC sections only appear when multiple instances are detected (automatically hidden for single-instance databases).

---

## RAC Health Checks Added

### 1. ✅ RAC: Global Cache Waits (Top GC Events)
**Source**: health_check.sh - 44_rac_gc_waits.sql

**SQL Query**:
```sql
SELECT event,
       COUNT(*) as samples,
       ROUND(COUNT(*) * 100 / SUM(COUNT(*)) OVER (), 2) as pct
FROM gv$active_session_history
WHERE event LIKE 'gc%'
  AND sample_time > SYSDATE - INTERVAL '1' HOUR
GROUP BY event
ORDER BY samples DESC
FETCH FIRST 10 ROWS ONLY
```

**Purpose**:
- Identify Global Cache contention across all RAC nodes
- Monitor inter-instance block transfers
- Detect excessive gc waits that degrade performance

**Thresholds**:
- **OK**: < 100 samples
- **CRITICAL**: > 100 samples (highlighted in red)

**Report Display**:
```
RAC: Global Cache Waits (Last Hour)

Event                              Samples    % of Total
gc current block busy              450        35.25%  🔴
gc cr block 2-way                  320        25.12%  🔴
gc buffer busy acquire             125        9.82%   🔴
gc cr multi block request          85         6.67%
```

---

### 2. ✅ RAC: GC Waits by Instance
**Source**: health_check.sh - 45_rac_gc_waits_by_instance.sql

**SQL Query**:
```sql
SELECT inst_id,
       event,
       COUNT(*) as wait_count
FROM gv$active_session_history
WHERE event LIKE 'gc%'
  AND sample_time > SYSDATE - INTERVAL '1' HOUR
GROUP BY inst_id, event
ORDER BY inst_id, wait_count DESC
```

**Purpose**:
- Breakdown GC waits by instance
- Identify which RAC nodes have the most contention
- Detect instance-specific performance issues

**Thresholds**:
- **OK**: < 200 waits
- **WARNING**: 200-500 waits (yellow)
- **CRITICAL**: > 500 waits (red)

**Report Display**:
```
RAC: GC Waits by Instance (Last Hour)

Instance ID    Event                              Wait Count
1              gc current block busy              650  🔴
1              gc cr block 2-way                  420  🔴
2              gc current block busy              280  🟡
2              gc cr block 2-way                  190
3              gc current block busy              120
```

**Analysis**: Instance 1 has significantly higher gc waits - investigate workload distribution

---

### 3. ✅ RAC: Interconnect Activity
**Source**: health_check.sh - 47_rac_interconnect_stats.sql

**SQL Query**:
```sql
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
```

**Purpose**:
- Monitor inter-instance block transfer volume
- Measure interconnect bandwidth utilization
- Identify excessive block shipping between nodes

**Thresholds**:
- **OK**: < 500 MB transferred
- **CRITICAL**: > 500 MB (highlighted in red)

**Report Display**:
```
RAC: Interconnect Activity

Instance ID    Metric                           MB
1              gc current blocks received       1,234.56  🔴
1              gc current blocks served         987.65    🔴
1              gc cr blocks received            456.78
1              gc cr blocks served              345.67
2              gc current blocks received       876.54    🔴
2              gc current blocks served         654.32    🔴
```

**Analysis**: High interconnect activity - check for hot blocks, poor data distribution, or network issues

---

### 4. ✅ RAC: GES Blocking Sessions
**Source**: health_check.sh - 46_rac_blocking_ges.sql

**SQL Query**:
```sql
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
```

**Purpose**:
- Identify GES (Global Enqueue Service) lock contention
- Detect cross-instance blocking sessions
- Monitor RAC-specific locking issues

**Thresholds**:
- **OK**: < 20 blocking occurrences
- **CRITICAL**: > 20 occurrences (highlighted in red)

**Report Display** (when blocking detected):
```
RAC: GES Blocking Sessions (Last Hour)

Blocking Session    Blocking Instance    Blocks    First Seen            Last Seen
1234                2                    45        2026-01-10 14:15      2026-01-10 14:45  🔴
5678                1                    28        2026-01-10 14:20      2026-01-10 14:50  🔴
```

**Report Display** (when no blocking):
```
RAC: GES Blocking Sessions (Last Hour)

✓ No blocking sessions detected
```

**Analysis**: Blocking session 1234 on instance 2 caused 45 blocks over 30 minutes - investigate application lock contention

---

### 5. ✅ RAC: CPU Utilization per Instance
**Source**: health_check.sh - 43_realtime_cpu.sql

**SQL Query**:
```sql
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
```

**Purpose**:
- Monitor CPU utilization across all RAC instances
- Detect CPU imbalance between nodes
- Identify overloaded instances

**Thresholds**:
- **OK**: < 75% CPU utilization
- **WARNING**: 75-90% (yellow)
- **CRITICAL**: > 90% (red)

**Report Display**:
```
RAC: CPU Utilization per Instance

Instance ID    CPU Busy (secs)    Total CPU (secs)    CPU Util %
1              45,678.90         50,000.00           91.36%  🔴
2              38,456.78         50,000.00           76.91%  🟡
3              25,890.12         50,000.00           51.78%
```

**Analysis**: Instance 1 is CPU-constrained (91%), Instance 3 is underutilized (52%) - workload imbalance detected

---

### 6. ✅ RAC: Global Enqueue Contention
**Source**: health_check.sh - 48_rac_global_enqueue_contention.sql

**SQL Query**:
```sql
SELECT event,
       COUNT(*) as samples
FROM gv$active_session_history
WHERE event LIKE 'ges%'
  AND sample_time > SYSDATE - INTERVAL '1' HOUR
GROUP BY event
ORDER BY samples DESC
```

**Purpose**:
- Monitor GES (Global Enqueue Service) wait events
- Identify global resource contention
- Detect RAC-specific enqueue bottlenecks

**Thresholds**:
- **OK**: < 50 samples
- **CRITICAL**: > 50 samples (highlighted in red)

**Report Display**:
```
RAC: Global Enqueue Contention (Last Hour)

Event                          Samples
ges message wait               125  🔴
ges remote message             78   🔴
ges lmd to send msgs           42
```

---

## Implementation Details

### Auto-Detection Logic

All RAC checks include automatic detection:

```python
# Only add RAC data if multiple instances detected
if gc_waits and len(health_data.get('instances', [])) > 1:
    health_data['rac_gc_waits'] = gc_waits
else:
    health_data['rac_gc_waits'] = []
```

**Behavior**:
- **Single Instance**: RAC sections completely hidden
- **RAC (2+ Instances)**: All RAC sections displayed

---

### Data Gathering (Lines 409-539)

```python
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
    if gc_waits and len(health_data.get('instances', [])) > 1:
        health_data['rac_gc_waits'] = gc_waits
    else:
        health_data['rac_gc_waits'] = []
except Exception:
    health_data['rac_gc_waits'] = []

# ... (similar pattern for other 5 checks)
```

### HTML Report Generation (Lines 1901-1984)

- **Color-coded thresholds**: Red (critical), yellow (warning), green (OK)
- **Conditional display**: Only show sections with data
- **Friendly messages**: "✓ No blocking sessions detected" when clean
- **Instance-specific breakdowns**: Helps identify problematic nodes

---

## Benefits

### RAC Performance Monitoring
- **Global Cache**: Identify inter-instance block transfer bottlenecks
- **Interconnect**: Monitor network bandwidth utilization between nodes
- **GES Locking**: Detect cross-instance lock contention
- **CPU Balance**: Identify workload distribution issues

### Proactive Alerting
- **Color-Coded Thresholds**: Instant visual identification of issues
- **Historical Tracking**: Last hour data provides trend visibility
- **Instance Breakdown**: Pinpoint which node has problems

### Production-Ready
- **Extracted from health_check.sh**: Battle-tested in production
- **Auto-Detection**: Works for both RAC and single-instance
- **Comprehensive**: Covers all major RAC contention points

---

## RAC Issue Diagnosis Guide

### High Global Cache Waits

**Symptoms**:
- `gc current block busy` > 100 samples
- `gc cr block 2-way` high percentage

**Possible Causes**:
1. **Hot Blocks**: Multiple instances accessing same blocks
2. **Poor Partitioning**: Data not distributed across instances
3. **Interconnect Latency**: Network performance degradation

**Actions**:
1. Check application data distribution
2. Review partitioning strategy
3. Monitor interconnect network performance
4. Consider instance caging or service-based routing

---

### Instance Skew

**Symptoms**:
- One instance has 2x CPU utilization of others
- Uneven GC wait distribution across instances

**Possible Causes**:
1. **Service Routing**: All connections going to one instance
2. **Singleton Services**: Service running on single instance only
3. **Application Design**: Hardcoded connection to specific instance

**Actions**:
1. Review service configuration and routing
2. Enable Load Balancing and Connection Pool balancing
3. Use `REMOTE_LISTENER` for proper connection distribution
4. Check application connection strings

---

### GES Blocking

**Symptoms**:
- Multiple blocking sessions detected
- `ges message wait` events high

**Possible Causes**:
1. **Application Locks**: Long-held transactions across instances
2. **Enqueue Contention**: Global resource bottlenecks
3. **Sequence Caching**: Insufficient sequence cache size

**Actions**:
1. Review application transaction patterns
2. Increase sequence cache size
3. Tune `_GC_POLICY_TIME` if needed
4. Check for serialization points in application

---

### High Interconnect Activity

**Symptoms**:
- `gc current blocks received/served` > 500 MB
- High interconnect bandwidth utilization

**Possible Causes**:
1. **Full Table Scans**: Excessive block shipping
2. **Index Scans**: Hot index blocks
3. **Poor Caching**: Blocks not staying in local buffer cache

**Actions**:
1. Review SQL execution plans
2. Increase `DB_CACHE_SIZE` if needed
3. Consider result cache for frequently accessed data
4. Partition large tables by instance

---

## Comparison: health_check.sh RAC Checks vs Python Toolkit

| RAC Feature | health_check.sh | Python Toolkit | Status |
|-------------|-----------------|----------------|--------|
| Global Cache Waits | ✅ Yes | ✅ Added | ✅ Merged |
| GC Waits by Instance | ✅ Yes | ✅ Added | ✅ Merged |
| Interconnect Activity | ✅ Yes | ✅ Added | ✅ Merged |
| GES Blocking | ✅ Yes | ✅ Added | ✅ Merged |
| CPU Util per Instance | ✅ Yes | ✅ Added | ✅ Merged |
| Global Enqueue | ✅ Yes | ✅ Added | ✅ Merged |
| Instance Skew Analysis | ✅ Yes (AWR) | ⏸️ Basic | 📋 Future (AWR) |
| Auto-Detection | ❌ No | ✅ Yes | ✅ Advantage |
| Color Coding | ⚠️ Limited | ✅ Full | ✅ Advantage |

---

## Testing

### Test Scenarios

1. **Single Instance Database**
   ```
   Expected: No RAC sections appear in report
   Result: ✅ Clean report, no RAC checks displayed
   ```

2. **RAC Environment (2+ Instances)**
   ```
   Expected: All 6 RAC sections appear
   Result: ✅ All RAC checks displayed with instance breakdowns
   ```

3. **RAC with GC Contention**
   ```
   Expected: Red highlighting on high gc waits
   Result: ✅ Critical waits highlighted in red
   ```

4. **RAC with No Issues**
   ```
   Expected: Friendly "✓ No issues" messages
   Result: ✅ Clean display with positive messages
   ```

---

## Files Modified

1. **[oracle_pdb_toolkit.py](oracle_pdb_toolkit.py)**
   - Lines 409-539: Added 6 RAC-specific health check queries
   - Lines 1901-1984: Added HTML report sections for RAC checks
   - Total: ~215 lines added

2. **[RAC_ENHANCEMENTS.md](RAC_ENHANCEMENTS.md)** (this file)
   - Complete documentation of RAC health checks

---

## Future Enhancements

### AWR-Based RAC Checks (from health_check.sh)

1. **Instance Skew Analysis** - Historical workload distribution
2. **IOPS Trends per Instance** - I/O performance over time
3. **AWR-Based GC Stats** - Historical GC contention analysis
4. **Interconnect Bandwidth Trends** - Network performance history

### Additional RAC Metrics

5. **Cache Fusion Statistics** - Block transfer efficiency
6. **GCS/GES Resource Usage** - Global resource consumption
7. **Remastering Events** - Dynamic remastering frequency
8. **DRM Statistics** - Dynamic Resource Mastering metrics

---

## Summary

Successfully extracted and implemented **6 comprehensive RAC health checks** from health_check.sh:

✅ **Global Cache Waits** - Inter-instance block transfer contention
✅ **GC Waits by Instance** - Per-node GC wait breakdown
✅ **Interconnect Activity** - Network bandwidth utilization
✅ **GES Blocking Sessions** - Cross-instance lock contention
✅ **CPU Utilization per Instance** - Per-node CPU monitoring
✅ **Global Enqueue Contention** - GES resource bottlenecks

**Key Features**:
- Auto-detection of RAC environment
- Color-coded thresholds (red/yellow/green)
- Production-proven queries from health_check.sh
- Comprehensive instance-level breakdowns
- Clean display for non-RAC databases

---

**Version**: 1.2.8
**Status**: ✅ Production Ready
**Last Updated**: January 10, 2026
