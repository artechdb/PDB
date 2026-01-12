"""
Test script for refactored modules

This script verifies that the newly created modules can be imported
and their basic functionality works correctly.
"""

import sys
import os
from pathlib import Path

# Fix Windows console encoding issues
if sys.platform == 'win32':
    os.system('chcp 65001 > nul 2>&1')
    sys.stdout.reconfigure(encoding='utf-8')

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all modules can be imported."""
    print("Testing module imports...")

    try:
        from utils.db_connection import (
            DatabaseConnection,
            create_connection,
            build_dsn_string,
            test_connection,
            get_connection_string
        )
        print("✓ utils.db_connection imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import utils.db_connection: {e}")
        return False

    try:
        from utils.helper_functions import (
            init_oracle_client_thick_mode,
            parse_storage_value,
            format_storage_gb,
            convert_storage_to_gb,
            DatabaseWorker
        )
        print("✓ utils.helper_functions imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import utils.helper_functions: {e}")
        return False

    try:
        import yaml
        with open('configs/settings.yaml', 'r') as f:
            config = yaml.safe_load(f)
        print("✓ configs/settings.yaml loaded successfully")
    except Exception as e:
        print(f"✗ Failed to load configs/settings.yaml: {e}")
        return False

    return True

def test_dsn_builder():
    """Test DSN string builder."""
    print("\nTesting DSN string builder...")
    from utils.db_connection import build_dsn_string

    dsn = build_dsn_string("localhost", "1521", "FREEPDB1")
    expected = "localhost:1521/FREEPDB1"

    if dsn == expected:
        print(f"✓ DSN builder works: {dsn}")
        return True
    else:
        print(f"✗ DSN builder failed: expected {expected}, got {dsn}")
        return False

def test_storage_parser():
    """Test storage value parser."""
    print("\nTesting storage value parser...")
    from utils.helper_functions import parse_storage_value, format_storage_gb

    tests = [
        ("50G", 50.0, "50.00G"),
        ("2048M", 2.0, "2.00G"),
        ("1T", 1024.0, "1024.00G"),
        ("UNLIMITED", None, "UNLIMITED"),
    ]

    all_passed = True
    for input_val, expected_gb, expected_str in tests:
        result_gb = parse_storage_value(input_val)
        result_str = format_storage_gb(result_gb)

        if result_gb == expected_gb and result_str == expected_str:
            print(f"✓ {input_val} -> {result_gb} GB -> {result_str}")
        else:
            print(f"✗ {input_val} failed: expected {expected_gb} GB, got {result_gb}")
            all_passed = False

    return all_passed

def test_connection_string_builder():
    """Test connection string builder."""
    print("\nTesting connection string builder...")
    from utils.db_connection import get_connection_string

    # Test external auth with hostname
    params1 = {
        'connection_mode': 'external_auth',
        'db_name': 'PROD',
        'hostname': 'dbserver',
        'port': '1521',
        'service': 'PRODPDB'
    }
    conn_str1 = get_connection_string(params1)
    print(f"✓ External auth with hostname: {conn_str1}")

    # Test external auth with TNS
    params2 = {
        'connection_mode': 'external_auth',
        'db_name': 'PROD_TNS'
    }
    conn_str2 = get_connection_string(params2)
    print(f"✓ External auth with TNS: {conn_str2}")

    # Test user/pass mode
    params3 = {
        'connection_mode': 'user_pass',
        'hostname': 'localhost',
        'port': '1521',
        'service': 'FREEPDB1'
    }
    conn_str3 = get_connection_string(params3)
    print(f"✓ User/pass mode: {conn_str3}")

    return True

def test_config_structure():
    """Test configuration file structure."""
    print("\nTesting configuration structure...")

    try:
        import yaml
        with open('configs/settings.yaml', 'r') as f:
            config = yaml.safe_load(f)

        required_sections = [
            'application',
            'oracle_client',
            'connection',
            'health_check',
            'pdb_clone',
            'logging',
            'gui'
        ]

        all_present = True
        for section in required_sections:
            if section in config:
                print(f"✓ Section '{section}' present")
            else:
                print(f"✗ Section '{section}' missing")
                all_present = False

        return all_present

    except Exception as e:
        print(f"✗ Error testing config: {e}")
        return False

def main():
    """Run all tests."""
    print("="*60)
    print("Oracle PDB Toolkit - Refactored Modules Test Suite")
    print("="*60)

    results = []

    # Run tests
    results.append(("Module Imports", test_imports()))
    results.append(("DSN Builder", test_dsn_builder()))
    results.append(("Storage Parser", test_storage_parser()))
    results.append(("Connection String Builder", test_connection_string_builder()))
    results.append(("Config Structure", test_config_structure()))

    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{test_name:30} {status}")

    print(f"\nTotal: {passed}/{total} tests passed")
    print("="*60)

    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
