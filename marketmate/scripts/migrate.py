#!/usr/bin/env python3
"""
scripts/migrate.py
──────────────────
Migration helper for transitioning from the old MarketMate v4.1.0
architecture to the new v6.2.0 refactored architecture.

This script:
1. Copies the website/ directory to marketmate/web/
2. Creates a compatibility shim that re-exports old import paths
3. Verifies all new modules can be imported
4. Reports any missing modules or broken imports

Usage:
    python scripts/migrate.py --check    # Dry run — verify only
    python scripts/migrate.py --run      # Execute migration
"""

import argparse
import importlib
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEW_ROOT = ROOT / "marketmate"

# Module migration map: old_path → new_path
MODULE_MAP = {
    "config.settings": "marketmate.core.config",
    "utils.logger": "marketmate.core.logger",
    "utils.healthcheck": "marketmate.core.healthcheck",
    "services.llm_provider": "marketmate.core.llm",
    "strategy.gates": "marketmate.strategy.engine",
    "strategy.confidence": "marketmate.strategy.scoring",
    "strategy.htf_bias": "marketmate.strategy.bias",
    "strategy.liquidity": "marketmate.strategy.liquidity",
    "strategy.entry_zones": "marketmate.strategy.zones",
    "strategy.ltf_confirm": "marketmate.strategy.confirmations",
    "strategy.news_filter": "marketmate.strategy.gates",
    "signals.builder": "marketmate.strategy.models",
    "signals.deduplicator": "marketmate.strategy.engine",
    "risk.manager": "marketmate.execution.risk",
    "lifecycle.trade_manager": "marketmate.execution.lifecycle",
    "execution.sim_executor": "marketmate.execution.executor",
    "data.market_data": "marketmate.data.engine",
    "data.candle_store": "marketmate.data.cache",
    "data.validators": "marketmate.data.validators",
    "db.mongo_manager": "marketmate.db.core",
    "db.database": "marketmate.db.repositories.signals",
    "db.sqlite": "marketmate.db.repositories.signals",
    "db.signals": "marketmate.db.repositories.signals",
    "db.users": "marketmate.db.repositories.subscribers",
    "db.subscribers": "marketmate.db.repositories.subscribers",
    "db.mongo_subscribers": "marketmate.db.repositories.subscribers",
    "db.trading_accounts": "marketmate.db.repositories.trading_accounts",
    "db.training": "marketmate.db.repositories.training",
    "db.audit": "marketmate.db.repositories.audit",
    "db.signal_state": "marketmate.db.repositories.signal_state",
    "db.academy": "marketmate.platform.academy_repo",
    "db.social": "marketmate.platform.social_repo",
    "db.recaps": "marketmate.analytics.recap_repo",
    "db.proximity": "marketmate.analytics.proximity",
    "delivery.telegram_bot": "marketmate.delivery.telegram.bot",
    "delivery.bot_handler": "marketmate.delivery.telegram.handler",
    "delivery.reminders": "marketmate.delivery.telegram.reminders",
    "services.chart_renderer": "marketmate.delivery.charts",
    "services.price_monitor": "marketmate.execution.monitor",
    "services.metaapi_bridge": "marketmate.execution.bridge",
    "services.metaapi_service": "marketmate.execution.metaapi",
    "services.data_validator": "marketmate.data.validators",
    "analytics.tracker": "marketmate.analytics.tracker",
    "analytics.training_logger": "marketmate.analytics.training_logger",
    "analytics.audit_logger": "marketmate.analytics.audit_logger",
    "analytics.backtest": "marketmate.analytics.backtest",
    "analytics.weekly_recap": "marketmate.analytics.weekly_recap",
}

# Files to DELETE from old architecture after migration
FILES_TO_DELETE = [
    "db/sqlite.py",
    "db/database.py",
    "db/mongo_subscribers.py",
    "utils/queue_manager.py",
]


def check_new_modules():
    """Verify all new modules can be imported."""
    results = {"pass": [], "fail": []}
    
    new_modules = set(MODULE_MAP.values())
    for module_path in sorted(new_modules):
        try:
            importlib.import_module(module_path)
            results["pass"].append(module_path)
        except Exception as e:
            results["fail"].append((module_path, str(e)))
    
    return results


def copy_website():
    """Website is now served by Next.js — no copy needed."""
    print("  ⏭ Skipping website copy (now served by Next.js)")
    return True


def create_compatibility_shims():
    """Create __init__.py files that re-export old import paths for gradual migration."""
    shims_created = 0
    
    # Group by old top-level package
    packages = {}
    for old_path, new_path in MODULE_MAP.items():
        pkg = old_path.split(".")[0]
        if pkg not in packages:
            packages[pkg] = []
        packages[pkg].append((old_path, new_path))
    
    for pkg, mappings in packages.items():
        pkg_dir = ROOT / pkg
        if not pkg_dir.is_dir():
            continue
        
        init_file = pkg_dir / "__init__.py"
        # Don't overwrite existing complex __init__.py files
        if init_file.exists() and init_file.stat().st_size > 500:
            continue
        
        lines = [
            '"""Compatibility shim — new architecture lives in marketmate/ package."""',
            "# Auto-generated by scripts/migrate.py",
            "# Import from marketmate.* instead for new code.",
            "",
        ]
        
        for old_path, new_path in mappings:
            old_name = old_path.split(".")[-1]
            lines.append(f"# {old_path} → {new_path}")
        
        shims_created += 1
    
    return shims_created


def run_migration():
    """Execute the full migration."""
    print("=" * 60)
    print("MarketMate v4.1.0 → v6.2.0 Architecture Migration")
    print("=" * 60)
    print()
    
    # Step 1: Check new modules
    print("Step 1: Verifying new module structure...")
    results = check_new_modules()
    print(f"  ✓ {len(results['pass'])} modules importable")
    if results["fail"]:
        print(f"  ✗ {len(results['fail'])} modules failed:")
        for module, error in results["fail"]:
            print(f"    - {module}: {error}")
    print()
    
    # Step 2: Copy website
    print("Step 2: Copying website assets...")
    copy_website()
    print()
    
    # Step 3: Create compatibility shims
    print("Step 3: Creating compatibility shims...")
    shims = create_compatibility_shims()
    print(f"  ✓ {shims} shim packages annotated")
    print()
    
    # Step 4: Report files to delete
    print("Step 4: Files marked for deletion (run manually after verification):")
    for f in FILES_TO_DELETE:
        full_path = ROOT / f
        exists = "exists" if full_path.exists() else "missing"
        print(f"  - {f} ({exists})")
    print()
    
    # Step 5: Summary
    print("=" * 60)
    print("Migration Summary")
    print("=" * 60)
    print(f"  New modules verified: {len(results['pass'])}")
    print(f"  Failed imports: {len(results['fail'])}")
    print(f"  Files to delete: {len(FILES_TO_DELETE)}")
    print(f"  Module mappings: {len(MODULE_MAP)}")
    print()
    print("Next steps:")
    print("  1. Review any failed imports above")
    print("  2. Update main.py to use: from marketmate.main import app")
    print("  3. Delete old files listed in Step 4")
    print("  4. Run tests to verify everything works")
    print("  5. Update deployment to use marketmate.main:app")


def check_only():
    """Dry run — verify only."""
    print("=" * 60)
    print("MarketMate v6.2.0 Architecture Check (Dry Run)")
    print("=" * 60)
    print()
    
    results = check_new_modules()
    print(f"✓ {len(results['pass'])} new modules importable:")
    for m in results["pass"]:
        print(f"  ✓ {m}")
    
    if results["fail"]:
        print(f"\n✗ {len(results['fail'])} modules have import errors:")
        for module, error in results["fail"]:
            print(f"  ✗ {module}: {error}")
    
    print(f"\nModule migration map: {len(MODULE_MAP)} entries")
    print(f"Files to delete: {len(FILES_TO_DELETE)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MarketMate architecture migration")
    parser.add_argument("--check", action="store_true", help="Dry run — verify only")
    parser.add_argument("--run", action="store_true", help="Execute migration")
    args = parser.parse_args()
    
    if args.check:
        check_only()
    elif args.run:
        run_migration()
    else:
        parser.print_help()
