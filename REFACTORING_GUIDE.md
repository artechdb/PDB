# Oracle PDB Toolkit - Modular Refactoring Guide

## Overview

This document describes the modular refactoring of `oracle_pdb_toolkit.py` (2,995 lines) into a more maintainable structure with separate utility modules and configuration files.

## Created Files

### 1. `utils/db_connection.py` (265 lines)
**Purpose:** Database connection management

**Extracted from:** Lines 112-141 of `oracle_pdb_toolkit.py`

**Key Components:**
- `DatabaseConnection` class - Context manager for database connections
- `create_connection()` - Main function to create connections
- `build_dsn_string()` - DSN string builder
- `test_connection()` - Connection testing utility
- `get_connection_string()` - Get DSN without connecting

**Supported Connection Methods:**
1. **External Auth + TNS Alias** - Uses OS authentication with tnsnames.ora
2. **External Auth + Hostname/Port/Service** - Uses OS authentication with direct connection
3. **Username/Password + Hostname/Port/Service** - Uses database authentication

**Usage Examples:**

```python
from utils.db_connection import create_connection

# Example 1: External Auth with TNS Alias
params = {
    'connection_mode': 'external_auth',
    'db_name': 'PROD_CDB'
}
with create_connection(params) as db_conn:
    cursor = db_conn.get_cursor()
    cursor.execute("SELECT * FROM v$version")
    print(cursor.fetchone())

# Example 2: External Auth with Hostname/Port
params = {
    'connection_mode': 'external_auth',
    'db_name': 'PROD_CDB',
    'hostname': 'dbserver.example.com',
    'port': '1521',
    'service': 'PROD'
}
with create_connection(params) as db_conn:
    cursor = db_conn.get_cursor()
    # Execute queries...

# Example 3: Username/Password
params = {
    'connection_mode': 'user_pass',
    'hostname': 'dbserver.example.com',
    'port': '1521',
    'service': 'PROD',
    'username': 'system',
    'password': 'oracle'
}
with create_connection(params) as db_conn:
    cursor = db_conn.get_cursor()
    # Execute queries...
```

### 2. `utils/helper_functions.py` (426 lines)
**Purpose:** Utility functions and background worker thread

**Extracted from:**
- Oracle Client initialization (lines 22-79)
- DatabaseWorker class (lines 82-108)
- Storage parsing logic (lines 854-866, 900-913)

**Key Components:**

#### Oracle Client Initialization
```python
from utils.helper_functions import init_oracle_client_thick_mode

# Initialize with auto-detection
success, message = init_oracle_client_thick_mode()
if success:
    print(f"Initialized: {message}")
else:
    print(f"Failed: {message}")

# Initialize with specific path
success, message = init_oracle_client_thick_mode(
    lib_dir=r"C:\oracle\instantclient_19_8"
)
```

#### Storage Value Parsing
```python
from utils.helper_functions import parse_storage_value, format_storage_gb

# Parse storage strings
gb_value = parse_storage_value('50G')      # Returns: 50.0
gb_value = parse_storage_value('2048M')    # Returns: 2.0
gb_value = parse_storage_value('1T')       # Returns: 1024.0
gb_value = parse_storage_value('UNLIMITED') # Returns: None

# Format storage values
formatted = format_storage_gb(50.0)   # Returns: '50.00G'
formatted = format_storage_gb(None)   # Returns: 'UNLIMITED'
```

#### DatabaseWorker Thread
```python
from utils.helper_functions import DatabaseWorker

# Create worker for background operation
worker = DatabaseWorker('health_check', params)

# Connect signals
worker.finished.connect(on_finished)
worker.progress.connect(on_progress)

# Start operation in background
worker.start()

def on_finished(success, message):
    if success:
        print(f"Completed: {message}")
    else:
        print(f"Failed: {message}")

def on_progress(msg):
    print(f"Progress: {msg}")
```

**Note:** The `DatabaseWorker` class methods (`perform_health_check`, `perform_pdb_precheck`, etc.) need to be implemented in the main application or subclass.

### 3. `configs/settings.yaml` (250 lines)
**Purpose:** Centralized configuration management

**Key Sections:**

#### Application Settings
```yaml
application:
  name: "Oracle PDB Management Toolkit"
  version: "1.2.6"
```

#### Oracle Client Configuration
```yaml
oracle_client:
  thick_mode: true
  windows_paths:
    - "${ORACLE_HOME}"
    - "${ORACLE_HOME}/bin"
    - "C:/oracle/instantclient_19_8"
    # ... more paths
```

#### Connection Defaults
```yaml
connection:
  default_mode: "external_auth"
  default_port: 1521
  timeout: 30
```

#### Health Check Configuration
```yaml
health_check:
  output_dir: "."
  report_filename_pattern: "{db_name}_db_health_report_{timestamp}.html"
  thresholds:
    tablespace_warning: 80
    tablespace_critical: 90
    memory_warning: 85
    pdb_storage_warning: 80
```

#### PDB Clone Configuration
```yaml
pdb_clone:
  output_dir: "."
  validation_report_pattern: "{source_cdb}_{source_pdb}_{target_cdb}_{target_pdb}_pdb_validation_report_{timestamp}.html"
  clone:
    default_storage: ""
    file_name_convert: true
```

**Usage Example:**
```python
import yaml

# Load configuration
with open('configs/settings.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Access settings
app_name = config['application']['name']
default_port = config['connection']['default_port']
warning_threshold = config['health_check']['thresholds']['tablespace_warning']

print(f"Application: {app_name}")
print(f"Default Port: {default_port}")
print(f"Warning Threshold: {warning_threshold}%")
```

## Integration with Main Application

### Step 1: Import the Modules

```python
# At the top of oracle_pdb_toolkit.py
from utils.db_connection import create_connection, DatabaseConnection
from utils.helper_functions import (
    init_oracle_client_thick_mode,
    DatabaseWorker,
    parse_storage_value,
    format_storage_gb
)
import yaml

# Load configuration
with open('configs/settings.yaml', 'r') as f:
    CONFIG = yaml.safe_load(f)
```

### Step 2: Replace Oracle Client Initialization

Replace lines 22-79 in the original file with:

```python
# Initialize Oracle Client in Thick Mode
success, message = init_oracle_client_thick_mode()
if success:
    print(message)
else:
    print(f"WARNING: {message}")
    print("Thick mode is required for external authentication and database links.")
```

### Step 3: Replace Connection Logic

Replace connection logic in `perform_health_check()` and other methods:

**Old Code (lines 112-141):**
```python
if connection_mode == 'external_auth':
    db_name = self.params.get('db_name')
    hostname = self.params.get('hostname')
    if hostname:
        connection = oracledb.connect(dsn=db_name, externalauth=True)
    else:
        connection = oracledb.connect(dsn=db_name, externalauth=True)
else:
    hostname = self.params.get('hostname')
    port = self.params.get('port')
    service = self.params.get('service')
    username = self.params.get('username')
    password = self.params.get('password')
    dsn = f"{hostname}:{port}/{service}"
    connection = oracledb.connect(user=username, password=password, dsn=dsn)
```

**New Code:**
```python
from utils.db_connection import create_connection

# Create connection using the utility
db_conn = create_connection(self.params)
connection = db_conn.connection
cursor = db_conn.get_cursor()

# Use connection...

# Close when done
db_conn.close()

# Or use context manager:
with create_connection(self.params) as db_conn:
    cursor = db_conn.get_cursor()
    # Execute queries...
```

### Step 4: Replace Storage Parsing Logic

Replace storage parsing code (lines 854-866, 900-913) with:

**Old Code:**
```python
storage_str = source_max_pdb_storage_raw.upper()
if 'G' in storage_str:
    source_max_pdb_storage = source_max_pdb_storage_raw
elif 'M' in storage_str:
    gb_val = float(storage_str.replace('M', '')) / 1024
    source_max_pdb_storage = f"{gb_val:.2f}G"
elif 'T' in storage_str:
    gb_val = float(storage_str.replace('T', '')) * 1024
    source_max_pdb_storage = f"{gb_val:.2f}G"
else:
    gb_val = float(storage_str) / (1024**3)
    source_max_pdb_storage = f"{gb_val:.2f}G"
```

**New Code:**
```python
from utils.helper_functions import convert_storage_to_gb

# Convert and format in one call
source_max_pdb_storage = convert_storage_to_gb(
    source_max_pdb_storage_raw,
    display_format=True
)

# Or parse to float for comparisons
max_storage_gb = parse_storage_value(target_max_pdb_storage_raw)
if max_storage_gb and source_pdb_size_gb > max_storage_gb:
    storage_ok = False
```

## Benefits of Refactoring

### 1. **Improved Maintainability**
- Separated concerns into logical modules
- Easier to locate and update specific functionality
- Reduced code duplication

### 2. **Better Testability**
- Each module can be tested independently
- Mock connections for unit testing
- Isolated error handling

### 3. **Enhanced Reusability**
- Connection utilities can be used in other scripts
- Storage parsing available for any module
- DatabaseWorker can be extended for new operations

### 4. **Cleaner Code Organization**
- Original file: 2,995 lines
- New structure:
  - `db_connection.py`: 265 lines
  - `helper_functions.py`: 426 lines
  - `settings.yaml`: 250 lines
  - Main file: ~2,000 lines (after refactoring)

### 5. **Flexible Configuration**
- Centralized settings in YAML
- Easy to modify thresholds and paths
- No code changes needed for configuration updates

## Testing

Run the test suite to verify the modules:

```bash
cd C:\Users\user\Desktop\Oracle\PDB
python test_refactored_modules.py
```

Expected output:
```
============================================================
Oracle PDB Toolkit - Refactored Modules Test Suite
============================================================
Testing module imports...
✓ utils.db_connection imported successfully
✓ utils.helper_functions imported successfully
✓ configs/settings.yaml loaded successfully

Testing DSN string builder...
✓ DSN builder works: localhost:1521/FREEPDB1

Testing storage value parser...
✓ 50G -> 50.0 GB -> 50.00G
✓ 2048M -> 2.0 GB -> 2.00G
✓ 1T -> 1024.0 GB -> 1024.00G
✓ UNLIMITED -> None GB -> UNLIMITED

Testing connection string builder...
✓ External auth with hostname: dbserver:1521/PRODPDB
✓ External auth with TNS: PROD_TNS
✓ User/pass mode: localhost:1521/FREEPDB1

Testing configuration structure...
✓ Section 'application' present
✓ Section 'oracle_client' present
✓ Section 'connection' present
✓ Section 'health_check' present
✓ Section 'pdb_clone' present
✓ Section 'logging' present
✓ Section 'gui' present

Total: 5/5 tests passed
============================================================
```

## File Structure

```
C:\Users\user\Desktop\Oracle\PDB\
├── oracle_pdb_toolkit.py          # Main application (to be refactored)
├── utils\
│   ├── __init__.py                # Package initialization
│   ├── db_connection.py           # Database connection utilities (NEW)
│   └── helper_functions.py        # Helper functions and DatabaseWorker (NEW)
├── configs\
│   └── settings.yaml              # Configuration file (NEW)
├── test_refactored_modules.py     # Test suite (NEW)
├── REFACTORING_GUIDE.md           # This document (NEW)
└── requirements.txt               # Python dependencies
```

## Next Steps

1. **Update Main Application**: Integrate the new modules into `oracle_pdb_toolkit.py`
2. **Remove Duplicated Code**: Delete old connection and initialization code
3. **Test Integration**: Run full application tests
4. **Update Documentation**: Reflect changes in README.md
5. **Consider Further Refactoring**:
   - Extract report generation into `utils/report_generator.py`
   - Create separate modules for health check and PDB clone operations
   - Add unit tests for each module

## Troubleshooting

### Import Errors
If you encounter import errors:
```python
# Ensure utils directory is in Python path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
```

### Oracle Client Initialization Fails
Check:
1. ORACLE_HOME environment variable is set
2. Oracle Client libraries are accessible
3. Paths in `configs/settings.yaml` are correct
4. On Windows, ensure the correct architecture (x64 vs x86)

### Connection Failures
Verify:
1. TNS alias exists in tnsnames.ora (for external auth with TNS)
2. Hostname/port/service are correct
3. External authentication is properly configured (OS user, wallet)
4. Database listener is running

## Support

For issues or questions about the refactoring:
1. Check the test suite output
2. Review error messages and tracebacks
3. Verify configuration in `settings.yaml`
4. Ensure all dependencies are installed (`pip install -r requirements.txt`)

## Version History

- **2.0.0** (2026-01-11): Initial modular refactoring
  - Created `utils/db_connection.py`
  - Created `utils/helper_functions.py`
  - Created `configs/settings.yaml`
  - Added test suite
  - Added refactoring documentation
