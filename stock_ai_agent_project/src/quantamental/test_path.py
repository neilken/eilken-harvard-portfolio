# test_path.py
import os
from pathlib import Path

# See where you are
print(f"Current directory: {os.getcwd()}")

# See where config.yaml is
config_path = Path(__file__).parent / "config.yaml"
print(f"Config location: {config_path}")

# Try different relative paths
paths_to_try = [
    "../secrets/stock-busters-service-account.json",
    "../../secrets/stock-busters-service-account.json",
    "../../../secrets/stock-busters-service-account.json",
]

for path in paths_to_try:
    full_path = Path(__file__).parent / path
    if full_path.exists():
        print(f"✅ FOUND: {path}")
        print(f"   Absolute: {full_path.resolve()}")
    else:
        print(f"❌ NOT FOUND: {path}")
