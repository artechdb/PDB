# Oracle PDB Toolkit - Migration Checklist

## Overview
This checklist guides you through integrating the refactored modules into the main `oracle_pdb_toolkit.py` application.

---

## Pre-Migration

### 1. Backup Current Application
- [ ] Create backup of `oracle_pdb_toolkit.py`
  ```bash
  cp oracle_pdb_toolkit.py oracle_pdb_toolkit.py.backup
  ```

### 2. Verify New Modules Work
- [ ] Run test suite
  ```bash
  python test_refactored_modules.py
  ```
- [ ] Verify all tests pass (5/5)

### 3. Install Dependencies
- [ ] Ensure PyYAML is installed
  ```bash
  pip install pyyaml
  ```
- [ ] Verify all requirements
  ```bash
  pip install -r requirements.txt
  ```

---

## Phase 1: Add Imports (Top of File)

### Step 1.1: Add New Imports
- [ ] Add after existing imports (around line 20):
```python
# Import refactored modules
from utils.db_connection import create_connection, DatabaseConnection
from utils.helper_functions import (
    init_oracle_client_thick_mode,
    parse_storage_value,
    format_storage_gb,
    convert_storage_to_gb,
    DatabaseWorker as BaseWorker
)
import yaml
```

### Step 1.2: Load Configuration
- [ ] Add after imports:
```python
# Load application configuration
try:
    with open('configs/settings.yaml', 'r') as f:
        CONFIG = yaml.safe_load(f)
except Exception as e:
    print(f"WARNING: Could not load configuration: {e}")
    CONFIG = {}
```

**Location:** After line 20
**Lines Added:** ~15

---

## Phase 2: Replace Oracle Client Initialization

### Step 2.1: Remove Old Code
- [ ] Comment out or delete lines 22-79 (58 lines)
  - All the Oracle Client initialization code
  - Platform detection
  - Path iteration
  - Error handling

### Step 2.2: Add New Code
- [ ] Replace with:
```python
# Initialize Oracle Client in Thick Mode (required for DB Links and external auth)
# CRITICAL: This must be called before any connection attempts
success, message = init_oracle_client_thick_mode()
if success:
    print(message)
else:
    print(f"WARNING: {message}")
    print("Thick mode is required for external authentication and database links.")
```

**Location:** Lines 22-79
**Old Lines:** 58
**New Lines:** 6
**Reduction:** 90%

---

## Phase 3: Update DatabaseWorker Class

### Step 3.1: Change Class Declaration
- [ ] Change line 82 from:
```python
class DatabaseWorker(QThread):
```
to:
```python
class DatabaseWorker(BaseWorker):
```

### Step 3.2: Remove __init__ and run Methods
- [ ] The base class now provides these
- [ ] Keep only the perform_* methods:
  - `perform_health_check()`
  - `perform_pdb_precheck()`
  - `perform_pdb_clone()`
  - `perform_pdb_postcheck()`

**Location:** Lines 82-108
**Old Lines:** 27
**New Lines:** 2
**Note:** Or keep the full class if you prefer not to inherit

---

## Phase 4: Replace Connection Logic in perform_health_check()

### Step 4.1: Find Connection Code
- [ ] Locate lines 112-141 (30 lines of connection logic)

### Step 4.2: Replace with New Code
- [ ] Replace entire connection block with:
```python
# Connect based on mode using refactored connection utility
try:
    db_conn = create_connection(self.params)
    connection = db_conn.connection
    cursor = connection.cursor()
except Exception as e:
    raise Exception(f"Connection failed: {str(e)}")
```

### Step 4.3: Add Cleanup at End
- [ ] Before function return, add:
```python
# Clean up connection
db_conn.close()
```

**Location:** Lines 112-141
**Old Lines:** 30
**New Lines:** 8
**Reduction:** 73%

---

## Phase 5: Replace Connection Logic in perform_pdb_precheck()

### Step 5.1: Replace Source CDB Connection
- [ ] Find source CDB connection code
- [ ] Replace with:
```python
source_conn = create_connection(source_params)
source_cursor = source_conn.get_cursor()
```

### Step 5.2: Replace Target CDB Connection
- [ ] Find target CDB connection code
- [ ] Replace with:
```python
target_conn = create_connection(target_params)
target_cursor = target_conn.get_cursor()
```

### Step 5.3: Add Cleanup
- [ ] Before function return:
```python
source_conn.close()
target_conn.close()
```

**Location:** Throughout perform_pdb_precheck() method
**Multiple Occurrences:** ~5-6 places

---

## Phase 6: Replace Storage Parsing Logic

### Step 6.1: Find Storage Parsing (Location 1)
- [ ] Lines 854-866 (source PDB storage)
- [ ] Replace entire try/except block with:
```python
# Convert source MAX_PDB_STORAGE to GB for display
source_max_pdb_storage = convert_storage_to_gb(
    source_max_pdb_storage_raw,
    display_format=True
)
```

### Step 6.2: Find Storage Parsing (Location 2)
- [ ] Lines 900-913 (target PDB storage)
- [ ] Replace with:
```python
# Convert target MAX_PDB_STORAGE to GB for display and comparison
if target_max_pdb_storage_raw.upper() == 'UNLIMITED':
    target_max_pdb_storage = 'UNLIMITED'
    max_storage_gb = None
else:
    max_storage_gb = parse_storage_value(target_max_pdb_storage_raw)
    target_max_pdb_storage = format_storage_gb(max_storage_gb)
```

### Step 6.3: Find Health Check Storage Parsing
- [ ] Around lines 199-221 (health check MAX_PDB_STORAGE)
- [ ] Replace parsing logic with:
```python
# Calculate percentage if MAX_PDB_STORAGE is set and not UNLIMITED
if health_data['max_pdb_storage'] != 'UNLIMITED':
    max_storage_gb = parse_storage_value(health_data['max_pdb_storage'])
    if max_storage_gb:
        pdb_data_size_gb = health_data['pdb_data_size_gb']
        if isinstance(pdb_data_size_gb, (int, float)):
            percentage = (pdb_data_size_gb / max_storage_gb) * 100
            health_data['pdb_storage_percentage'] = f"{percentage:.1f}%"
```

**Location:** Lines 854-866, 900-913, 199-221
**Old Lines:** 26 per occurrence
**New Lines:** 5-7 per occurrence
**Reduction:** ~75%

---

## Phase 7: Replace Connection Logic in perform_pdb_clone()

### Step 7.1: Replace Clone Connection
- [ ] Find connection code in clone method
- [ ] Replace with create_connection() pattern
- [ ] Add cleanup at end

**Location:** Within perform_pdb_clone() method

---

## Phase 8: Replace Connection Logic in perform_pdb_postcheck()

### Step 8.1: Replace Postcheck Connection
- [ ] Find connection code in postcheck method
- [ ] Replace with create_connection() pattern
- [ ] Add cleanup at end

**Location:** Within perform_pdb_postcheck() method

---

## Phase 9: Update Configuration Usage

### Step 9.1: Replace Hardcoded Values
- [ ] Replace hardcoded port `1521` with:
```python
port = params.get('port', CONFIG.get('connection', {}).get('default_port', '1521'))
```

### Step 9.2: Replace Threshold Values
- [ ] Find hardcoded thresholds (80, 90, etc.)
- [ ] Replace with config values:
```python
warning_threshold = CONFIG.get('health_check', {}).get('thresholds', {}).get('tablespace_warning', 80)
```

**Location:** Throughout the file

---

## Phase 10: Testing

### Step 10.1: Unit Testing
- [ ] Run module test suite
  ```bash
  python test_refactored_modules.py
  ```
- [ ] Verify 5/5 tests pass

### Step 10.2: Integration Testing
- [ ] Test DB Health Check
  - [ ] With external auth + TNS
  - [ ] With external auth + hostname/port
  - [ ] With user/pass auth
  - [ ] Verify HTML report generation

- [ ] Test PDB Clone
  - [ ] Run pre-check validation
  - [ ] Run clone operation (if safe)
  - [ ] Run post-check validation
  - [ ] Verify validation reports

### Step 10.3: Error Testing
- [ ] Test with invalid connection
- [ ] Test with missing Oracle Client
- [ ] Test with invalid storage values
- [ ] Verify error messages are clear

---

## Phase 11: Documentation Updates

### Step 11.1: Update README
- [ ] Add section on modular architecture
- [ ] Document configuration file usage
- [ ] Update installation instructions
- [ ] Add note about PyYAML dependency

### Step 11.2: Update Version History
- [ ] Add entry for version 2.0.0
- [ ] List modular refactoring changes
- [ ] Credit the refactoring work

### Step 11.3: Create Migration Notes
- [ ] Document any breaking changes
- [ ] List deprecated functions
- [ ] Provide upgrade path

---

## Phase 12: Cleanup

### Step 12.1: Remove Commented Code
- [ ] Remove old commented-out code
- [ ] Keep backup file for reference

### Step 12.2: Update Imports
- [ ] Remove unused imports
- [ ] Organize import statements
- [ ] Group by standard/third-party/local

### Step 12.3: Code Formatting
- [ ] Run code formatter (black/autopep8)
- [ ] Fix any linting issues
- [ ] Update docstrings if needed

---

## Post-Migration

### Verify Functionality
- [ ] All features work as before
- [ ] No regressions introduced
- [ ] Performance is acceptable
- [ ] Error handling is robust

### Performance Check
- [ ] Connection time comparable
- [ ] Report generation speed same
- [ ] No memory leaks
- [ ] Thread handling correct

### Final Review
- [ ] Code is cleaner and more maintainable
- [ ] Configuration is externalized
- [ ] Tests pass
- [ ] Documentation is updated

---

## Rollback Plan

If issues occur:

1. **Immediate Rollback**
   ```bash
   cp oracle_pdb_toolkit.py.backup oracle_pdb_toolkit.py
   ```

2. **Partial Rollback**
   - Keep new modules in `utils/` and `configs/`
   - Revert to old connection logic in main file
   - Fix issues incrementally

3. **Debug Mode**
   - Enable detailed logging
   - Add print statements
   - Check error messages
   - Review traceback

---

## Estimated Time

| Phase | Time | Complexity |
|-------|------|------------|
| Pre-Migration | 15 min | Easy |
| Phase 1-2: Imports & Init | 30 min | Easy |
| Phase 3: DatabaseWorker | 15 min | Easy |
| Phase 4-8: Connection Logic | 2 hours | Medium |
| Phase 9: Configuration | 1 hour | Medium |
| Phase 10: Testing | 2 hours | Medium |
| Phase 11-12: Cleanup | 1 hour | Easy |
| **Total** | **~7 hours** | **Medium** |

---

## Success Criteria

✓ All tests pass (5/5)
✓ DB Health Check works with all 3 connection methods
✓ PDB Clone pre-check, clone, post-check all work
✓ Configuration loaded from YAML
✓ No code duplication in connection logic
✓ Storage parsing uses utility functions
✓ Oracle Client init uses utility function
✓ Documentation updated
✓ No regressions from original functionality

---

## Support Resources

- **Refactoring Guide:** `REFACTORING_GUIDE.md`
- **Summary:** `REFACTORING_SUMMARY.md`
- **Quick Reference:** `QUICK_REFERENCE.md`
- **Test Suite:** `test_refactored_modules.py`
- **Configuration:** `configs/settings.yaml`

---

## Notes

- Take it step by step
- Test after each phase
- Keep backup file until confident
- Document any issues encountered
- Update this checklist if needed

---

**Migration Version:** 2.0.0
**Date:** January 11, 2026
**Estimated Completion Time:** 7 hours
**Complexity:** Medium
