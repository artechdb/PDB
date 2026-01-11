"""
Oracle Connection Test Script
Tests Oracle Instant Client and database connectivity
"""

import sys
import oracledb

print("=" * 70)
print("Oracle Connection Test")
print("=" * 70)

# Test 1: Check oracledb version
print("\n1. Checking python-oracledb version...")
print(f"   Version: {oracledb.__version__}")

# Test 2: Try to initialize Oracle Client (Thick Mode)
print("\n2. Attempting to initialize Oracle Client (Thick Mode)...")
initialized = False

import platform
import os

if platform.system() == 'Windows':
    # Check ORACLE_HOME environment variable first
    oracle_home = os.environ.get('ORACLE_HOME')

    possible_paths = []

    # Add ORACLE_HOME if set
    if oracle_home:
        print(f"   ORACLE_HOME detected: {oracle_home}")
        possible_paths.append(oracle_home)
        possible_paths.append(os.path.join(oracle_home, 'bin'))

    # Add common instant client locations
    possible_paths.extend([
        r"C:\oracle\instantclient_19_8",
        r"C:\oracle\instantclient_21_3",
        r"C:\instantclient_19_8",
        r"C:\instantclient_21_3",
        r"C:\Users\user\Downloads\WINDOWS.X64_213000_client_home",
        r"C:\Users\user\Downloads\WINDOWS.X64_213000_client_home\bin"
    ])

    # Finally try auto-detect
    possible_paths.append(None)

    last_error = None
    for lib_dir in possible_paths:
        try:
            if lib_dir:
                print(f"   Trying: {lib_dir}")
                oracledb.init_oracle_client(lib_dir=lib_dir)
            else:
                print(f"   Trying: auto-detect from PATH/ORACLE_HOME")
                oracledb.init_oracle_client()

            print(f"   SUCCESS: Oracle Client initialized")
            if lib_dir:
                print(f"   Location: {lib_dir}")
            else:
                print(f"   Location: auto-detected")
            initialized = True
            break
        except Exception as e:
            last_error = e
            print(f"   Failed: {e}")
            continue
else:
    try:
        oracledb.init_oracle_client()
        print("   SUCCESS: Oracle Client initialized")
        initialized = True
    except Exception as e:
        print(f"   Failed: {e}")
        last_error = e

if not initialized:
    print("\n   ERROR: Could not initialize Oracle Client!")
    print(f"   Last error: {last_error}")
    print(f"   ORACLE_HOME: {os.environ.get('ORACLE_HOME', 'Not Set')}")
    print(f"   PATH: {os.environ.get('PATH', 'Not Set')[:200]}...")
    print("\n   Troubleshooting:")
    print("   - If ORACLE_HOME is set, ensure it points to a valid Oracle installation")
    print("   - Check that the Oracle Client DLLs exist in the bin directory")
    print("   - For Instant Client, ensure oci.dll, oraociei*.dll exist")
    print("   - Download from: https://www.oracle.com/database/technologies/instant-client/downloads.html")
    sys.exit(1)

# Test 3: Check if Thick Mode is active
print("\n3. Checking connection mode...")
print(f"   Thick mode: {oracledb.is_thin_mode() == False}")
print(f"   Thin mode: {oracledb.is_thin_mode()}")

if oracledb.is_thin_mode():
    print("   WARNING: Still in Thin Mode! External authentication requires Thick Mode.")
    sys.exit(1)

# Test 4: Test database connection
print("\n4. Testing database connection...")
print("   Enter TNS alias to test (e.g., ORCL or press Enter to skip): ", end='')
tns_alias = input().strip()

if tns_alias:
    print(f"\n   Attempting to connect to: {tns_alias}")
    print(f"   Using external authentication (no password)...")

    try:
        conn = oracledb.connect(dsn=tns_alias, externalauth=True)
        print("   SUCCESS: Connected to database!")

        # Get database info
        cursor = conn.cursor()
        cursor.execute("SELECT banner FROM v$version WHERE ROWNUM = 1")
        version = cursor.fetchone()[0]
        print(f"   Database: {version}")

        cursor.execute("SELECT name, open_mode FROM v$database")
        db_info = cursor.fetchone()
        print(f"   DB Name: {db_info[0]}")
        print(f"   Open Mode: {db_info[1]}")

        cursor.execute("SELECT sys_context('USERENV', 'SESSION_USER') FROM dual")
        user = cursor.fetchone()[0]
        print(f"   Connected as: {user}")

        cursor.close()
        conn.close()

        print("\n   Connection test PASSED!")

    except oracledb.DatabaseError as e:
        error, = e.args
        print(f"   ERROR: {error.message}")
        print("\n   Troubleshooting:")
        if "DPY-4001" in str(error.message):
            print("   - External authentication not configured")
            print("   - Check that user exists with IDENTIFIED EXTERNALLY")
            print("   - Verify SQLNET.AUTHENTICATION_SERVICES = (NTS) in sqlnet.ora")
            print("   - Or configure Oracle Wallet")
        elif "ORA-12154" in str(error.message):
            print("   - TNS alias not found in tnsnames.ora")
            print("   - Check TNS_ADMIN environment variable")
            print("   - Verify tnsnames.ora location")
        elif "ORA-01017" in str(error.message):
            print("   - Invalid credentials or external auth not working")
            print("   - Verify OS authentication is configured on database")
        else:
            print("   - Check Oracle alert log for details")
            print("   - Verify network connectivity to database")
        sys.exit(1)
else:
    print("   Skipped database connection test")

print("\n" + "=" * 70)
print("All tests completed successfully!")
print("You are ready to use the Oracle PDB Toolkit")
print("=" * 70)
