"""
Oracle PDB Toolkit - Admin Toolbox GUI
Version: 2.0.0

PyQt6-based graphical interface for Oracle PDB management operations.
Provides tabs for:
- Database Health Check
- PDB Clone (Precheck, Clone, Postcheck)

Supports both external authentication and username/password connection modes.
"""

import sys
import traceback
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QLineEdit,
                             QTextEdit, QGroupBox, QMessageBox, QTabWidget,
                             QRadioButton, QButtonGroup)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

# Import modular functions
import db_healthcheck
import pdb_clone
from utils.report_generator import generate_health_report, generate_precheck_report, generate_postcheck_report


class DatabaseWorker(QThread):
    """Background worker thread for database operations"""
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(str)

    def __init__(self, operation, params):
        super().__init__()
        self.operation = operation
        self.params = params

    def run(self):
        try:
            if self.operation == "health_check":
                result = self.perform_health_check()
            elif self.operation == "pdb_precheck":
                result = self.perform_pdb_precheck()
            elif self.operation == "pdb_clone":
                result = self.perform_pdb_clone()
            elif self.operation == "pdb_postcheck":
                result = self.perform_pdb_postcheck()
            elif self.operation == "test_health_connection":
                result = self.test_health_connection()
            elif self.operation == "test_source_connection":
                result = self.test_clone_connection("source")
            elif self.operation == "test_target_connection":
                result = self.test_clone_connection("target")
            else:
                self.finished.emit(False, f"Unknown operation: {self.operation}")
                return

            self.finished.emit(True, result)

        except Exception as e:
            error_msg = f"Error: {str(e)}\n{traceback.format_exc()}"
            self.finished.emit(False, error_msg)

    def perform_health_check(self):
        """Generate database performance health HTML report"""
        # Perform health check using modular function
        health_data = db_healthcheck.perform_health_check(
            self.params,
            progress_callback=self.progress.emit
        )

        # Generate HTML report
        report_path = generate_health_report(health_data)
        self.progress.emit(f"Report generated: {report_path}")

        return f"Health check completed successfully.\nReport: {report_path}"

    def perform_pdb_precheck(self):
        """Perform PDB clone precheck validations"""
        # Perform precheck using modular function
        validation_results, source_data, target_data = pdb_clone.perform_pdb_precheck(
            self.params,
            progress_callback=self.progress.emit
        )

        # Generate HTML report
        report_path = generate_precheck_report(
            self.params['source_cdb'],
            self.params['source_pdb'],
            self.params['target_cdb'],
            self.params['target_pdb'],
            validation_results,
            source_data,
            target_data
        )

        self.progress.emit(f"Precheck report generated: {report_path}")

        all_passed = all(r['status'] == 'PASS' for r in validation_results if r['status'] != 'SKIPPED')
        status = "All checks PASSED" if all_passed else "Some checks FAILED"

        return f"PDB clone precheck completed.\nStatus: {status}\nReport: {report_path}"

    def perform_pdb_clone(self):
        """Execute PDB clone operation"""
        result = pdb_clone.perform_pdb_clone(
            self.params,
            progress_callback=self.progress.emit
        )

        return result

    def perform_pdb_postcheck(self):
        """Perform PDB clone postcheck validations"""
        # Perform postcheck using modular function
        validation_results, source_data, target_data, param_differences = pdb_clone.perform_pdb_postcheck(
            self.params,
            progress_callback=self.progress.emit
        )

        # Generate HTML report
        report_path = generate_postcheck_report(
            self.params['source_cdb'],
            self.params['source_pdb'],
            self.params['target_cdb'],
            self.params['target_pdb'],
            validation_results,
            source_data,
            target_data,
            param_differences
        )

        self.progress.emit(f"Postcheck report generated: {report_path}")

        all_passed = all(r['status'] == 'PASS' for r in validation_results)
        status = "All checks PASSED" if all_passed else "Some checks FAILED"

        return f"PDB clone postcheck completed.\nStatus: {status}\nReport: {report_path}"

    def test_health_connection(self):
        """Test database connection for health check"""
        import oracledb

        connection_mode = self.params.get('connection_mode')
        self.progress.emit("Testing database connection...")

        try:
            if connection_mode == 'external_auth':
                # Check if TNS alias or hostname/port/service
                if 'db_name' in self.params and not self.params.get('hostname'):
                    # TNS alias
                    dsn = self.params['db_name']
                    self.progress.emit(f"Connecting using TNS alias: {dsn} (External Auth)")
                    conn = oracledb.connect(dsn=dsn, externalauth=True)
                else:
                    # Hostname/port/service
                    hostname = self.params['hostname']
                    port = self.params['port']
                    service = self.params['service']
                    dsn = f"{hostname}:{port}/{service}"
                    self.progress.emit(f"Connecting to: {dsn} (External Auth)")
                    conn = oracledb.connect(dsn=dsn, externalauth=True)
            else:
                # Username/password
                hostname = self.params['hostname']
                port = self.params['port']
                service = self.params['service']
                username = self.params['username']
                password = self.params['password']
                dsn = f"{hostname}:{port}/{service}"
                self.progress.emit(f"Connecting to: {dsn} as {username}")
                conn = oracledb.connect(user=username, password=password, dsn=dsn)

            # Get connection info
            cursor = conn.cursor()

            # Get database name and version
            cursor.execute("SELECT name, version_full FROM v$database, v$instance")
            row = cursor.fetchone()
            db_name = row[0] if row else "Unknown"
            db_version = row[1] if row else "Unknown"

            # Get instance info
            cursor.execute("SELECT instance_name, host_name, status FROM v$instance")
            inst_row = cursor.fetchone()
            instance_name = inst_row[0] if inst_row else "Unknown"
            host_name = inst_row[1] if inst_row else "Unknown"
            status = inst_row[2] if inst_row else "Unknown"

            # Get current user
            cursor.execute("SELECT user FROM dual")
            current_user = cursor.fetchone()[0]

            cursor.close()
            conn.close()

            self.progress.emit(f"Connection successful!")
            self.progress.emit(f"  Database: {db_name}")
            self.progress.emit(f"  Version: {db_version}")
            self.progress.emit(f"  Instance: {instance_name}")
            self.progress.emit(f"  Host: {host_name}")
            self.progress.emit(f"  Status: {status}")
            self.progress.emit(f"  Connected as: {current_user}")

            return f"Connection successful!\n\nDatabase: {db_name}\nVersion: {db_version}\nInstance: {instance_name}\nHost: {host_name}\nStatus: {status}\nConnected as: {current_user}"

        except oracledb.Error as e:
            error_obj, = e.args
            self.progress.emit(f"Connection FAILED!")
            self.progress.emit(f"  Oracle Error Code: {error_obj.code}")
            self.progress.emit(f"  Error Message: {error_obj.message}")
            raise Exception(f"Oracle Error {error_obj.code}: {error_obj.message}")

    def test_clone_connection(self, target_type):
        """Test database connection for PDB clone (source or target)"""
        import oracledb

        connection_mode = self.params.get('connection_mode')

        if target_type == "source":
            scan = self.params['source_scan']
            port = self.params['source_port']
            cdb = self.params['source_cdb']
            username = self.params.get('source_username')
            password = self.params.get('source_password')
            label = "Source CDB"
        else:
            scan = self.params['target_scan']
            port = self.params['target_port']
            cdb = self.params['target_cdb']
            username = self.params.get('target_username')
            password = self.params.get('target_password')
            label = "Target CDB"

        dsn = f"{scan}:{port}/{cdb}"
        self.progress.emit(f"Testing {label} connection...")
        self.progress.emit(f"DSN: {dsn}")

        try:
            if connection_mode == 'external_auth':
                self.progress.emit(f"Connecting using External Authentication...")
                conn = oracledb.connect(dsn=dsn, externalauth=True)
            else:
                self.progress.emit(f"Connecting as user: {username}")
                conn = oracledb.connect(user=username, password=password, dsn=dsn)

            cursor = conn.cursor()

            # Get database name and version
            cursor.execute("SELECT name, version_full FROM v$database, v$instance")
            row = cursor.fetchone()
            db_name = row[0] if row else "Unknown"
            db_version = row[1] if row else "Unknown"

            # Get instance info
            cursor.execute("SELECT instance_name, host_name, status FROM v$instance")
            inst_row = cursor.fetchone()
            instance_name = inst_row[0] if inst_row else "Unknown"
            host_name = inst_row[1] if inst_row else "Unknown"
            status = inst_row[2] if inst_row else "Unknown"

            # Get current container
            cursor.execute("SELECT sys_context('USERENV', 'CON_NAME') FROM dual")
            container = cursor.fetchone()[0]

            # Get current user
            cursor.execute("SELECT user FROM dual")
            current_user = cursor.fetchone()[0]

            # Get PDB list
            cursor.execute("SELECT name, open_mode FROM v$pdbs ORDER BY con_id")
            pdbs = cursor.fetchall()

            cursor.close()
            conn.close()

            self.progress.emit(f"{label} connection successful!")
            self.progress.emit(f"  Database: {db_name}")
            self.progress.emit(f"  Version: {db_version}")
            self.progress.emit(f"  Instance: {instance_name}")
            self.progress.emit(f"  Host: {host_name}")
            self.progress.emit(f"  Status: {status}")
            self.progress.emit(f"  Container: {container}")
            self.progress.emit(f"  Connected as: {current_user}")
            self.progress.emit(f"  PDBs found: {len(pdbs)}")
            for pdb_name, pdb_mode in pdbs:
                self.progress.emit(f"    - {pdb_name}: {pdb_mode}")

            pdb_list = "\n".join([f"  - {p[0]}: {p[1]}" for p in pdbs])
            return f"{label} connection successful!\n\nDatabase: {db_name}\nVersion: {db_version}\nInstance: {instance_name}\nHost: {host_name}\nStatus: {status}\nContainer: {container}\nConnected as: {current_user}\n\nPDBs ({len(pdbs)}):\n{pdb_list}"

        except oracledb.Error as e:
            error_obj, = e.args
            self.progress.emit(f"{label} connection FAILED!")
            self.progress.emit(f"  Oracle Error Code: {error_obj.code}")
            self.progress.emit(f"  Error Message: {error_obj.message}")
            raise Exception(f"Oracle Error {error_obj.code}: {error_obj.message}")


class OraclePDBToolkit(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.worker = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Oracle PDB Management Toolkit")
        self.setGeometry(100, 100, 900, 700)

        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Title
        title = QLabel("Oracle DBA Admin Toolbox")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)

        # Tab widget for main menu
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab 1: DB Health Check
        self.health_tab = QWidget()
        self.setup_health_tab()
        self.tabs.addTab(self.health_tab, "DB Health Check")

        # Tab 2: PDB Clone
        self.clone_tab = QWidget()
        self.setup_clone_tab()
        self.tabs.addTab(self.clone_tab, "PDB Clone")

        # Output area
        output_group = QGroupBox("Output / Progress")
        output_layout = QVBoxLayout()
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        output_layout.addWidget(self.output_text)
        output_group.setLayout(output_layout)
        main_layout.addWidget(output_group)

        self.log("Oracle PDB Toolkit initialized successfully")
        self.log("Note: Supports both external authentication and username/password")

    def setup_health_tab(self):
        """Setup DB Health Check tab"""
        layout = QVBoxLayout(self.health_tab)

        # Connection method selection
        method_group = QGroupBox("Connection Method")
        method_layout = QVBoxLayout()

        self.health_conn_method = QButtonGroup()

        self.health_external_auth_radio = QRadioButton("External Authentication (OS Auth / Wallet)")
        self.health_external_auth_radio.setChecked(True)
        self.health_conn_method.addButton(self.health_external_auth_radio, 1)
        method_layout.addWidget(self.health_external_auth_radio)

        self.health_user_pass_radio = QRadioButton("Username / Password")
        self.health_conn_method.addButton(self.health_user_pass_radio, 2)
        method_layout.addWidget(self.health_user_pass_radio)

        method_group.setLayout(method_layout)
        layout.addWidget(method_group)

        # Connection configuration
        input_group = QGroupBox("Connection Configuration")
        input_layout = QVBoxLayout()

        # External Authentication fields (TNS or Hostname/Port)
        self.health_ext_auth_widget = QWidget()
        ext_auth_layout = QVBoxLayout(self.health_ext_auth_widget)
        ext_auth_layout.setContentsMargins(0, 0, 0, 0)

        # Option 1: TNS Alias
        tns_row = QHBoxLayout()
        tns_row.addWidget(QLabel("TNS Alias:"))
        self.health_ext_tns = QLineEdit()
        self.health_ext_tns.setPlaceholderText("e.g., ORCL or orcl_high (leave empty to use hostname/port)")
        tns_row.addWidget(self.health_ext_tns)
        ext_auth_layout.addLayout(tns_row)

        # Separator
        or_label = QLabel("— OR —")
        or_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        or_label.setStyleSheet("color: #666; font-style: italic; margin: 5px 0;")
        ext_auth_layout.addWidget(or_label)

        # Option 2: Hostname/Port/Service
        ext_host_row = QHBoxLayout()
        ext_host_row.addWidget(QLabel("Hostname:"))
        self.health_ext_hostname = QLineEdit()
        self.health_ext_hostname.setPlaceholderText("e.g., dbserver.example.com")
        ext_host_row.addWidget(self.health_ext_hostname)
        ext_auth_layout.addLayout(ext_host_row)

        ext_port_row = QHBoxLayout()
        ext_port_row.addWidget(QLabel("Port:"))
        self.health_ext_port = QLineEdit()
        self.health_ext_port.setPlaceholderText("1521")
        self.health_ext_port.setText("1521")
        self.health_ext_port.setMaximumWidth(100)
        ext_port_row.addWidget(self.health_ext_port)
        ext_port_row.addStretch()
        ext_auth_layout.addLayout(ext_port_row)

        ext_service_row = QHBoxLayout()
        ext_service_row.addWidget(QLabel("Service Name:"))
        self.health_ext_service = QLineEdit()
        self.health_ext_service.setPlaceholderText("e.g., ORCL or orcl_high")
        ext_service_row.addWidget(self.health_ext_service)
        ext_auth_layout.addLayout(ext_service_row)

        input_layout.addWidget(self.health_ext_auth_widget)

        # Hostname/Port/Service (for username/password)
        self.health_host_widget = QWidget()
        host_layout = QVBoxLayout(self.health_host_widget)
        host_layout.setContentsMargins(0, 0, 0, 0)

        host_row = QHBoxLayout()
        host_row.addWidget(QLabel("Hostname:"))
        self.health_hostname = QLineEdit()
        self.health_hostname.setPlaceholderText("e.g., dbserver.example.com")
        host_row.addWidget(self.health_hostname)
        host_layout.addLayout(host_row)

        port_row = QHBoxLayout()
        port_row.addWidget(QLabel("Port:"))
        self.health_port = QLineEdit()
        self.health_port.setPlaceholderText("1521")
        self.health_port.setText("1521")
        self.health_port.setMaximumWidth(100)
        port_row.addWidget(self.health_port)
        port_row.addStretch()
        host_layout.addLayout(port_row)

        service_row = QHBoxLayout()
        service_row.addWidget(QLabel("Service Name:"))
        self.health_service = QLineEdit()
        self.health_service.setPlaceholderText("e.g., ORCL or orcl_high")
        service_row.addWidget(self.health_service)
        host_layout.addLayout(service_row)

        user_row = QHBoxLayout()
        user_row.addWidget(QLabel("Username:"))
        self.health_username = QLineEdit()
        self.health_username.setPlaceholderText("e.g., system or admin")
        user_row.addWidget(self.health_username)
        host_layout.addLayout(user_row)

        pass_row = QHBoxLayout()
        pass_row.addWidget(QLabel("Password:"))
        self.health_password = QLineEdit()
        self.health_password.setPlaceholderText("Password")
        self.health_password.setEchoMode(QLineEdit.EchoMode.Password)
        pass_row.addWidget(self.health_password)
        host_layout.addLayout(pass_row)

        self.health_host_widget.setVisible(False)
        input_layout.addWidget(self.health_host_widget)

        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # Connect radio button signals
        self.health_external_auth_radio.toggled.connect(self.toggle_health_connection_fields)
        self.health_user_pass_radio.toggled.connect(self.toggle_health_connection_fields)

        # Action buttons
        button_layout = QHBoxLayout()

        # Test Connection button
        self.health_test_btn = QPushButton("Test Connection")
        self.health_test_btn.setStyleSheet("background-color: #6c757d; color: white; padding: 10px; font-weight: bold;")
        self.health_test_btn.clicked.connect(self.test_health_connection)
        button_layout.addWidget(self.health_test_btn)

        # Run button
        self.health_run_btn = QPushButton("Generate Health Report")
        self.health_run_btn.setStyleSheet("background-color: #0066cc; color: white; padding: 10px; font-weight: bold;")
        self.health_run_btn.clicked.connect(self.run_health_check)
        button_layout.addWidget(self.health_run_btn)

        layout.addLayout(button_layout)

        layout.addStretch()

    def toggle_health_connection_fields(self):
        """Toggle between external auth and username/password fields"""
        if self.health_external_auth_radio.isChecked():
            self.health_ext_auth_widget.setVisible(True)
            self.health_host_widget.setVisible(False)
        else:
            self.health_ext_auth_widget.setVisible(False)
            self.health_host_widget.setVisible(True)

    def toggle_clone_connection_fields(self):
        """Toggle between external auth and username/password fields for PDB Clone"""
        if self.clone_external_auth_radio.isChecked():
            self.source_credentials_widget.setVisible(False)
            self.target_credentials_widget.setVisible(False)
        else:
            self.source_credentials_widget.setVisible(True)
            self.target_credentials_widget.setVisible(True)

    def setup_clone_tab(self):
        """Setup PDB Clone tab"""
        layout = QVBoxLayout(self.clone_tab)

        # Connection method selection
        method_group = QGroupBox("Connection Method")
        method_layout = QVBoxLayout()

        self.clone_conn_method = QButtonGroup()

        self.clone_external_auth_radio = QRadioButton("External Authentication (OS Auth / Wallet)")
        self.clone_external_auth_radio.setChecked(True)
        self.clone_conn_method.addButton(self.clone_external_auth_radio, 1)
        method_layout.addWidget(self.clone_external_auth_radio)

        self.clone_user_pass_radio = QRadioButton("Username / Password")
        self.clone_conn_method.addButton(self.clone_user_pass_radio, 2)
        method_layout.addWidget(self.clone_user_pass_radio)

        method_group.setLayout(method_layout)
        layout.addWidget(method_group)

        # Input fields
        input_group = QGroupBox("PDB Clone Configuration")
        input_layout = QVBoxLayout()

        # Source configuration
        source_label = QLabel("Source Configuration")
        source_label.setStyleSheet("font-weight: bold; color: #0066cc;")
        input_layout.addWidget(source_label)

        source_host_layout = QHBoxLayout()
        source_host_layout.addWidget(QLabel("Source SCAN Host:"))
        self.source_scan = QLineEdit()
        self.source_scan.setPlaceholderText("e.g., prod-scan.example.com")
        source_host_layout.addWidget(self.source_scan)
        input_layout.addLayout(source_host_layout)

        source_port_layout = QHBoxLayout()
        source_port_layout.addWidget(QLabel("Port:"))
        self.source_port = QLineEdit()
        self.source_port.setPlaceholderText("1521")
        self.source_port.setText("1521")
        self.source_port.setMaximumWidth(100)
        source_port_layout.addWidget(self.source_port)
        source_port_layout.addStretch()
        input_layout.addLayout(source_port_layout)

        source_cdb_layout = QHBoxLayout()
        source_cdb_layout.addWidget(QLabel("Source CDB:"))
        self.source_cdb = QLineEdit()
        self.source_cdb.setPlaceholderText("Source CDB service name")
        source_cdb_layout.addWidget(self.source_cdb)
        input_layout.addLayout(source_cdb_layout)

        source_pdb_layout = QHBoxLayout()
        source_pdb_layout.addWidget(QLabel("Source PDB:"))
        self.source_pdb = QLineEdit()
        self.source_pdb.setPlaceholderText("Source PDB name/service (e.g., PRODPDB)")
        source_pdb_layout.addWidget(self.source_pdb)
        input_layout.addLayout(source_pdb_layout)

        # Credentials for username/password mode (source)
        self.source_credentials_widget = QWidget()
        source_cred_layout = QVBoxLayout(self.source_credentials_widget)
        source_cred_layout.setContentsMargins(0, 0, 0, 0)

        source_user_layout = QHBoxLayout()
        source_user_layout.addWidget(QLabel("Username:"))
        self.source_username = QLineEdit()
        self.source_username.setPlaceholderText("Source database username")
        source_user_layout.addWidget(self.source_username)
        source_cred_layout.addLayout(source_user_layout)

        source_pass_layout = QHBoxLayout()
        source_pass_layout.addWidget(QLabel("Password:"))
        self.source_password = QLineEdit()
        self.source_password.setPlaceholderText("Password")
        self.source_password.setEchoMode(QLineEdit.EchoMode.Password)
        source_pass_layout.addWidget(self.source_password)
        source_cred_layout.addLayout(source_pass_layout)

        self.source_credentials_widget.setVisible(False)
        input_layout.addWidget(self.source_credentials_widget)

        # Target configuration
        target_label = QLabel("Target Configuration")
        target_label.setStyleSheet("font-weight: bold; color: #0066cc; margin-top: 15px;")
        input_layout.addWidget(target_label)

        target_host_layout = QHBoxLayout()
        target_host_layout.addWidget(QLabel("Target SCAN Host:"))
        self.target_scan = QLineEdit()
        self.target_scan.setPlaceholderText("e.g., dev-scan.example.com")
        target_host_layout.addWidget(self.target_scan)
        input_layout.addLayout(target_host_layout)

        target_port_layout = QHBoxLayout()
        target_port_layout.addWidget(QLabel("Port:"))
        self.target_port = QLineEdit()
        self.target_port.setPlaceholderText("1521")
        self.target_port.setText("1521")
        self.target_port.setMaximumWidth(100)
        target_port_layout.addWidget(self.target_port)
        target_port_layout.addStretch()
        input_layout.addLayout(target_port_layout)

        target_cdb_layout = QHBoxLayout()
        target_cdb_layout.addWidget(QLabel("Target CDB:"))
        self.target_cdb = QLineEdit()
        self.target_cdb.setPlaceholderText("Target CDB service name")
        target_cdb_layout.addWidget(self.target_cdb)
        input_layout.addLayout(target_cdb_layout)

        target_pdb_layout = QHBoxLayout()
        target_pdb_layout.addWidget(QLabel("Target PDB:"))
        self.target_pdb = QLineEdit()
        self.target_pdb.setPlaceholderText("New PDB name/service (e.g., DEVPDB)")
        target_pdb_layout.addWidget(self.target_pdb)
        input_layout.addLayout(target_pdb_layout)

        # Credentials for username/password mode (target)
        self.target_credentials_widget = QWidget()
        target_cred_layout = QVBoxLayout(self.target_credentials_widget)
        target_cred_layout.setContentsMargins(0, 0, 0, 0)

        target_user_layout = QHBoxLayout()
        target_user_layout.addWidget(QLabel("Username:"))
        self.target_username = QLineEdit()
        self.target_username.setPlaceholderText("Target database username")
        target_user_layout.addWidget(self.target_username)
        target_cred_layout.addLayout(target_user_layout)

        target_pass_layout = QHBoxLayout()
        target_pass_layout.addWidget(QLabel("Password:"))
        self.target_password = QLineEdit()
        self.target_password.setPlaceholderText("Password")
        self.target_password.setEchoMode(QLineEdit.EchoMode.Password)
        target_pass_layout.addWidget(self.target_password)
        target_cred_layout.addLayout(target_pass_layout)

        self.target_credentials_widget.setVisible(False)
        input_layout.addWidget(self.target_credentials_widget)

        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # Connect radio button signals
        self.clone_external_auth_radio.toggled.connect(self.toggle_clone_connection_fields)
        self.clone_user_pass_radio.toggled.connect(self.toggle_clone_connection_fields)

        # Connection test buttons
        test_button_layout = QHBoxLayout()

        self.test_source_btn = QPushButton("Test Source Connection")
        self.test_source_btn.setStyleSheet("background-color: #6c757d; color: white; padding: 8px; font-weight: bold;")
        self.test_source_btn.clicked.connect(self.test_source_connection)
        test_button_layout.addWidget(self.test_source_btn)

        self.test_target_btn = QPushButton("Test Target Connection")
        self.test_target_btn.setStyleSheet("background-color: #6c757d; color: white; padding: 8px; font-weight: bold;")
        self.test_target_btn.clicked.connect(self.test_target_connection)
        test_button_layout.addWidget(self.test_target_btn)

        layout.addLayout(test_button_layout)

        # Action buttons
        button_layout = QHBoxLayout()

        self.precheck_btn = QPushButton("Run Precheck")
        self.precheck_btn.setStyleSheet("background-color: #28a745; color: white; padding: 10px; font-weight: bold;")
        self.precheck_btn.clicked.connect(self.run_precheck)
        button_layout.addWidget(self.precheck_btn)

        self.clone_btn = QPushButton("Execute PDB Clone")
        self.clone_btn.setStyleSheet("background-color: #ffc107; color: black; padding: 10px; font-weight: bold;")
        self.clone_btn.clicked.connect(self.run_clone)
        button_layout.addWidget(self.clone_btn)

        self.postcheck_btn = QPushButton("Run Postcheck")
        self.postcheck_btn.setStyleSheet("background-color: #17a2b8; color: white; padding: 10px; font-weight: bold;")
        self.postcheck_btn.clicked.connect(self.run_postcheck)
        button_layout.addWidget(self.postcheck_btn)

        layout.addLayout(button_layout)
        layout.addStretch()

    def log(self, message):
        """Add message to output area"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.output_text.append(f"[{timestamp}] {message}")
        QApplication.processEvents()

    def disable_buttons(self):
        """Disable all action buttons during operations"""
        self.health_test_btn.setEnabled(False)
        self.health_run_btn.setEnabled(False)
        self.test_source_btn.setEnabled(False)
        self.test_target_btn.setEnabled(False)
        self.precheck_btn.setEnabled(False)
        self.clone_btn.setEnabled(False)
        self.postcheck_btn.setEnabled(False)

    def enable_buttons(self):
        """Enable all action buttons after operations"""
        self.health_test_btn.setEnabled(True)
        self.health_run_btn.setEnabled(True)
        self.test_source_btn.setEnabled(True)
        self.test_target_btn.setEnabled(True)
        self.precheck_btn.setEnabled(True)
        self.clone_btn.setEnabled(True)
        self.postcheck_btn.setEnabled(True)

    def run_health_check(self):
        """Run database health check"""
        params = {}

        if self.health_external_auth_radio.isChecked():
            # External authentication mode
            tns_alias = self.health_ext_tns.text().strip()
            hostname = self.health_ext_hostname.text().strip()
            port = self.health_ext_port.text().strip()
            service = self.health_ext_service.text().strip()

            params['connection_mode'] = 'external_auth'

            # Check if TNS alias is provided
            if tns_alias:
                params['db_name'] = tns_alias
                self.log(f"Starting health check for database: {tns_alias} (External Auth - TNS)")
            elif hostname and port and service:
                # Use hostname/port/service
                params['hostname'] = hostname
                params['port'] = port
                params['service'] = service
                params['db_name'] = f"{hostname}:{port}/{service}"
                self.log(f"Starting health check for {service} at {hostname}:{port} (External Auth - Direct)")
            else:
                QMessageBox.warning(self, "Input Required",
                                  "Please provide either:\n"
                                  "- TNS Alias, OR\n"
                                  "- Hostname + Port + Service Name")
                return

        else:
            # Username/password mode
            hostname = self.health_hostname.text().strip()
            port = self.health_port.text().strip()
            service = self.health_service.text().strip()
            username = self.health_username.text().strip()
            password = self.health_password.text().strip()

            if not all([hostname, port, service, username, password]):
                QMessageBox.warning(self, "Input Required",
                                  "Please provide all connection details:\n"
                                  "- Hostname\n- Port\n- Service Name\n- Username\n- Password")
                return

            params['connection_mode'] = 'user_pass'
            params['hostname'] = hostname
            params['port'] = port
            params['service'] = service
            params['username'] = username
            params['password'] = password
            self.log(f"Starting health check for {service} at {hostname}:{port} (User: {username})")

        self.disable_buttons()

        self.worker = DatabaseWorker("health_check", params)
        self.worker.progress.connect(self.log)
        self.worker.finished.connect(self.on_operation_finished)
        self.worker.start()

    def test_health_connection(self):
        """Test database connection for health check"""
        params = {}

        if self.health_external_auth_radio.isChecked():
            # External authentication mode
            tns_alias = self.health_ext_tns.text().strip()
            hostname = self.health_ext_hostname.text().strip()
            port = self.health_ext_port.text().strip()
            service = self.health_ext_service.text().strip()

            params['connection_mode'] = 'external_auth'

            # Check if TNS alias is provided
            if tns_alias:
                params['db_name'] = tns_alias
                self.log(f"Testing connection to: {tns_alias} (External Auth - TNS)")
            elif hostname and port and service:
                # Use hostname/port/service
                params['hostname'] = hostname
                params['port'] = port
                params['service'] = service
                params['db_name'] = f"{hostname}:{port}/{service}"
                self.log(f"Testing connection to: {service} at {hostname}:{port} (External Auth)")
            else:
                QMessageBox.warning(self, "Input Required",
                                  "Please provide either:\n"
                                  "- TNS Alias, OR\n"
                                  "- Hostname + Port + Service Name")
                return

        else:
            # Username/password mode
            hostname = self.health_hostname.text().strip()
            port = self.health_port.text().strip()
            service = self.health_service.text().strip()
            username = self.health_username.text().strip()
            password = self.health_password.text().strip()

            if not all([hostname, port, service, username, password]):
                QMessageBox.warning(self, "Input Required",
                                  "Please provide all connection details:\n"
                                  "- Hostname\n- Port\n- Service Name\n- Username\n- Password")
                return

            params['connection_mode'] = 'user_pass'
            params['hostname'] = hostname
            params['port'] = port
            params['service'] = service
            params['username'] = username
            params['password'] = password
            self.log(f"Testing connection to: {service} at {hostname}:{port} (User: {username})")

        self.disable_buttons()

        self.worker = DatabaseWorker("test_health_connection", params)
        self.worker.progress.connect(self.log)
        self.worker.finished.connect(self.on_operation_finished)
        self.worker.start()

    def test_source_connection(self):
        """Test source database connection for PDB clone"""
        source_scan = self.source_scan.text().strip()
        source_port = self.source_port.text().strip()
        source_cdb = self.source_cdb.text().strip()

        if not all([source_scan, source_port, source_cdb]):
            QMessageBox.warning(self, "Input Required",
                              "Please provide source connection details:\n"
                              "- Source SCAN Host\n- Port\n- Source CDB")
            return

        params = {
            'connection_mode': 'external_auth' if self.clone_external_auth_radio.isChecked() else 'user_pass',
            'source_scan': source_scan,
            'source_port': source_port,
            'source_cdb': source_cdb
        }

        # Add credentials if username/password mode
        if self.clone_user_pass_radio.isChecked():
            source_user = self.source_username.text().strip()
            source_pass = self.source_password.text().strip()

            if not all([source_user, source_pass]):
                QMessageBox.warning(self, "Credentials Required",
                                  "Please provide source database username and password")
                return

            params['source_username'] = source_user
            params['source_password'] = source_pass

        self.log(f"Testing source connection to: {source_scan}:{source_port}/{source_cdb}")
        self.disable_buttons()

        self.worker = DatabaseWorker("test_source_connection", params)
        self.worker.progress.connect(self.log)
        self.worker.finished.connect(self.on_operation_finished)
        self.worker.start()

    def test_target_connection(self):
        """Test target database connection for PDB clone"""
        target_scan = self.target_scan.text().strip()
        target_port = self.target_port.text().strip()
        target_cdb = self.target_cdb.text().strip()

        if not all([target_scan, target_port, target_cdb]):
            QMessageBox.warning(self, "Input Required",
                              "Please provide target connection details:\n"
                              "- Target SCAN Host\n- Port\n- Target CDB")
            return

        params = {
            'connection_mode': 'external_auth' if self.clone_external_auth_radio.isChecked() else 'user_pass',
            'target_scan': target_scan,
            'target_port': target_port,
            'target_cdb': target_cdb
        }

        # Add credentials if username/password mode
        if self.clone_user_pass_radio.isChecked():
            target_user = self.target_username.text().strip()
            target_pass = self.target_password.text().strip()

            if not all([target_user, target_pass]):
                QMessageBox.warning(self, "Credentials Required",
                                  "Please provide target database username and password")
                return

            params['target_username'] = target_user
            params['target_password'] = target_pass

        self.log(f"Testing target connection to: {target_scan}:{target_port}/{target_cdb}")
        self.disable_buttons()

        self.worker = DatabaseWorker("test_target_connection", params)
        self.worker.progress.connect(self.log)
        self.worker.finished.connect(self.on_operation_finished)
        self.worker.start()

    def run_precheck(self):
        """Run PDB clone precheck"""
        source_scan = self.source_scan.text().strip()
        source_port = self.source_port.text().strip()
        source_cdb = self.source_cdb.text().strip()
        source_pdb = self.source_pdb.text().strip()
        target_scan = self.target_scan.text().strip()
        target_port = self.target_port.text().strip()
        target_cdb = self.target_cdb.text().strip()
        target_pdb = self.target_pdb.text().strip()

        # Validate required fields
        if not all([source_scan, source_port, source_cdb, source_pdb, target_scan, target_port, target_cdb, target_pdb]):
            QMessageBox.warning(self, "Input Required",
                              "Please provide all required fields:\n"
                              "- Source and Target SCAN hosts\n"
                              "- Ports\n"
                              "- CDB and PDB names")
            return

        params = {
            'connection_mode': 'external_auth' if self.clone_external_auth_radio.isChecked() else 'user_pass',
            'source_scan': source_scan,
            'source_port': source_port,
            'source_cdb': source_cdb,
            'source_pdb': source_pdb,
            'target_scan': target_scan,
            'target_port': target_port,
            'target_cdb': target_cdb,
            'target_pdb': target_pdb
        }

        # Add credentials if username/password mode
        if self.clone_user_pass_radio.isChecked():
            source_user = self.source_username.text().strip()
            source_pass = self.source_password.text().strip()
            target_user = self.target_username.text().strip()
            target_pass = self.target_password.text().strip()

            if not all([source_user, source_pass, target_user, target_pass]):
                QMessageBox.warning(self, "Credentials Required",
                                  "Please provide username and password for both source and target databases")
                return

            params['source_username'] = source_user
            params['source_password'] = source_pass
            params['target_username'] = target_user
            params['target_password'] = target_pass

        self.log("Starting PDB clone precheck...")
        self.disable_buttons()

        self.worker = DatabaseWorker("pdb_precheck", params)
        self.worker.progress.connect(self.log)
        self.worker.finished.connect(self.on_operation_finished)
        self.worker.start()

    def run_clone(self):
        """Execute PDB clone"""
        source_scan = self.source_scan.text().strip()
        source_port = self.source_port.text().strip()
        source_cdb = self.source_cdb.text().strip()
        source_pdb = self.source_pdb.text().strip()
        target_scan = self.target_scan.text().strip()
        target_port = self.target_port.text().strip()
        target_cdb = self.target_cdb.text().strip()
        target_pdb = self.target_pdb.text().strip()

        if not all([source_scan, source_port, source_cdb, source_pdb, target_scan, target_port, target_cdb, target_pdb]):
            QMessageBox.warning(self, "Input Required",
                              "Please provide all required fields")
            return

        # Confirmation dialog
        reply = QMessageBox.question(self, 'Confirm Clone Operation',
                                    f"Are you sure you want to clone:\n\n"
                                    f"Source: {source_pdb}@{source_scan}:{source_port}/{source_cdb}\n"
                                    f"Target: {target_pdb}@{target_scan}:{target_port}/{target_cdb}\n\n"
                                    f"This operation will create a new PDB.",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.No:
            return

        params = {
            'connection_mode': 'external_auth' if self.clone_external_auth_radio.isChecked() else 'user_pass',
            'source_scan': source_scan,
            'source_port': source_port,
            'source_cdb': source_cdb,
            'source_pdb': source_pdb,
            'target_scan': target_scan,
            'target_port': target_port,
            'target_cdb': target_cdb,
            'target_pdb': target_pdb
        }

        # Add credentials if username/password mode
        if self.clone_user_pass_radio.isChecked():
            source_user = self.source_username.text().strip()
            source_pass = self.source_password.text().strip()
            target_user = self.target_username.text().strip()
            target_pass = self.target_password.text().strip()

            if not all([source_user, source_pass, target_user, target_pass]):
                QMessageBox.warning(self, "Credentials Required",
                                  "Please provide username and password for both source and target databases")
                return

            params['source_username'] = source_user
            params['source_password'] = source_pass
            params['target_username'] = target_user
            params['target_password'] = target_pass

        self.log("Starting PDB clone operation...")
        self.disable_buttons()

        self.worker = DatabaseWorker("pdb_clone", params)
        self.worker.progress.connect(self.log)
        self.worker.finished.connect(self.on_operation_finished)
        self.worker.start()

    def run_postcheck(self):
        """Run PDB clone postcheck"""
        source_scan = self.source_scan.text().strip()
        source_port = self.source_port.text().strip()
        source_cdb = self.source_cdb.text().strip()
        source_pdb = self.source_pdb.text().strip()
        target_scan = self.target_scan.text().strip()
        target_port = self.target_port.text().strip()
        target_cdb = self.target_cdb.text().strip()
        target_pdb = self.target_pdb.text().strip()

        if not all([source_scan, source_port, source_cdb, source_pdb, target_scan, target_port, target_cdb, target_pdb]):
            QMessageBox.warning(self, "Input Required",
                              "Please provide all required fields")
            return

        params = {
            'connection_mode': 'external_auth' if self.clone_external_auth_radio.isChecked() else 'user_pass',
            'source_scan': source_scan,
            'source_port': source_port,
            'source_cdb': source_cdb,
            'source_pdb': source_pdb,
            'target_scan': target_scan,
            'target_port': target_port,
            'target_cdb': target_cdb,
            'target_pdb': target_pdb
        }

        # Add credentials if username/password mode
        if self.clone_user_pass_radio.isChecked():
            source_user = self.source_username.text().strip()
            source_pass = self.source_password.text().strip()
            target_user = self.target_username.text().strip()
            target_pass = self.target_password.text().strip()

            if not all([source_user, source_pass, target_user, target_pass]):
                QMessageBox.warning(self, "Credentials Required",
                                  "Please provide username and password for both source and target databases")
                return

            params['source_username'] = source_user
            params['source_password'] = source_pass
            params['target_username'] = target_user
            params['target_password'] = target_pass

        self.log("Starting PDB clone postcheck...")
        self.disable_buttons()

        self.worker = DatabaseWorker("pdb_postcheck", params)
        self.worker.progress.connect(self.log)
        self.worker.finished.connect(self.on_operation_finished)
        self.worker.start()

    def on_operation_finished(self, success, message):
        """Handle operation completion"""
        self.enable_buttons()

        if success:
            self.log(f"SUCCESS: {message}")
            QMessageBox.information(self, "Operation Complete", message)
        else:
            self.log(f"ERROR: {message}")
            QMessageBox.critical(self, "Operation Failed", message)
