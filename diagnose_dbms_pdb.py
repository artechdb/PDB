"""
Diagnostic script to check DBMS_PDB package availability and signatures
This helps troubleshoot DBMS_PDB.DESCRIBE errors
"""

import oracledb
import sys
from getpass import getpass

print("=" * 80)
print("DBMS_PDB Diagnostic Tool")
print("=" * 80)

# Get connection details
print("\nEnter connection details for the SOURCE PDB:")
print("(This should be the PDB you want to describe)")
hostname = input("Hostname: ").strip()
port = input("Port [1521]: ").strip() or "1521"
service = input("Service Name (PDB): ").strip()
username = input("Username: ").strip()
password = getpass("Password: ")

dsn = f"{hostname}:{port}/{service}"

print(f"\nConnecting to: {dsn}")
print("=" * 80)

try:
    conn = oracledb.connect(user=username, password=password, dsn=dsn)
    cursor = conn.cursor()
    print("✓ Connected successfully")

    # Check Oracle version
    print("\n" + "=" * 80)
    print("1. Oracle Version")
    print("=" * 80)
    cursor.execute("SELECT banner FROM v$version WHERE banner LIKE 'Oracle%'")
    version = cursor.fetchone()
    if version:
        print(f"   {version[0]}")

    # Check current container
    print("\n" + "=" * 80)
    print("2. Current Container Context")
    print("=" * 80)
    cursor.execute("SELECT SYS_CONTEXT('USERENV', 'CON_NAME') FROM dual")
    container = cursor.fetchone()
    if container:
        print(f"   Container Name: {container[0]}")

    cursor.execute("SELECT SYS_CONTEXT('USERENV', 'CON_ID') FROM dual")
    con_id = cursor.fetchone()
    if con_id:
        print(f"   Container ID: {con_id[0]}")

    # Check DBMS_PDB package exists
    print("\n" + "=" * 80)
    print("3. DBMS_PDB Package Status")
    print("=" * 80)
    cursor.execute("""
        SELECT object_name, object_type, status
        FROM all_objects
        WHERE owner = 'SYS'
        AND object_name = 'DBMS_PDB'
        ORDER BY object_type
    """)
    objects = cursor.fetchall()
    if objects:
        for obj in objects:
            print(f"   {obj[1]}: {obj[0]} - Status: {obj[2]}")
    else:
        print("   ✗ DBMS_PDB package not found!")

    # List all procedures/functions in DBMS_PDB
    print("\n" + "=" * 80)
    print("4. DBMS_PDB Procedures and Functions")
    print("=" * 80)
    cursor.execute("""
        SELECT DISTINCT object_name, procedure_name
        FROM all_procedures
        WHERE owner = 'SYS'
        AND object_name = 'DBMS_PDB'
        ORDER BY procedure_name
    """)
    procedures = cursor.fetchall()
    if procedures:
        for proc in procedures:
            proc_name = proc[1] or '(Package Level)'
            print(f"   - {proc_name}")
    else:
        print("   ✗ No procedures found in DBMS_PDB")

    # Get DESCRIBE procedure signature (all overloads)
    print("\n" + "=" * 80)
    print("5. DBMS_PDB.DESCRIBE Signature(s)")
    print("=" * 80)
    cursor.execute("""
        SELECT argument_name, position, data_type, in_out, data_level, overload
        FROM all_arguments
        WHERE owner = 'SYS'
        AND package_name = 'DBMS_PDB'
        AND object_name = 'DESCRIBE'
        ORDER BY overload NULLS FIRST, position
    """)
    describe_args = cursor.fetchall()

    if describe_args:
        current_overload = None
        for arg in describe_args:
            arg_name = arg[0] or 'RETURN_VALUE'
            overload = arg[5] or '1'

            if overload != current_overload:
                if current_overload is not None:
                    print()
                print(f"   Overload {overload}:")
                current_overload = overload

            print(f"      Position {arg[1]}: {arg_name}")
            print(f"         Type: {arg[2]}")
            print(f"         Direction: {arg[3]}")
            print(f"         Level: {arg[4]}")
    else:
        print("   ✗ DESCRIBE procedure not found in DBMS_PDB!")
        print("   This might mean:")
        print("      - Oracle version doesn't support DBMS_PDB.DESCRIBE")
        print("      - Insufficient privileges to see the procedure")
        print("      - Different procedure name in this Oracle version")

    # Try to execute DBMS_PDB.DESCRIBE
    print("\n" + "=" * 80)
    print("6. Test DBMS_PDB.DESCRIBE Execution")
    print("=" * 80)

    # Test 1: Single parameter with named binding
    print("\n   Test 1: Named parameter (pdb_descr_xml => :xml_output)")
    try:
        xml_var = cursor.var(oracledb.DB_TYPE_CLOB)
        cursor.execute("""
            BEGIN
                DBMS_PDB.DESCRIBE(pdb_descr_xml => :xml_output);
            END;
        """, xml_output=xml_var)

        xml_clob = xml_var.getvalue()
        xml_content = xml_clob.read() if hasattr(xml_clob, 'read') else str(xml_clob)
        xml_len = len(xml_content) if xml_content else 0

        print(f"   ✓ SUCCESS!")
        print(f"      XML Length: {xml_len} characters")

        if xml_len > 0:
            print(f"      First 200 chars: {xml_content[:200]}...")

            # Save to file
            filename = "dbms_pdb_describe_test.xml"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            print(f"      ✓ XML saved to: {filename}")

    except Exception as e:
        print(f"   ✗ FAILED: {str(e)}")

        # Test 2: Positional parameter only
        print("\n   Test 2: Positional parameter (:xml_output)")
        try:
            xml_var = cursor.var(oracledb.DB_TYPE_CLOB)
            cursor.execute("""
                BEGIN
                    DBMS_PDB.DESCRIBE(:xml_output);
                END;
            """, [xml_var])

            xml_clob = xml_var.getvalue()
            xml_content = xml_clob.read() if hasattr(xml_clob, 'read') else str(xml_clob)
            xml_len = len(xml_content) if xml_content else 0

            print(f"   ✓ SUCCESS!")
            print(f"      XML Length: {xml_len} characters")

            if xml_len > 0:
                print(f"      First 200 chars: {xml_content[:200]}...")

                # Save to file
                filename = "dbms_pdb_describe_test.xml"
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(xml_content)
                print(f"      ✓ XML saved to: {filename}")

        except Exception as e2:
            print(f"   ✗ FAILED: {str(e2)}")

            print("\n   Both methods failed. DBMS_PDB.DESCRIBE cannot be executed.")
            print("   Possible reasons:")
            print("      - Procedure doesn't exist in this Oracle version")
            print("      - Different signature than expected")
            print("      - Insufficient privileges")
            print("      - Need to be in a specific PDB context")

    # Check privileges
    print("\n" + "=" * 80)
    print("7. User Privileges on DBMS_PDB")
    print("=" * 80)
    cursor.execute("""
        SELECT privilege, grantee
        FROM dba_tab_privs
        WHERE owner = 'SYS'
        AND table_name = 'DBMS_PDB'
        AND grantee IN (USER, 'PUBLIC')
    """)
    privs = cursor.fetchall()
    if privs:
        for priv in privs:
            print(f"   {priv[1]}: {priv[0]}")
    else:
        print("   ✗ No direct privileges found")
        print("   (May have privileges through roles)")

    cursor.close()
    conn.close()

    print("\n" + "=" * 80)
    print("Diagnostic Complete")
    print("=" * 80)

except Exception as e:
    print(f"\n✗ ERROR: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
