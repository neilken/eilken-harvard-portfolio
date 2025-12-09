"""
Setup Verification Script
Verifies all components are ready for MS4
"""

import sys
from pathlib import Path
import importlib.util

# ANSI color codes for pretty output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_header(text):
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{text.center(60)}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")


def check_mark(passed):
    return f"{GREEN}✅{RESET}" if passed else f"{RED}❌{RESET}"


def check_python_version():
    """Check Python version >= 3.8"""
    print_header("PYTHON VERSION CHECK")
    version = sys.version_info
    passed = version.major == 3 and version.minor >= 8
    print(
        f"{check_mark(passed)} Python version: {version.major}.{version.minor}.{version.micro}"
    )
    if not passed:
        print(f"   {RED}Required: Python 3.8 or higher{RESET}")
    return passed


def check_dependencies():
    """Check required Python packages"""
    print_header("DEPENDENCY CHECK")

    required_packages = {
        "pandas": "pandas",
        "numpy": "numpy",
        "sklearn": "scikit-learn",
        "wandb": "wandb",
        "yaml": "pyyaml",
        "google.cloud.storage": "google-cloud-storage (optional)",
        "aiohttp": "aiohttp",
        "requests": "requests",
        "matplotlib": "matplotlib",
        "seaborn": "seaborn",
        "pytest": "pytest",
    }

    all_passed = True
    for module_name, package_name in required_packages.items():
        try:
            if module_name == "sklearn":
                import sklearn

                version = sklearn.__version__
            elif module_name == "yaml":
                import yaml

                version = yaml.__version__
            elif module_name == "google.cloud.storage":
                version = "installed"
            else:
                mod = importlib.import_module(module_name)
                version = getattr(mod, "__version__", "unknown")

            print(f"{check_mark(True)} {package_name}: {version}")
        except ImportError:
            optional = "(optional)" in package_name
            print(f"{check_mark(optional)} {package_name}: NOT INSTALLED")
            if not optional:
                all_passed = False

    return all_passed


def check_project_structure():
    """Check essential files exist"""
    print_header("PROJECT STRUCTURE CHECK")

    essential_files = [
        # Core Python files
        ("main.py", "Main pipeline script"),
        ("utils.py", "Utility functions"),
        ("data_collect.py", "Data collection module"),
        ("data_process.py", "Data processing module"),
        ("model_train.py", "Model training module"),
        ("model_predict.py", "Model prediction module"),
        ("backtest.py", "Backtesting module"),
        ("data_versioning.py", "Data versioning module (MS4)"),  # NEW
        # Configuration
        ("config.yaml", "Configuration file"),
        ("requirements.txt", "Python dependencies"),
        ("Dockerfile", "Docker configuration"),
        # Testing
        ("pytest.ini", "Pytest configuration"),
        ("tests/test_unit_data_process.py", "Unit tests"),
        ("tests/test_integration_pipeline.py", "Integration tests"),
        # CI/CD
        (".github/workflows/ci.yml", "GitHub Actions CI/CD"),
        (".gitignore", "Git ignore rules"),
        # Documentation
        ("README.md", "Project documentation"),
    ]

    all_passed = True
    for filepath, description in essential_files:
        exists = Path(filepath).exists()
        print(f"{check_mark(exists)} {filepath:<40} {description}")
        if not exists:
            all_passed = False

    return all_passed


def check_data_files():
    """Check data files exist"""
    print_header("DATA FILES CHECK")

    data_files = [
        ("data/ohlcv_raw.parquet", "Raw OHLCV data", False),
        ("data/sp500_index.parquet", "S&P 500 index data", False),
        ("data/fundamentals_combined.parquet", "Fundamentals data", True),
        ("data/quantamental_monthly.parquet", "Processed features", True),
    ]

    any_exist = False
    for filepath, description, optional in data_files:
        exists = Path(filepath).exists()
        if exists:
            size_mb = Path(filepath).stat().st_size / 1024 / 1024
            print(f"{check_mark(True)} {filepath:<45} {description} ({size_mb:.1f} MB)")
            any_exist = True
        else:
            status = "optional" if optional else "required"
            print(f"{check_mark(optional)} {filepath:<45} {description} ({status})")

    if not any_exist:
        print(
            f"\n{YELLOW}  No data files found. Run data collection first:{RESET}"
        )  # noqa: F541
        print(f"   python main.py --step collect")

    return any_exist


def check_configuration():
    """Check configuration is valid"""
    print_header("CONFIGURATION CHECK")

    try:
        from utils import load_config

        config = load_config()

        required_sections = ["data", "features", "model", "wandb", "gcs"]
        all_passed = True

        for section in required_sections:
            exists = section in config
            print(f"{check_mark(exists)} Config section: {section}")
            if not exists:
                all_passed = False

        # Check W&B project
        if "wandb" in config and "project" in config["wandb"]:
            print(f"{check_mark(True)} W&B project: {config['wandb']['project']}")
        else:
            print(f"{check_mark(False)} W&B project not configured")
            all_passed = False

        return all_passed

    except Exception as e:
        print(f"{check_mark(False)} Configuration error: {e}")
        return False


def check_wandb_setup():
    """Check W&B is configured"""
    print_header("WEIGHTS & BIASES CHECK")

    try:
        import wandb

        # Check if logged in
        api_key = wandb.api.api_key
        if api_key:
            print(f"{check_mark(True)} W&B API key configured")

            # Try to access API
            try:
                wandb.Api()
                print(f"{check_mark(True)} W&B API accessible")
                return True
            except Exception as e:
                print(f"{check_mark(False)} W&B API error: {e}")
                return False
        else:
            print(f"{check_mark(False)} W&B not logged in")
            print(f"\n{YELLOW}Run: wandb login{RESET}")
            return False

    except ImportError:
        print(f"{check_mark(False)} wandb package not installed")
        return False


def check_tests():
    """Check tests can run"""
    print_header("TESTING SETUP CHECK")

    try:
        import pytest

        print(f"{check_mark(True)} pytest installed: {pytest.__version__}")

        # Check test files exist
        test_dir = Path("tests")
        if test_dir.exists():
            test_files = list(test_dir.glob("test_*.py"))
            print(f"{check_mark(True)} Found {len(test_files)} test files")
            return True
        else:
            print(f"{check_mark(False)} tests/ directory not found")
            return False

    except ImportError:
        print(f"{check_mark(False)} pytest not installed")
        return False


def check_docker():
    """Check Docker setup"""
    print_header("DOCKER CHECK")

    dockerfile_exists = Path("Dockerfile").exists()
    print(f"{check_mark(dockerfile_exists)} Dockerfile exists")

    if dockerfile_exists:
        # Check if docker is installed
        import subprocess

        try:
            result = subprocess.run(
                ["docker", "--version"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                print(f"{check_mark(True)} Docker installed: {result.stdout.strip()}")
                return True
            else:
                print(f"{check_mark(False)} Docker not accessible")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print(f"{check_mark(False)} Docker not installed or not in PATH")
            return False

    return dockerfile_exists


def check_ms4_modifications():
    """Check MS4-specific modifications are in place"""
    print_header("MS4 MODIFICATIONS CHECK")

    checks = []

    # Check 1: data_versioning.py exists
    dv_exists = Path("data_versioning.py").exists()
    checks.append(("data_versioning.py exists", dv_exists))
    print(f"{check_mark(dv_exists)} data_versioning.py module")

    # Check 2: main.py has data versioning
    try:
        with open("main.py", "r") as f:
            main_content = f.read()
            has_versioning = "run_data_versioning" in main_content
            checks.append(("main.py has versioning", has_versioning))
            print(f"{check_mark(has_versioning)} main.py includes data versioning")
    except Exception:
        checks.append(("main.py has versioning", False))
        print(f"{check_mark(False)} Could not check main.py")

    # Check 3: backtest.py modified
    try:
        with open("backtest.py", "r") as f:
            backtest_content = f.read()
            has_api_columns = "pred_next_month" in backtest_content
            checks.append(("backtest.py has API columns", has_api_columns))
            print(f"{check_mark(has_api_columns)} backtest.py has API column fixes")
    except Exception:
        checks.append(("backtest.py has API columns", False))
        print(f"{check_mark(False)} Could not check backtest.py")

    # Check 4: README has MS4 sections
    try:
        with open("README.md", "r") as f:
            readme_content = f.read()
            has_ms4 = "MS4" in readme_content or "Data Versioning" in readme_content
            checks.append(("README.md has MS4 docs", has_ms4))
            print(f"{check_mark(has_ms4)} README.md has MS4 documentation")
    except Exception:
        checks.append(("README.md has MS4 docs", False))
        print(f"{check_mark(False)} Could not check README.md")

    return all(check[1] for check in checks)


def main():
    """Run all verification checks"""
    print(f"\n{BLUE}{'*'*60}")
    print(f"{'QUANTAMENTAL MODEL - SETUP VERIFICATION'.center(60)}")
    print(f"{'MS4 Submission Readiness Check'.center(60)}")
    print(f"{'*'*60}{RESET}\n")

    results = {
        "Python Version": check_python_version(),
        "Dependencies": check_dependencies(),
        "Project Structure": check_project_structure(),
        "Data Files": check_data_files(),
        "Configuration": check_configuration(),
        "W&B Setup": check_wandb_setup(),
        "Testing Setup": check_tests(),
        "Docker Setup": check_docker(),
        "MS4 Modifications": check_ms4_modifications(),
    }

    # Summary
    print_header("VERIFICATION SUMMARY")

    total = len(results)
    passed = sum(results.values())

    for check_name, result in results.items():
        print(f"{check_mark(result)} {check_name}")

    print(f"\n{BLUE}{'─'*60}{RESET}")
    print(f"Overall: {passed}/{total} checks passed")
    print(f"{BLUE}{'─'*60}{RESET}\n")

    if passed == total:
        print(f"{GREEN}✅ ALL CHECKS PASSED - READY FOR MS4!{RESET}\n")
        return 0
    else:
        print(
            f"{YELLOW}⚠️  {total - passed} checks failed - review issues above{RESET}\n"
        )

        # Provide helpful next steps
        if not results["Dependencies"]:
            print(f"{YELLOW}Next step: pip3 install -r requirements.txt{RESET}")
        elif not results["Data Files"]:
            print(f"{YELLOW}Next step: python main.py --step collect{RESET}")
        elif not results["W&B Setup"]:
            print(f"{YELLOW}Next step: wandb login{RESET}")
        elif not results["MS4 Modifications"]:
            print(f"{YELLOW}Next step: Apply MS4 code modifications{RESET}")

        return 1


if __name__ == "__main__":
    sys.exit(main())
