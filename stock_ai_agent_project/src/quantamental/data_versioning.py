"""
Data Versioning Module
Handles versioning of input data files using both GCS and W&B Artifacts
For MS4 requirement: Data versioning strategy


"""

import pandas as pd
from datetime import datetime
from pathlib import Path
import logging
from typing import Dict
import json
import wandb

# Try to import GCS, but make it optional
try:
    from google.cloud import storage

    HAS_GCS = True
except ImportError:
    HAS_GCS = False
    logging.warning("google-cloud-storage not installed. GCS versioning disabled.")

from utils import load_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataVersionManager:
    """
    Manages data versioning using both GCS and W&B Artifacts

    MS4 Requirement: Demonstrate data versioning strategy for reproducibility

    Features:
    - W&B Artifacts for ML-centric versioning
    - GCS object versioning for cloud storage
    - Local metadata snapshots for quick reference
    """

    def __init__(self, config: dict = None):
        if config is None:
            config = load_config()

        self.config = config
        self.data_dir = config["data"]["data_dir"]
        self.wandb_project = config["wandb"]["project"]

        # Initialize GCS client if available
        self.gcs_client = None
        self.gcs_bucket = None
        if HAS_GCS:
            try:
                self.gcs_client = storage.Client()
                bucket_name = config.get("gcs", {}).get(
                    "bucket_name", "stock-busters-data"
                )
                self.gcs_bucket = self.gcs_client.bucket(bucket_name)
                logger.info(f" GCS versioning enabled: {bucket_name}")
            except Exception as e:
                logger.warning(f"  GCS versioning disabled: {e}")
        else:
            logger.info("  GCS not available (google-cloud-storage not installed)")

        logger.info(" Data Version Manager initialized")

    def save_input_data_snapshot(
        self,
        ohlcv_path: str,
        sp500_path: str,
        fundamentals_path: str = None,
        version_tag: str = None,
    ) -> Dict:
        """
        Create versioned snapshot of input data files

        Args:
            ohlcv_path: Path to ohlcv_raw.parquet
            sp500_path: Path to sp500_index.parquet
            fundamentals_path: Optional path to fundamentals
            version_tag: Optional version tag (e.g., 'ms4_v1')

        Returns:
            Dictionary with version metadata
        """
        if version_tag is None:
            version_tag = f"v_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        logger.info(f" Creating data snapshot: {version_tag}")

        version_info = {
            "version_tag": version_tag,
            "timestamp": datetime.now().isoformat(),
            "files": {},
        }

        # Version each file
        files_to_version = {"ohlcv_raw": ohlcv_path, "sp500_index": sp500_path}

        if fundamentals_path:
            files_to_version["fundamentals"] = fundamentals_path

        for name, path in files_to_version.items():
            if Path(path).exists():
                try:
                    df = pd.read_parquet(path)

                    metadata = {
                        "rows": len(df),
                        "columns": list(df.columns),
                        "shape": list(df.shape),
                        "memory_mb": round(
                            df.memory_usage(deep=True).sum() / 1024 / 1024, 2
                        ),
                        "file_size_mb": round(
                            Path(path).stat().st_size / 1024 / 1024, 2
                        ),
                    }

                    # Add date range if date column exists
                    if df.index.name == "date" or "date" in df.columns:
                        date_col = df.index if df.index.name == "date" else df["date"]
                        metadata["date_range"] = {
                            "start": str(pd.to_datetime(date_col).min()),
                            "end": str(pd.to_datetime(date_col).max()),
                            "days": (
                                pd.to_datetime(date_col).max()
                                - pd.to_datetime(date_col).min()
                            ).days,
                        }

                    # Add unique symbols count if symbol column exists
                    if "symbol" in df.columns:
                        metadata["unique_symbols"] = int(df["symbol"].nunique())

                    version_info["files"][name] = metadata
                    logger.info(
                        f"    {name}: {len(df):,} rows, {len(df.columns)} columns, {metadata['file_size_mb']} MB"
                    )

                except Exception as e:
                    logger.error(f"    Error processing {name}: {e}")
                    version_info["files"][name] = {"error": str(e)}
            else:
                logger.warning(f"     {name} not found: {path}")
                version_info["files"][name] = {"error": "File not found"}

        return version_info

    def version_with_wandb(
        self,
        ohlcv_path: str,
        sp500_path: str,
        fundamentals_path: str = None,
        version_tag: str = None,
    ) -> str:
        """
        Version input data as W&B Artifacts

        Args:
            ohlcv_path: Path to ohlcv_raw.parquet
            sp500_path: Path to sp500_index.parquet
            fundamentals_path: Optional path to fundamentals
            version_tag: Optional version tag

        Returns:
            Artifact version string
        """
        if version_tag is None:
            version_tag = f"ms4_{datetime.now().strftime('%Y%m%d')}"

        logger.info(f" Versioning data with W&B: {version_tag}")

        # Initialize W&B run
        run = wandb.init(
            project=self.wandb_project,
            job_type="data_versioning",
            name=f"data_version_{version_tag}",
            tags=["data_versioning", "ms4", version_tag],
            config={
                "version_tag": version_tag,
                "purpose": "MS4 data versioning",
                "timestamp": datetime.now().isoformat(),
            },
        )

        # Create artifact for each input file
        artifacts_created = []

        files_to_version = {"ohlcv_raw": ohlcv_path, "sp500_index": sp500_path}

        if fundamentals_path:
            files_to_version["fundamentals"] = fundamentals_path

        for name, path in files_to_version.items():
            if not Path(path).exists():
                logger.warning(f"     Skipping {name}: file not found at {path}")
                continue

            try:
                # Load data for metadata
                df = pd.read_parquet(path)

                # Create artifact metadata
                artifact_metadata = {
                    "version_tag": version_tag,
                    "rows": len(df),
                    "columns": list(df.columns),
                    "shape": list(df.shape),
                    "file_size_mb": round(Path(path).stat().st_size / 1024 / 1024, 2),
                    "created_at": datetime.now().isoformat(),
                }

                # Add date range if available
                if df.index.name == "date" or "date" in df.columns:
                    date_col = df.index if df.index.name == "date" else df["date"]
                    artifact_metadata["date_range"] = {
                        "start": str(pd.to_datetime(date_col).min()),
                        "end": str(pd.to_datetime(date_col).max()),
                    }

                # Add symbol count if available
                if "symbol" in df.columns:
                    artifact_metadata["unique_symbols"] = int(df["symbol"].nunique())

                # Create artifact
                artifact = wandb.Artifact(
                    name=name,
                    type="raw_data",
                    description=f"Input data: {name} ({version_tag})",
                    metadata=artifact_metadata,
                )

                # Add file to artifact
                artifact.add_file(path, name=f"{name}.parquet")

                # Log artifact
                logged_artifact = run.log_artifact(artifact)
                logged_artifact.wait()
                artifacts_created.append(f"{name}:v{artifact.version}")

                logger.info(f"    {name} → W&B artifact v{artifact.version}")

            except Exception as e:
                logger.error(f"    Error versioning {name} with W&B: {e}")

        # Log summary
        run.summary["artifacts_created"] = artifacts_created
        run.summary["version_tag"] = version_tag
        run.summary["num_artifacts"] = len(artifacts_created)

        run.finish()

        logger.info(f" W&B versioning complete: {len(artifacts_created)} artifacts")

        return version_tag

    def version_with_gcs(
        self,
        ohlcv_path: str,
        sp500_path: str,
        fundamentals_path: str = None,
        version_tag: str = None,
    ) -> Dict:
        """
        Version input data using GCS object versioning

        Note: Requires bucket to have versioning enabled

        Args:
            ohlcv_path: Path to ohlcv_raw.parquet
            sp500_path: Path to sp500_index.parquet
            fundamentals_path: Optional path to fundamentals
            version_tag: Optional version tag

        Returns:
            Dictionary with GCS generation numbers
        """
        if not HAS_GCS or self.gcs_bucket is None:
            logger.warning("  GCS versioning not available")
            return {"error": "GCS not available"}

        if version_tag is None:
            version_tag = f"ms4_{datetime.now().strftime('%Y%m%d')}"

        logger.info(f"☁️  Versioning data with GCS: {version_tag}")

        generation_numbers = {}

        files_to_version = {"ohlcv_raw": ohlcv_path, "sp500_index": sp500_path}

        if fundamentals_path:
            files_to_version["fundamentals"] = fundamentals_path

        for name, path in files_to_version.items():
            if not Path(path).exists():
                logger.warning(f"     Skipping {name}: file not found")
                continue

            try:
                # Upload to GCS (versioning must be enabled on bucket)
                blob_name = f"raw_data/{name}.parquet"
                blob = self.gcs_bucket.blob(blob_name)

                # Add metadata
                blob.metadata = {
                    "version_tag": version_tag,
                    "upload_timestamp": datetime.now().isoformat(),
                    "source": "quantamental_pipeline",
                    "file_size_mb": str(
                        round(Path(path).stat().st_size / 1024 / 1024, 2)
                    ),
                }

                # Upload
                blob.upload_from_filename(path)

                generation_numbers[name] = str(blob.generation)

                logger.info(f"   ✅ {name} → GCS generation {blob.generation}")

                # Also save metadata file
                df = pd.read_parquet(path)
                metadata = {
                    "version_tag": version_tag,
                    "generation": str(blob.generation),
                    "rows": len(df),
                    "columns": list(df.columns),
                    "timestamp": datetime.now().isoformat(),
                    "blob_name": blob_name,
                }

                metadata_blob = self.gcs_bucket.blob(
                    f"metadata/{name}_{version_tag}.json"
                )
                metadata_blob.upload_from_string(json.dumps(metadata, indent=2))

            except Exception as e:
                logger.error(f"    Error uploading {name} to GCS: {e}")
                generation_numbers[name] = {"error": str(e)}

        logger.info(f" GCS versioning complete: {len(generation_numbers)} files")

        return generation_numbers

    def create_version_snapshot(self, version_tag: str = "ms4_submission") -> Dict:
        """
        Complete versioning: W&B + GCS + local snapshot

        Versions BOTH:
        - Input files (ohlcv_raw, sp500_index, fundamentals)
        - Output files (combined CSV, company profiles, equity curves)

        Args:
            version_tag: Version identifier (default: 'ms4_submission')

        Returns:
            Complete version information
        """
        logger.info("=" * 60)
        logger.info(f"📦 CREATING DATA VERSION SNAPSHOT: {version_tag}")
        logger.info("=" * 60)

        version_info = {
            "version_tag": version_tag,
            "timestamp": datetime.now().isoformat(),
            "methods": [],
            "status": "success",
            "input_files": {},
            "output_files": {},
        }

        # ============================================
        # PART 1: VERSION INPUT FILES
        # ============================================
        logger.info("\n📥 VERSIONING INPUT FILES:")

        input_files = {
            "ohlcv_raw": f"{self.data_dir}/ohlcv_raw.parquet",
            "sp500_index": f"{self.data_dir}/sp500_index.parquet",
            "fundamentals": f"{self.data_dir}/fundamentals_combined.parquet",
        }

        # Create W&B run for versioning
        run = wandb.init(
            project=self.wandb_project,
            job_type="data_versioning",
            name=f"data_version_{version_tag}",
            tags=["data_versioning", "ms4", version_tag],
            config={
                "version_tag": version_tag,
                "purpose": "MS4 data versioning - inputs + outputs",
                "timestamp": datetime.now().isoformat(),
            },
        )

        artifacts_created = []

        # Version each input file
        for name, path in input_files.items():
            if not Path(path).exists():
                logger.warning(f"   ⚠️  {name}: not found at {path}")
                version_info["input_files"][name] = {"error": "File not found"}
                continue

            try:
                # Load data for metadata
                df = pd.read_parquet(path)

                # Create metadata
                metadata = {
                    "version_tag": version_tag,
                    "file_type": "input",
                    "rows": len(df),
                    "columns": list(df.columns),
                    "shape": list(df.shape),
                    "file_size_mb": round(Path(path).stat().st_size / 1024 / 1024, 2),
                    "created_at": datetime.now().isoformat(),
                }

                # Add date range if available
                if df.index.name == "date" or "date" in df.columns:
                    date_col = df.index if df.index.name == "date" else df["date"]
                    metadata["date_range"] = {
                        "start": str(pd.to_datetime(date_col).min()),
                        "end": str(pd.to_datetime(date_col).max()),
                    }

                # Add symbol count if available
                if "symbol" in df.columns:
                    metadata["unique_symbols"] = int(df["symbol"].nunique())

                # Create W&B artifact
                artifact = wandb.Artifact(
                    name=f"input_{name}",
                    type="raw_data",
                    description=f"Input data: {name} ({version_tag})",
                    metadata=metadata,
                )

                # Add file
                artifact.add_file(path, name=f"{name}.parquet")

                # Log and wait
                logged_artifact = run.log_artifact(artifact)
                logged_artifact.wait()

                artifacts_created.append(f"input_{name}:v{logged_artifact.version}")
                version_info["input_files"][name] = metadata

                logger.info(
                    f"   ✅ {name}: {len(df):,} rows, {metadata['file_size_mb']} MB → v{logged_artifact.version}"
                )

            except Exception as e:
                logger.error(f"   ❌ Error versioning {name}: {e}")
                version_info["input_files"][name] = {"error": str(e)}

        # ============================================
        # PART 2: VERSION OUTPUT FILES
        # ============================================
        logger.info("\n📤 VERSIONING OUTPUT FILES:")

        output_files = {
            "combined_quantamental": f"{self.data_dir}/combined_quantamental_hybrid_with_factors_and_backtest.csv",
            "company_profiles": f"{self.data_dir}/company_profiles.csv",
            "equity_curves": f"{self.data_dir}/all_equity_curves.csv",
        }

        # Version each output file
        for name, path in output_files.items():
            if not Path(path).exists():
                logger.warning(f"   ⚠️  {name}: not found at {path}")
                version_info["output_files"][name] = {"error": "File not found"}
                continue

            try:
                # Load data for metadata
                df = pd.read_csv(path)

                # Create metadata
                metadata = {
                    "version_tag": version_tag,
                    "file_type": "output",
                    "rows": len(df),
                    "columns": list(df.columns),
                    "num_columns": len(df.columns),
                    "shape": list(df.shape),
                    "file_size_mb": round(Path(path).stat().st_size / 1024 / 1024, 2),
                    "created_at": datetime.now().isoformat(),
                }

                # Add date range if available
                if "date" in df.columns:
                    try:
                        date_col = pd.to_datetime(df["date"])
                        metadata["date_range"] = {
                            "start": str(date_col.min()),
                            "end": str(date_col.max()),
                        }
                    except Exception:
                        pass

                # Add symbol count if available
                if "symbol" in df.columns:
                    metadata["unique_symbols"] = int(df["symbol"].nunique())

                # Create W&B artifact
                artifact = wandb.Artifact(
                    name=f"output_{name}",
                    type="model_output",
                    description=f"Output file: {name} ({version_tag})",
                    metadata=metadata,
                )

                # Add file
                artifact.add_file(path, name=f"{name}.csv")

                # Log and wait
                logged_artifact = run.log_artifact(artifact)
                logged_artifact.wait()

                artifacts_created.append(f"output_{name}:v{logged_artifact.version}")
                version_info["output_files"][name] = metadata

                logger.info(
                    f"   ✅ {name}: {len(df):,} rows, {len(df.columns)} cols → v{logged_artifact.version}"
                )

            except Exception as e:
                logger.error(f"   ❌ Error versioning {name}: {e}")
                version_info["output_files"][name] = {"error": str(e)}

        # Log summary to W&B
        run.summary["artifacts_created"] = artifacts_created
        run.summary["version_tag"] = version_tag
        run.summary["num_input_files"] = len(
            [v for v in version_info["input_files"].values() if "error" not in v]
        )
        run.summary["num_output_files"] = len(
            [v for v in version_info["output_files"].values() if "error" not in v]
        )
        run.summary["total_artifacts"] = len(artifacts_created)

        run.finish()

        version_info["methods"].append("wandb_artifacts")
        version_info["wandb_artifacts"] = artifacts_created

        # ============================================
        # PART 3: SAVE LOCAL SNAPSHOT
        # ============================================
        logger.info("\n💾 SAVING LOCAL SNAPSHOT:")

        version_file = f"{self.data_dir}/version_info_{version_tag}.json"
        try:
            with open(version_file, "w") as f:
                json.dump(version_info, f, indent=2)
            logger.info(f"   ✅ Version info saved to: {version_file}")
            version_info["methods"].append("local_snapshot")
        except Exception as e:
            logger.error(f"   ❌ Failed to save version info: {e}")

        # ============================================
        # SUMMARY
        # ============================================
        logger.info("\n" + "=" * 60)
        logger.info("✅ VERSION SNAPSHOT COMPLETE!")
        logger.info(f"   Version tag: {version_tag}")
        logger.info(
            f"   Input files versioned: {len([v for v in version_info['input_files'].values() if 'error' not in v])}"
        )
        logger.info(
            f"   Output files versioned: {len([v for v in version_info['output_files'].values() if 'error' not in v])}"
        )
        logger.info(f"   Total W&B artifacts: {len(artifacts_created)}")
        logger.info(f"   Methods used: {', '.join(version_info['methods'])}")
        logger.info(f"   Info saved to: {version_file}")
        logger.info("=" * 60)

        return version_info


def main():
    """Test data versioning"""
    import argparse

    parser = argparse.ArgumentParser(description="Version input data for MS4")
    parser.add_argument(
        "--version-tag",
        default="ms4_submission",
        help="Version tag (default: ms4_submission)",
    )
    args = parser.parse_args()

    logger.info(" Starting data versioning...")

    config = load_config()
    versioner = DataVersionManager(config)

    # Create MS4 submission snapshot
    version_info = versioner.create_version_snapshot(version_tag=args.version_tag)

    print("\n" + "=" * 60)
    print(" DATA VERSIONING COMPLETE!")
    print("=" * 60)
    print(f"\nVersion Tag: {version_info['version_tag']}")
    print(f"Methods Used: {', '.join(version_info['methods'])}")
    print(f"\nVersion Info:")
    print(json.dumps(version_info, indent=2))
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
