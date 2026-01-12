"""
Helper Functions and Utilities Module

This module provides utility functions and classes for the Oracle PDB Toolkit.
Includes Oracle Client initialization, storage parsing, and background worker threads.

Extracted from oracle_pdb_toolkit.py:
- Oracle Client initialization (lines 22-79)
- DatabaseWorker class (lines 82-108)
- Storage parsing logic (lines 854-866, 900-913)
"""

import os
import platform
import traceback
from typing import Optional, Tuple, Union
from PyQt6.QtCore import QThread, pyqtSignal
import oracledb


def init_oracle_client_thick_mode(lib_dir: Optional[str] = None) -> Tuple[bool, str]:
    """
    Initialize Oracle Client in Thick Mode.

    Thick mode is required for:
    - External authentication (OS authentication)
    - Database links
    - Advanced Oracle features

    This function tries multiple common Oracle Client locations on Windows,
    or uses auto-detection on Linux/Unix systems.

    Args:
        lib_dir: Optional specific path to Oracle Client libraries.
                 If None, will try common locations and auto-detect.

    Returns:
        tuple: (success: bool, message: str)
            - success: True if initialization successful, False otherwise
            - message: Success message with path or error description

    Example:
        >>> success, msg = init_oracle_client_thick_mode()
        >>> if success:
        ...     print(f"Oracle Client initialized: {msg}")
        ... else:
        ...     print(f"Failed to initialize: {msg}")

    Note:
        On Windows, this function checks:
        1. Provided lib_dir parameter
        2. ORACLE_HOME environment variable
        3. Common instant client locations
        4. Auto-detection

        On Linux/Unix, it relies on:
        1. Provided lib_dir parameter
        2. Auto-detection (LD_LIBRARY_PATH, default paths)
    """
    try:
        # If specific lib_dir provided, try that first
        if lib_dir:
            try:
                oracledb.init_oracle_client(lib_dir=lib_dir)
                return True, f"Oracle Client initialized in Thick Mode: {lib_dir}"
            except Exception as e:
                return False, f"Failed to initialize with provided path: {e}"

        # Platform-specific initialization
        if platform.system() == 'Windows':
            return _init_oracle_client_windows()
        else:
            return _init_oracle_client_unix()

    except Exception as e:
        return False, f"Oracle Client initialization failed: {e}"


def _init_oracle_client_windows() -> Tuple[bool, str]:
    """
    Initialize Oracle Client on Windows systems.

    Tries multiple common locations in order:
    1. ORACLE_HOME environment variable
    2. ORACLE_HOME/bin directory
    3. Common instant client locations
    4. Auto-detection

    Returns:
        tuple: (success: bool, message: str)
    """
    oracle_home = os.environ.get('ORACLE_HOME')
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
        r"C:\oracle\instantclient_23_3",
        r"C:\instantclient_19_8",
        r"C:\instantclient_21_3",
        r"C:\instantclient_23_3",
        r"C:\Users\user\Downloads\WINDOWS.X64_213000_client_home",
        r"C:\Users\user\Downloads\WINDOWS.X64_213000_client_home\bin"
    ])

    # Finally try auto-detect (None)
    possible_paths.append(None)

    last_error = None
    for lib_dir in possible_paths:
        try:
            if lib_dir:
                oracledb.init_oracle_client(lib_dir=lib_dir)
                return True, f"Oracle Client initialized in Thick Mode: {lib_dir}"
            else:
                oracledb.init_oracle_client()
                return True, "Oracle Client initialized in Thick Mode: auto-detected"
        except Exception as e:
            last_error = e
            continue

    # If we get here, all attempts failed
    oracle_home_status = oracle_home if oracle_home else "Not Set"
    return False, (
        f"Could not initialize Oracle Client. Last error: {last_error}\n"
        f"ORACLE_HOME is set to: {oracle_home_status}\n"
        "Please ensure Oracle Client libraries are accessible."
    )


def _init_oracle_client_unix() -> Tuple[bool, str]:
    """
    Initialize Oracle Client on Unix/Linux systems.

    Uses auto-detection based on:
    - LD_LIBRARY_PATH environment variable
    - Standard Oracle Client locations

    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        oracledb.init_oracle_client()
        return True, "Oracle Client initialized in Thick Mode"
    except Exception as e:
        return False, f"Oracle Client initialization failed: {e}"


def parse_storage_value(storage_str: str) -> Optional[float]:
    """
    Parse Oracle storage value string to GB (float).

    Supports various Oracle storage formats:
    - '50G' or '50g' -> 50.0 GB
    - '2048M' or '2048m' -> 2.0 GB
    - '1T' or '1t' -> 1024.0 GB
    - '5368709120' (bytes) -> 5.0 GB
    - 'UNLIMITED' -> None

    Args:
        storage_str: Storage value string from Oracle (e.g., '50G', '2048M', '1T')

    Returns:
        float: Storage value in GB, or None if UNLIMITED or unable to parse

    Example:
        >>> parse_storage_value('50G')
        50.0
        >>> parse_storage_value('2048M')
        2.0
        >>> parse_storage_value('1T')
        1024.0
        >>> parse_storage_value('UNLIMITED')
        None
    """
    if not storage_str:
        return None

    storage_str_upper = storage_str.upper().strip()

    # Check for UNLIMITED
    if storage_str_upper == 'UNLIMITED':
        return None

    try:
        # Check for gigabytes (G)
        if 'G' in storage_str_upper:
            return float(storage_str_upper.replace('G', ''))

        # Check for megabytes (M)
        elif 'M' in storage_str_upper:
            mb_val = float(storage_str_upper.replace('M', ''))
            return mb_val / 1024

        # Check for terabytes (T)
        elif 'T' in storage_str_upper:
            tb_val = float(storage_str_upper.replace('T', ''))
            return tb_val * 1024

        # Assume bytes if no unit specified
        else:
            bytes_val = float(storage_str_upper)
            return bytes_val / (1024**3)

    except (ValueError, AttributeError):
        # Return None if parsing fails
        return None


def format_storage_gb(gb_value: Optional[float], unlimited_text: str = 'UNLIMITED') -> str:
    """
    Format storage GB value as display string.

    Args:
        gb_value: Storage in GB (float) or None for unlimited
        unlimited_text: Text to display for unlimited (default: 'UNLIMITED')

    Returns:
        str: Formatted storage string (e.g., '50.00G', 'UNLIMITED')

    Example:
        >>> format_storage_gb(50.0)
        '50.00G'
        >>> format_storage_gb(None)
        'UNLIMITED'
        >>> format_storage_gb(None, 'No Limit')
        'No Limit'
    """
    if gb_value is None:
        return unlimited_text
    return f"{gb_value:.2f}G"


def convert_storage_to_gb(storage_str: str, display_format: bool = True) -> Union[str, float, None]:
    """
    Convert Oracle storage string to GB with optional formatting.

    Combines parse_storage_value and format_storage_gb for convenience.

    Args:
        storage_str: Storage value string from Oracle
        display_format: If True, return formatted string; if False, return float

    Returns:
        str or float or None: Formatted string if display_format=True,
                              float in GB if display_format=False,
                              None if UNLIMITED or parse error

    Example:
        >>> convert_storage_to_gb('2048M', display_format=True)
        '2.00G'
        >>> convert_storage_to_gb('2048M', display_format=False)
        2.0
        >>> convert_storage_to_gb('UNLIMITED', display_format=True)
        'UNLIMITED'
    """
    gb_value = parse_storage_value(storage_str)

    if display_format:
        return format_storage_gb(gb_value)
    else:
        return gb_value


class DatabaseWorker(QThread):
    """
    Background worker thread for database operations.

    This QThread subclass runs database operations in the background to prevent
    GUI freezing during long-running queries. It emits signals for progress
    updates and completion status.

    Signals:
        finished(bool, str): Emitted when operation completes
            - arg1 (bool): True if successful, False if error
            - arg2 (str): Result message or error details

        progress(str): Emitted during operation for progress updates
            - arg1 (str): Progress message

    Supported Operations:
        - health_check: Generate database health report
        - pdb_precheck: Perform PDB clone pre-checks
        - pdb_clone: Execute PDB clone operation
        - pdb_postcheck: Perform PDB clone post-checks

    Attributes:
        operation: String identifier for the operation to perform
        params: Dictionary of parameters for the operation

    Example:
        >>> # Create worker for health check
        >>> params = {'connection_mode': 'external_auth', 'db_name': 'PROD'}
        >>> worker = DatabaseWorker('health_check', params)
        >>>
        >>> # Connect signals
        >>> worker.finished.connect(on_finished)
        >>> worker.progress.connect(on_progress)
        >>>
        >>> # Start background operation
        >>> worker.start()
        >>>
        >>> def on_finished(success, message):
        ...     if success:
        ...         print(f"Operation completed: {message}")
        ...     else:
        ...         print(f"Operation failed: {message}")
        >>>
        >>> def on_progress(msg):
        ...     print(f"Progress: {msg}")

    Note:
        This class is designed to be subclassed or have its perform_* methods
        implemented in the main application. The base implementation provides
        the threading framework and signal handling.
    """

    # Qt signals for communication with main thread
    finished = pyqtSignal(bool, str)  # (success, message)
    progress = pyqtSignal(str)  # (progress_message)

    def __init__(self, operation: str, params: dict):
        """
        Initialize database worker thread.

        Args:
            operation: Operation identifier (e.g., 'health_check', 'pdb_clone')
            params: Dictionary of operation parameters
        """
        super().__init__()
        self.operation = operation
        self.params = params

    def run(self) -> None:
        """
        Main thread execution method.

        This is called when worker.start() is invoked. It routes to the
        appropriate operation handler and emits finished signal with result.

        Note: This method runs in a separate thread.
        """
        try:
            # Route to appropriate operation handler
            if self.operation == "health_check":
                result = self.perform_health_check()
            elif self.operation == "pdb_precheck":
                result = self.perform_pdb_precheck()
            elif self.operation == "pdb_clone":
                result = self.perform_pdb_clone()
            elif self.operation == "pdb_postcheck":
                result = self.perform_pdb_postcheck()
            else:
                self.finished.emit(False, f"Unknown operation: {self.operation}")
                return

            # Emit success with result
            self.finished.emit(True, result)

        except Exception as e:
            # Emit failure with error details and traceback
            error_msg = f"Error: {str(e)}\n{traceback.format_exc()}"
            self.finished.emit(False, error_msg)

    def perform_health_check(self) -> str:
        """
        Perform database health check operation.

        This method should be overridden in subclass or main application.

        Returns:
            str: HTML report or result message

        Raises:
            NotImplementedError: If not overridden
        """
        raise NotImplementedError("perform_health_check must be implemented")

    def perform_pdb_precheck(self) -> str:
        """
        Perform PDB clone pre-check operation.

        This method should be overridden in subclass or main application.

        Returns:
            str: Pre-check results or report

        Raises:
            NotImplementedError: If not overridden
        """
        raise NotImplementedError("perform_pdb_precheck must be implemented")

    def perform_pdb_clone(self) -> str:
        """
        Perform PDB clone operation.

        This method should be overridden in subclass or main application.

        Returns:
            str: Clone operation results

        Raises:
            NotImplementedError: If not overridden
        """
        raise NotImplementedError("perform_pdb_clone must be implemented")

    def perform_pdb_postcheck(self) -> str:
        """
        Perform PDB clone post-check operation.

        This method should be overridden in subclass or main application.

        Returns:
            str: Post-check results or report

        Raises:
            NotImplementedError: If not overridden
        """
        raise NotImplementedError("perform_pdb_postcheck must be implemented")
