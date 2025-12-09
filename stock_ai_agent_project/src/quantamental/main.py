"""
Quantamental Pipeline - Main Script

Pipeline steps:
1. Data Collection (FMP API)
2. Data Processing (features)
3. Model Training (with validation)
4. Prediction (validated model)
5. Backtest (output CSV)
6. RAG Reasoning (optional)
7. Data Versioning (W&B artifacts)
"""

import asyncio
import argparse
import logging
from pathlib import Path
import pandas as pd

from utils import load_config
from data_collect import FMPDataCollector
from data_process import DataProcessor
from model_train import QuantamentalTrainer
from model_predict import QuantamentalPredictor
from backtest import QuantamentalBacktester

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)


# Safe imports for optional modules
try:
    from model_validation import validate_metrics, get_best_model

    HAS_MODEL_VALIDATION = True
except ImportError:
    HAS_MODEL_VALIDATION = False
    log.debug("model_validation not available")

try:
    from generate_stock_reasoning import add_reasoning_to_combined_file

    HAS_RAG = True
except ImportError:
    HAS_RAG = False
    log.debug("generate_stock_reasoning not available")

try:
    from data_versioning import DataVersionManager

    HAS_VERSIONING = True
except ImportError:
    HAS_VERSIONING = False
    log.debug("data_versioning not available")


# -----------------------------------------------------------------------------
# Pipeline Steps
# -----------------------------------------------------------------------------


def run_data_collection(config, force_refresh=False):
    """Step 1: Collect data from FMP API"""
    log.info("=" * 50)
    log.info("STEP 1: DATA COLLECTION")
    log.info("=" * 50)

    if force_refresh:
        import os

        data_dir = config["data"]["data_dir"]
        for f in [
            "ohlcv_raw.parquet",
            "fundamentals_combined.parquet",
            "sp500_index.parquet",
        ]:
            path = f"{data_dir}/{f}"
            if os.path.exists(path):
                os.remove(path)
                log.info(f"Removed cache: {path}")

    collector = FMPDataCollector(config)
    return asyncio.run(collector.collect_all())


def run_data_processing(config, data=None):
    """Step 2: Process data and engineer features"""
    log.info("=" * 50)
    log.info("STEP 2: DATA PROCESSING")
    log.info("=" * 50)

    processor = DataProcessor(config)

    if data is None:
        data_dir = config["data"]["data_dir"]
        data = {
            "ohlcv": pd.read_parquet(f"{data_dir}/ohlcv_raw.parquet"),
            "fundamentals": pd.read_parquet(
                f"{data_dir}/fundamentals_combined.parquet"
            ),
            "sp500_index": pd.read_parquet(f"{data_dir}/sp500_index.parquet"),
        }

    return processor.process_all(
        data["ohlcv"], data["fundamentals"], data["sp500_index"]
    )


def run_model_training(config, df=None, validate=True):
    """Step 3: Train model with W&B logging and validation"""
    log.info("=" * 50)
    log.info("STEP 3: MODEL TRAINING")
    log.info("=" * 50)

    trainer = QuantamentalTrainer(config)

    if df is None:
        df = pd.read_parquet(
            f"{config['data']['data_dir']}/quantamental_monthly.parquet"
        )

    model, scaler, metrics = trainer.train_with_wandb(df)

    # Validate model quality (if available)
    if validate and HAS_MODEL_VALIDATION:
        status, msg = validate_metrics(metrics)
        log.info(f"Model validation: {msg}")

        if status == "rejected":
            log.error("Model rejected! Accuracy below minimum threshold.")
        elif status == "degraded":
            log.warning("Model degraded - predictions may be unreliable")

    return model, scaler, metrics


def run_prediction(config, df=None, use_validated_model=True):
    """Step 4: Generate predictions"""
    log.info("=" * 50)
    log.info("STEP 4: PREDICTION")
    log.info("=" * 50)

    # Try to use validated model from W&B
    if use_validated_model and HAS_MODEL_VALIDATION:
        try:
            model, metrics, status = get_best_model(allow_degraded=True)
            if model is not None:
                log.info(
                    f"Using validated model: {status} ({metrics.get('accuracy', 0):.1%})"
                )
        except Exception as e:
            log.warning(f"Could not load validated model: {e}")

    # Use standard predictor
    predictor = QuantamentalPredictor(config)

    if df is None:
        df = pd.read_parquet(
            f"{config['data']['data_dir']}/quantamental_monthly.parquet"
        )

    return predictor.predict_next_month(df)


def run_backtest(config, df=None):
    """Step 5: Backtest and upload to GCS"""
    log.info("=" * 50)
    log.info("STEP 5: BACKTEST & GCS UPLOAD")
    log.info("=" * 50)

    backtester = QuantamentalBacktester(config)

    if df is None:
        df = pd.read_parquet(
            f"{config['data']['data_dir']}/quantamental_monthly.parquet"
        )

    return backtester.run_backtest(df, use_wandb_logging=True)


def run_rag_reasoning(config, combined_csv_path=None, sample_size=None):
    """Step 6: Add RAG reasoning to output CSV (optional)"""
    log.info("=" * 50)
    log.info("STEP 6: RAG REASONING")
    log.info("=" * 50)

    if not HAS_RAG:
        log.warning("generate_stock_reasoning not available, skipping RAG")
        return None

    # Default path if not provided
    if combined_csv_path is None:
        data_dir = config["data"]["data_dir"]
        combined_csv_path = (
            f"{data_dir}/combined_quantamental_hybrid_with_factors_and_backtest.csv"
        )

    if not Path(combined_csv_path).exists():
        log.warning(f"CSV not found: {combined_csv_path}, skipping RAG")
        return None

    try:
        enhanced_path = add_reasoning_to_combined_file(
            combined_file_path=combined_csv_path,
            sample_size=sample_size,
            max_workers=20,
            upload_to_gcs=True,
            gcs_bucket=config.get("gcs", {}).get("bucket_name"),
            gcs_path=config.get("gcs", {}).get("output_folder", "model_output")
            + "/combined_quantamental_hybrid_with_factors_and_backtest_with_reasoning.csv",
        )
        log.info(f"RAG reasoning added: {enhanced_path}")
        return enhanced_path
    except Exception as e:
        log.error(f"RAG reasoning failed: {e}")
        return None


def run_data_versioning(config, version_tag="ms4"):
    """Step 7: Version data with W&B artifacts"""
    log.info("=" * 50)
    log.info("STEP 7: DATA VERSIONING")
    log.info("=" * 50)

    if not HAS_VERSIONING:
        log.warning("data_versioning not available, skipping")
        return None

    versioner = DataVersionManager(config)
    version_info = versioner.create_version_snapshot(version_tag=version_tag)

    log.info(f"Data versioned: {', '.join(version_info.get('methods', []))}")
    return version_info


# -----------------------------------------------------------------------------
# Full Pipeline
# -----------------------------------------------------------------------------


def run_full_pipeline(
    force_refresh=False,
    skip_training=False,
    enable_rag=False,
    rag_sample_size=None,
    version_data=True,
):
    """Run complete pipeline."""
    log.info("STARTING QUANTAMENTAL PIPELINE")
    log.info("=" * 50)

    config = load_config()
    results = {}

    # Step 1: Data Collection
    data = run_data_collection(config, force_refresh=force_refresh)

    # Step 2: Data Processing
    df = run_data_processing(config, data)

    # Step 3: Model Training
    if not skip_training:
        model, scaler, metrics = run_model_training(config, df, validate=True)
        results["model_metrics"] = metrics
    else:
        log.info("Skipping training (using existing model)")

    # Step 4: Prediction
    df_predict, top_stocks = run_prediction(config, df, use_validated_model=True)
    results["top_stocks"] = top_stocks

    # Step 5: Backtest
    backtest_results = run_backtest(config, df)
    results["backtest"] = backtest_results

    # Step 6: RAG Reasoning (optional)
    if enable_rag:
        csv_path = backtest_results.get("local_files", {}).get("combined")
        enhanced_path = run_rag_reasoning(config, csv_path, sample_size=rag_sample_size)
        results["rag_output"] = enhanced_path

    # Step 7: Data Versioning (LAST)
    if version_data:
        version_info = run_data_versioning(config, version_tag="ms4")
        results["version_info"] = version_info

    log.info("=" * 50)
    log.info("PIPELINE COMPLETE")
    log.info("=" * 50)

    return results


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Quantamental Pipeline")
    parser.add_argument(
        "--step",
        choices=[
            "all",
            "collect",
            "process",
            "train",
            "predict",
            "backtest",
            "rag",
            "version",
        ],
        default="all",
    )
    parser.add_argument(
        "--force-refresh", action="store_true", help="Re-fetch data from API"
    )
    parser.add_argument(
        "--skip-training", action="store_true", help="Use existing model"
    )
    parser.add_argument("--enable-rag", action="store_true", help="Add RAG reasoning")
    parser.add_argument(
        "--rag-sample", type=int, default=None, help="Limit RAG to N stocks"
    )
    parser.add_argument(
        "--no-version", action="store_true", help="Skip data versioning"
    )

    args = parser.parse_args()
    config = load_config()

    try:
        if args.step == "all":
            run_full_pipeline(
                force_refresh=args.force_refresh,
                skip_training=args.skip_training,
                enable_rag=args.enable_rag,
                rag_sample_size=args.rag_sample,
                version_data=not args.no_version,
            )
        elif args.step == "collect":
            run_data_collection(config, args.force_refresh)
        elif args.step == "process":
            run_data_processing(config)
        elif args.step == "train":
            run_model_training(config, validate=True)
        elif args.step == "predict":
            run_prediction(config, use_validated_model=True)
        elif args.step == "backtest":
            run_backtest(config)
        elif args.step == "rag":
            run_rag_reasoning(config, sample_size=args.rag_sample)
        elif args.step == "version":
            run_data_versioning(config)

        log.info("Done!")

    except Exception as e:
        log.error(f"Pipeline failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
