# Connection Modes Reference

## DB Health Check - Two Connection Methods

### Method 1: External Authentication (Thick Mode)

**When to Use**:
- You have OS authentication or Oracle Wallet configured
- You want passwordless connections
- Security policy requires no password entry

**Requirements**:
- Oracle Instant Client installed (Thick Mode)
- OS authentication or Oracle Wallet configured
- User exists with `IDENTIFIED EXTERNALLY` (for OS auth)
- **Optional**: TNS alias configured OR direct hostname/port connection

**How to Connect**:

**Option A: With TNS Alias**
1. Select: **External Authentication (OS Auth / Wallet)**
2. Enter: **TNS Alias** (e.g., `PROD_CDB`, `orcl_high`)
3. Click: **Generate Health Report**

**Example**:
```
Connection Method: [•] External Authentication (OS Auth / Wallet)

TNS Alias: PROD_CDB

— OR —

Hostname: (empty)
Port: (empty)
Service Name: (empty)
```

**Option B: With Hostname/Port (No TNS Required)**
1. Select: **External Authentication (OS Auth / Wallet)**
2. Leave TNS Alias empty
3. Enter: **Hostname**, **Port**, **Service Name**
4. Click: **Generate Health Report**

**Example**:
```
Connection Method: [•] External Authentication (OS Auth / Wallet)

TNS Alias: (empty)

— OR —

Hostname: prod-db-01.example.com
Port: 1521
Service Name: PROD_CDB
```

**Advantages**:
- ✓ No password needed
- ✓ More secure (credentials managed by OS/Wallet)
- ✓ Supports all toolkit features
- ✓ Required for PDB clone operations
- ✓ **NEW**: Can use hostname/port instead of TNS alias

**Disadvantages**:
- ✗ Requires Oracle Client installation
- ✗ Requires external auth setup (OS auth or Wallet)
- ✗ TNS configuration required only if using TNS alias option

---

### Method 2: Username/Password (Thin Mode)

**When to Use**:
- Quick ad-hoc health checks
- No Oracle Client installed
- No TNS configuration available
- Testing/troubleshooting database connectivity

**Requirements**:
- **None!** No Oracle Client needed
- Only need: hostname, port, service name, credentials

**How to Connect**:
1. Select: **Username / Password**
2. Fill in details:
   - **Hostname**: Database server hostname or IP
   - **Port**: Usually `1521` (default)
   - **Service Name**: Database service name
   - **Username**: Database username
   - **Password**: User password
3. Click: **Generate Health Report**

**Example**:
```
Connection Method: [•] Username / Password

Hostname: prod-db-01.example.com
Port: 1521
Service Name: PROD_CDB
Username: system
Password: ********
```

**Advantages**:
- ✓ No Oracle Client installation required
- ✓ Works from any computer with Python
- ✓ No TNS configuration needed
- ✓ Great for quick health checks
- ✓ Works across network without local Oracle setup

**Disadvantages**:
- ✗ Password must be entered each time (not stored)
- ✗ Cannot be used for PDB clone operations
- ✗ Limited to health check functionality only

---

## PDB Clone Operations

**Note**: PDB clone operations (Precheck, Clone, Postcheck) **ALWAYS require**:
- Thick Mode (Oracle Instant Client)
- External authentication
- Database link support

This is because PDB cloning uses `CREATE PLUGGABLE DATABASE ... FROM ...@LINK` which requires:
1. Database links (not supported in Thin Mode)
2. Appropriate privileges (typically DBA)
3. Network connectivity between CDBs

---

## Connection Mode Comparison

| Feature | External Auth (Thick) | Username/Password (Thin) |
|---------|----------------------|--------------------------|
| Oracle Client Required | Yes | No |
| TNS Configuration | Required | Not Required |
| Password Entry | No | Yes (each session) |
| DB Health Check | ✓ Yes | ✓ Yes |
| PDB Clone Operations | ✓ Yes | ✗ No |
| Database Links | ✓ Supported | ✗ Not Supported |
| Setup Complexity | High | Low |
| Best For | Production Operations | Ad-hoc Queries |

---

## Quick Decision Tree

**Need to clone a PDB?**
- → Use **External Authentication** (Thick Mode required)

**Just need a quick health check?**
- → Use **Username/Password** (works anywhere, no install needed)

**Have Oracle Client installed?**
- → Use **External Authentication** (more secure)

**Don't have Oracle Client?**
- → Use **Username/Password** (works immediately)

**Security policy forbids password entry?**
- → Use **External Authentication** (passwordless)

---

## Setup Time Estimate

**External Authentication**:
- First time setup: 30-60 minutes
  - Install Oracle Client (10 min)
  - Configure TNS (5 min)
  - Setup OS auth or wallet (15-45 min)
- After setup: Instant (no credentials needed)

**Username/Password**:
- First time setup: 0 minutes (just need credentials)
- Each connection: ~10 seconds (enter hostname, port, service, username, password)

---

## Security Considerations

**External Authentication**:
- Credentials never exposed in application
- OS or wallet manages authentication
- Suitable for production environments
- Audit trail maintained by OS/database

**Username/Password**:
- Password entered in GUI (not stored)
- Password visible to user during entry
- Suitable for non-production/testing
- Consider using service accounts with limited privileges

---

## Troubleshooting

### External Authentication Issues

**Error: "DPY-4001: no credentials specified"**
```
Solution:
1. Verify Oracle Client is installed and initialized
2. Check external authentication is configured
3. Test with: sqlplus /@TNS_ALIAS
```

**Error: "ORA-12154: TNS:could not resolve"**
```
Solution:
1. Check tnsnames.ora exists and has your alias
2. Verify TNS_ADMIN environment variable
3. Confirm alias name spelling
```

### Username/Password Issues

**Error: "ORA-01017: invalid username/password"**
```
Solution:
1. Verify username and password are correct
2. Check if account is locked: SELECT username, account_status FROM dba_users WHERE username = 'YOUR_USER';
3. Ensure user has necessary privileges
```

**Error: "Connection timeout"**
```
Solution:
1. Verify hostname/IP is correct
2. Check port number (default 1521)
3. Confirm firewall allows connection
4. Test network: ping hostname
```

---

## Examples

### Example 1: Production Health Check (External Auth)
```
Use Case: Weekly health check on production CDB
Method: External Authentication
Why: No password entry, more secure, automated via scripts

Setup:
- TNS Alias: PROD_CDB
- Authentication: OS Authentication (configured once)
- Time: < 5 seconds to run
```

### Example 2: Emergency Troubleshooting (Username/Password)
```
Use Case: Database is down, need quick health check from laptop
Method: Username/Password
Why: No local Oracle Client, need immediate access

Setup:
- Hostname: 192.168.1.100
- Port: 1521
- Service: PROD
- Username: sys as sysdba
- Password: (entered securely)
- Time: ~30 seconds to connect and run
```

### Example 3: PDB Clone (Must Use External Auth)
```
Use Case: Clone PROD PDB to DEV environment
Method: External Authentication (REQUIRED)
Why: Database links and special privileges needed

Setup:
- Source: PROD_CDB / PRODPDB
- Target: DEV_CDB / DEVPDB
- Authentication: External (both environments)
- Operations: Precheck → Clone → Postcheck
```

---

## Best Practices

1. **Use External Auth for**:
   - Regular operations
   - Production environments
   - Automated scripts
   - PDB clone operations

2. **Use Username/Password for**:
   - Ad-hoc health checks
   - Testing connectivity
   - Laptops without Oracle Client
   - Quick troubleshooting

3. **Security**:
   - Never store passwords in files
   - Use service accounts with minimum privileges
   - Rotate passwords regularly
   - Prefer external authentication for production

4. **Performance**:
   - External auth is faster (no credential validation)
   - Username/password works over WAN connections
   - Both modes generate identical health reports
