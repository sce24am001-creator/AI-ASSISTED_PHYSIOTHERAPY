"""
Master Application Launcher: AI-Assisted Physiotherapy Platform.

Runs pre-flight environment checks, initializes and seeds SQLite database if needed,
and launches the local Flask web server.
"""

import os
import sys

# Ensure project root in sys.path
PROJECT_DIR = os.path.abspath(os.path.dirname(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from database.db import DEFAULT_DB_PATH
from database.seed import seed_database
from backend.app import create_app


def main():
    print("=" * 70)
    print("   AI-ASSISTED PHYSIOTHERAPY REHABILITATION PLATFORM")
    print("   Hand & Wrist Clinical Movement Analysis & Guidance")
    print("=" * 70)

    # 1. Database check & auto-seeding
    db_path = DEFAULT_DB_PATH
    if not os.path.exists(db_path):
        print("\n[INIT] Initializing and seeding database...")
        seed_database(db_path)
    else:
        print(f"\n[OK] Database active at: {db_path}")

    # 2. Display Demo Credentials
    print("\n" + "-" * 70)
    print("DEMO CREDENTIALS FOR UNIVERSITY EVALUATION:")
    print("  [*] Clinician Portal : Username: dr_sarah   | Password: physio123")
    print("  [*] Patient Portal   : Username: john_doe   | Password: patient123")
    print("-" * 70)
    print("\nStarting local Flask server at http://127.0.0.1:5000 ...")
    print("Open http://127.0.0.1:5000 in your browser.")
    print("Press Ctrl+C to stop the server.\n")

    app = create_app(db_path=db_path)
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
