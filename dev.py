#!/usr/bin/env python3
"""Development utilities for MikroTik Traffic Counter"""
import sys
import os
import shutil
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))


def setup_demo_data():
    """Generate demo data"""
    from generate_demo import populate_database
    populate_database()


def run_server(host: str = "127.0.0.1", port: int = 8000, reload: bool = True):
    """Run development server"""
    import uvicorn
    os.chdir(str(backend_path))
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload
    )


def clean_project(remove_env: bool = False):
    """Clean project: remove database, cache files, and optionally virtual environment"""
    project_root = Path(__file__).parent
    items_to_remove = []
    
    # Database files
    db_folder = project_root / "db"
    if db_folder.exists():
        for db_file in db_folder.glob("*.db"):
            items_to_remove.append(db_file)
    
    # Cache and temporary files
    patterns = [
        "**/__pycache__",
        "**/*.pyc",
        "**/*.pyo",
        "**/*.pyd",
        "**/.pytest_cache",
        "**/.mypy_cache",
        "**/.coverage",
        "**/*.egg-info",
    ]
    
    for pattern in patterns:
        for item in project_root.glob(pattern):
            items_to_remove.append(item)
    
    # Virtual environment (optional)
    venv_folder = project_root / ".venv"
    if remove_env and venv_folder.exists():
        items_to_remove.append(venv_folder)
    
    # Remove duplicates
    items_to_remove = list(set(items_to_remove))
    
    if not items_to_remove:
        print("✅ Project is already clean!")
        return
    
    print(f"🧹 Cleaning {len(items_to_remove)} items...")
    
    for item in items_to_remove:
        try:
            if item.is_dir():
                shutil.rmtree(item)
                print(f"  ✓ Removed directory: {item.relative_to(project_root)}")
            else:
                item.unlink()
                print(f"  ✓ Removed file: {item.relative_to(project_root)}")
        except Exception as e:
            print(f"  ✗ Failed to remove {item}: {e}")
    
    print("\n✅ Cleanup complete!")
    if not remove_env:
        print("💡 Tip: Use 'python dev.py clean --env' to also remove the virtual environment")


def show_help():
    """Show help message"""
    print("""
MikroTik Traffic Counter - Development Utilities

Usage: python dev.py [command] [options]

Commands:
    demo         Generate demo data
    run          Run development server (port 8000)
    run:prod     Run production server
    clean        Remove database, cache files, and temporary data
    help         Show this help message

Options for clean:
    --env        Also remove the virtual environment

Examples:
    python dev.py demo              # Generate demo data
    python dev.py run               # Start dev server with auto-reload
    python dev.py run:prod          # Start prod server
    python dev.py clean             # Clean database and cache files
    python dev.py clean --env       # Clean everything including virtual environment
    """)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "demo":
        setup_demo_data()
    elif cmd == "run":
        run_server(reload=True)
    elif cmd == "run:prod":
        run_server(host="0.0.0.0", reload=False)
    elif cmd == "clean":
        remove_env = "--env" in sys.argv
        clean_project(remove_env=remove_env)
    elif cmd in ("help", "-h", "--help"):
        show_help()
    else:
        print(f"Unknown command: {cmd}")
        show_help()
        sys.exit(1)
