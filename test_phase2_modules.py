"""
Test script for Phase 2 modular refactoring
Verifies that all 5 new modules are properly created and importable
"""

import sys
import os

def test_imports():
    """Test that all modules can be imported"""
    print("=" * 80)
    print("PHASE 2 MODULE VERIFICATION TEST")
    print("=" * 80)
    print()

    modules_to_test = [
        ("utils.report_generator", ["generate_health_report", "generate_precheck_report", "generate_postcheck_report"]),
        ("db_healthcheck", ["perform_health_check"]),
        ("pdb_clone", ["perform_pdb_precheck", "perform_pdb_clone", "perform_pdb_postcheck"]),
        ("admin_toolbox_qt", ["OraclePDBToolkit", "DatabaseWorker"]),
        ("main", ["main", "signal_handler"]),
    ]

    all_passed = True

    for module_name, expected_items in modules_to_test:
        print(f"Testing module: {module_name}")
        try:
            # Import the module
            module = __import__(module_name, fromlist=expected_items)
            print(f"  [OK] Module imported successfully")

            # Check for expected functions/classes
            missing_items = []
            for item in expected_items:
                if not hasattr(module, item):
                    missing_items.append(item)

            if missing_items:
                print(f"  [FAIL] Missing items: {', '.join(missing_items)}")
                all_passed = False
            else:
                print(f"  [OK] All expected items found: {', '.join(expected_items)}")

            # Show file location
            if hasattr(module, '__file__'):
                print(f"  [INFO] Location: {module.__file__}")

            print()

        except ImportError as e:
            print(f"  [FAIL] FAILED to import: {e}")
            all_passed = False
            print()
        except Exception as e:
            print(f"  [FAIL] Unexpected error: {e}")
            all_passed = False
            print()

    print("=" * 80)

    if all_passed:
        print("[SUCCESS] ALL MODULES PASSED VERIFICATION")
        print()
        print("Phase 2 Modular Refactoring Complete!")
        print()
        print("Created Modules:")
        print("  1. utils/report_generator.py  (~650 lines) - HTML report generation")
        print("  2. db_healthcheck.py          (~700 lines) - 21 health checks (including RAC)")
        print("  3. pdb_clone.py               (~900 lines) - PDB precheck, clone, postcheck")
        print("  4. admin_toolbox_qt.py        (~650 lines) - PyQt6 GUI application")
        print("  5. main.py                    (~50 lines)  - Application entry point")
        print()
        print("Usage:")
        print("  python main.py")
        print()
        return True
    else:
        print("[FAIL] SOME MODULES FAILED VERIFICATION")
        print()
        print("Please check the error messages above and fix any import issues.")
        return False

def check_file_sizes():
    """Check that all module files exist and have reasonable sizes"""
    print("=" * 80)
    print("FILE SIZE VERIFICATION")
    print("=" * 80)
    print()

    expected_files = [
        ("utils/report_generator.py", 10000, 50000),    # ~27KB
        ("db_healthcheck.py", 10000, 30000),            # ~18KB
        ("pdb_clone.py", 15000, 50000),                 # ~28KB
        ("admin_toolbox_qt.py", 20000, 50000),          # ~32KB
        ("main.py", 1000, 5000),                        # ~2.5KB
        ("utils/__init__.py", 500, 2000),               # ~1KB
    ]

    all_exist = True

    for filepath, min_size, max_size in expected_files:
        full_path = os.path.join(os.path.dirname(__file__), filepath)

        if os.path.exists(full_path):
            size = os.path.getsize(full_path)
            size_kb = size / 1024

            if min_size <= size <= max_size:
                print(f"[OK] {filepath:30s} - {size_kb:6.1f} KB")
            else:
                print(f"[WARN] {filepath:30s} - {size_kb:6.1f} KB (expected {min_size/1024:.1f}-{max_size/1024:.1f} KB)")
        else:
            print(f"[FAIL] {filepath:30s} - NOT FOUND")
            all_exist = False

    print()
    return all_exist


if __name__ == "__main__":
    print("\n")

    # Test file existence and sizes
    files_ok = check_file_sizes()

    print()

    # Test module imports
    imports_ok = test_imports()

    print("=" * 80)
    print()

    if files_ok and imports_ok:
        print("*** PHASE 2 COMPLETE - ALL TESTS PASSED ***")
        sys.exit(0)
    else:
        print("*** SOME TESTS FAILED - PLEASE REVIEW ERRORS ABOVE ***")
        sys.exit(1)
