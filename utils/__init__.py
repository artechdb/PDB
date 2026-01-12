"""
Oracle PDB Toolkit - Utils Package
Version: 2.0.0

This package contains utility modules for the Oracle PDB Management Toolkit:
- db_connection: Database connection management
- helper_functions: General utility functions and DatabaseWorker thread
- report_generator: HTML report generation
"""

__version__ = '2.0.0'

# Import key classes and functions for easy access
from .db_connection import DatabaseConnection, create_connection, build_dsn_string
from .helper_functions import DatabaseWorker, init_oracle_client_thick_mode, parse_storage_value
from .report_generator import generate_health_report, generate_precheck_report, generate_postcheck_report

__all__ = [
    # Connection management
    'DatabaseConnection',
    'create_connection',
    'build_dsn_string',

    # Helper functions
    'DatabaseWorker',
    'init_oracle_client_thick_mode',
    'parse_storage_value',

    # Report generation
    'generate_health_report',
    'generate_precheck_report',
    'generate_postcheck_report',
]
