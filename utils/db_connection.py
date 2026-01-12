"""
Database Connection Management Module

This module provides database connection utilities for the Oracle PDB Toolkit.
It supports multiple connection methods:
1. External Authentication with TNS Alias
2. External Authentication with Hostname/Port/Service
3. Username/Password Authentication with Hostname/Port/Service

Extracted from oracle_pdb_toolkit.py lines 112-141
"""

import oracledb
from typing import Dict, Optional, Any


class DatabaseConnection:
    """
    Context manager for Oracle database connections.

    Provides automatic resource cleanup and cursor management.

    Attributes:
        connection: The oracledb connection object
        params: Dictionary of connection parameters

    Example:
        >>> params = {'connection_mode': 'external_auth', 'db_name': 'PROD_CDB'}
        >>> with create_connection(params) as db_conn:
        ...     cursor = db_conn.get_cursor()
        ...     cursor.execute("SELECT * FROM v$version")
    """

    def __init__(self, connection: oracledb.Connection, params: Dict[str, Any]):
        """
        Initialize DatabaseConnection wrapper.

        Args:
            connection: Active oracledb connection object
            params: Dictionary containing connection parameters
        """
        self.connection = connection
        self.params = params

    def get_cursor(self) -> oracledb.Cursor:
        """
        Get a cursor from the connection.

        Returns:
            oracledb.Cursor: Database cursor for executing queries
        """
        return self.connection.cursor()

    def close(self) -> None:
        """Close the database connection if it exists."""
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                # Silently ignore errors during close
                pass

    def __enter__(self) -> 'DatabaseConnection':
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - ensures connection is closed."""
        self.close()


def build_dsn_string(hostname: str, port: str, service: str) -> str:
    """
    Build Oracle DSN (Data Source Name) string from components.

    Args:
        hostname: Database hostname or SCAN address
        port: Database listener port (typically 1521)
        service: Service name or SID

    Returns:
        str: DSN string in format "hostname:port/service"

    Example:
        >>> build_dsn_string('dbserver.example.com', '1521', 'PROD')
        'dbserver.example.com:1521/PROD'
    """
    return f"{hostname}:{port}/{service}"


def create_connection(params: Dict[str, Any]) -> DatabaseConnection:
    """
    Create database connection based on parameters dictionary.

    Supports three connection modes:
    1. External Auth + TNS Alias: Uses OS authentication with TNS alias from tnsnames.ora
    2. External Auth + Hostname/Port/Service: Uses OS authentication with direct connection
    3. Username/Password + Hostname/Port/Service: Uses database authentication

    Args:
        params: Dictionary containing connection parameters
            Required keys:
                - connection_mode: 'external_auth' or 'user_pass'

            For external_auth mode:
                - db_name: TNS alias or DSN string
                - hostname (optional): If provided, uses direct connection
                - port (optional): Database port
                - service (optional): Service name

            For user_pass mode:
                - hostname: Database hostname
                - port: Database port
                - service: Service name
                - username: Database username
                - password: Database password

    Returns:
        DatabaseConnection: Wrapped connection object with context manager support

    Raises:
        oracledb.DatabaseError: If connection fails
        KeyError: If required parameters are missing

    Example:
        >>> # External Auth with TNS
        >>> params = {
        ...     'connection_mode': 'external_auth',
        ...     'db_name': 'PROD_CDB'
        ... }
        >>> conn = create_connection(params)

        >>> # External Auth with hostname/port
        >>> params = {
        ...     'connection_mode': 'external_auth',
        ...     'db_name': 'PROD_CDB',
        ...     'hostname': 'dbserver.example.com',
        ...     'port': '1521',
        ...     'service': 'PROD'
        ... }
        >>> conn = create_connection(params)

        >>> # Username/Password
        >>> params = {
        ...     'connection_mode': 'user_pass',
        ...     'hostname': 'dbserver.example.com',
        ...     'port': '1521',
        ...     'service': 'PROD',
        ...     'username': 'system',
        ...     'password': 'oracle'
        ... }
        >>> conn = create_connection(params)
    """
    connection_mode = params.get('connection_mode', 'external_auth')

    # External Authentication Mode
    if connection_mode == 'external_auth':
        db_name = params.get('db_name')
        if not db_name:
            raise ValueError("db_name is required for external authentication")

        # Check if hostname/port was provided (vs TNS alias)
        hostname = params.get('hostname')

        if hostname:
            # Direct connection with hostname/port using external auth
            # This builds a DSN string from components
            port = params.get('port', '1521')
            service = params.get('service', db_name)
            dsn = build_dsn_string(hostname, port, service)
            connection = oracledb.connect(dsn=dsn, externalauth=True)
        else:
            # TNS alias connection
            # db_name is treated as a TNS alias from tnsnames.ora
            connection = oracledb.connect(dsn=db_name, externalauth=True)

    # Username/Password Authentication Mode
    else:  # user_pass mode
        hostname = params.get('hostname')
        port = params.get('port', '1521')
        service = params.get('service')
        username = params.get('username')
        password = params.get('password')

        # Validate required parameters
        if not all([hostname, service, username, password]):
            raise ValueError(
                "hostname, service, username, and password are required for "
                "username/password authentication"
            )

        # Build DSN string
        dsn = build_dsn_string(hostname, port, service)
        connection = oracledb.connect(user=username, password=password, dsn=dsn)

    # Wrap connection in DatabaseConnection object
    return DatabaseConnection(connection, params)


def test_connection(params: Dict[str, Any]) -> tuple[bool, str]:
    """
    Test database connection with given parameters.

    Args:
        params: Connection parameters dictionary (same format as create_connection)

    Returns:
        tuple: (success: bool, message: str)
            - success: True if connection successful, False otherwise
            - message: Success message or error description

    Example:
        >>> params = {'connection_mode': 'external_auth', 'db_name': 'PROD'}
        >>> success, msg = test_connection(params)
        >>> print(f"Connection {'successful' if success else 'failed'}: {msg}")
    """
    try:
        with create_connection(params) as db_conn:
            cursor = db_conn.get_cursor()
            cursor.execute("SELECT 'Connection successful' FROM dual")
            result = cursor.fetchone()
            cursor.close()
            return True, result[0] if result else "Connection successful"
    except Exception as e:
        return False, f"Connection failed: {str(e)}"


# Module-level convenience function for backward compatibility
def get_connection_string(params: Dict[str, Any]) -> str:
    """
    Get the DSN connection string from parameters without connecting.

    Args:
        params: Connection parameters dictionary

    Returns:
        str: DSN string or TNS alias

    Example:
        >>> params = {
        ...     'connection_mode': 'user_pass',
        ...     'hostname': 'localhost',
        ...     'port': '1521',
        ...     'service': 'FREEPDB1'
        ... }
        >>> get_connection_string(params)
        'localhost:1521/FREEPDB1'
    """
    connection_mode = params.get('connection_mode', 'external_auth')

    if connection_mode == 'external_auth':
        db_name = params.get('db_name', '')
        hostname = params.get('hostname')

        if hostname:
            port = params.get('port', '1521')
            service = params.get('service', db_name)
            return build_dsn_string(hostname, port, service)
        else:
            return db_name
    else:
        hostname = params.get('hostname', '')
        port = params.get('port', '1521')
        service = params.get('service', '')
        return build_dsn_string(hostname, port, service)
