"""
Oracle PDB Management Toolkit - Main Entry Point
Version: 2.0.0

Main application entry point that:
- Initializes Oracle Client in Thick Mode
- Sets up signal handling for graceful shutdown
- Launches the PyQt6 GUI application

Requirements:
- Oracle Client libraries (Instant Client or Full Client)
- PyQt6
- oracledb (python-oracledb)

Usage:
    python main.py
"""

import sys
import signal
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from utils.helper_functions import init_oracle_client_thick_mode
from admin_toolbox_qt import OraclePDBToolkit


def signal_handler(sig, frame):
    """Handle Ctrl+C (SIGINT) gracefully"""
    print("\n[INFO] Shutdown signal received. Closing application gracefully...")
    QApplication.quit()


def main():
    """Main entry point for Oracle PDB Toolkit"""

    # Initialize Oracle Client in Thick Mode
    # CRITICAL: This must be called before any connection attempts
    print("=" * 80)
    print("Oracle PDB Management Toolkit - Version 2.0.0")
    print("=" * 80)
    print("\nInitializing Oracle Client in Thick Mode...")
    print("(Required for external authentication and database links)")
    print()

    success, message = init_oracle_client_thick_mode()

    if success:
        print(f"SUCCESS: {message}")
    else:
        print(f"WARNING: {message}")
        print()
        print("Thick mode is required for:")
        print("  - External authentication (OS authentication)")
        print("  - Database links (required for PDB cloning)")
        print("  - Advanced Oracle features")
        print()
        print("The application will continue, but some features may not work correctly.")
        print("Please ensure Oracle Client libraries are properly installed and accessible.")

    print()
    print("=" * 80)
    print("Starting GUI Application...")
    print("=" * 80)
    print()

    # Register signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    # Create Qt Application
    app = QApplication(sys.argv)

    # Create a QTimer that fires periodically to allow Python to process signals
    # This is necessary because Qt's event loop blocks Python's signal handling
    timer = QTimer()
    timer.start(500)  # Fire every 500ms
    timer.timeout.connect(lambda: None)  # No-op, just allows Python signal processing

    # Create and show main window
    window = OraclePDBToolkit()
    window.show()

    # Start event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
