"""
Model Training Module
- Train Random Forest Classifier
- Log to Weights & Biases (W&B)
- Save model artifacts
- Evaluate performance
"""

import pandas as pd
import numpy as np
import joblib
from dateutil.relativedelta import relativedelta
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    classification_report,
    confusion_matrix,
    precision_recall_curve,
)
import matplotlib.pyplot as plt
import seaborn as sns
import wandb
import logging
import os

from utils import load_config, get_feature_list, ensure_dir

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QuantamentalTrainer:
    """Train and evaluate Quantamental model with W&B logging"""

    def __init__(self, config: dict):
        self.config = config
        self.data_dir = config["data"]["data_dir"]
        self.feature_names = get_feature_list(config)
        self.tech_cols = config["features"]["technical"]
        self.fund_cols = config["features"]["fundamental"]

        logger.info(" Quantamental Trainer initialized")
        logger.info(f"   Features: {len(self.feature_names)} total")

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare features for modeling:
        - Create lagged technical features
        - Forward-fill fundamentals
        - Create labels
        """
        logger.info(" Preparing features...")

        df = df.copy()

        # Create lagged technical features (prevent leakage)
        for col in self.tech_cols:
            df[f"{col}_lag1"] = df.groupby("symbol")[col].shift(1)

        # Forward-fill fundamentals (quarterly updates)
        df[self.fund_cols] = df.groupby("symbol")[self.fund_cols].ffill()

        # Create forward returns for labeling
        df["fwd_return_1m"] = df.groupby("symbol")["close"].shift(-1) / df["close"] - 1
        df["fwd_sp500_return_1m"] = df["sp500_return_1m"].shift(-1)

        # Label: 1 if stock outperforms S&P 500 next month
        df["label"] = (df["fwd_return_1m"] > df["fwd_sp500_return_1m"]).astype(int)

        # Drop rows with missing features or labels
        df_model = df.dropna(subset=self.feature_names + ["label"])

        logger.info(" Features prepared")
        logger.info(
            f"   Label distribution: {df_model['label'].value_counts(normalize=True).to_dict()}"
        )

        return df_model

    def create_train_test_split(
        self, df: pd.DataFrame, test_year: int = 2025, test_month: int = 10
    ) -> tuple:
        """
        Create time-based train/test split
        Train: 12 months before test month
        Test: Single month
        """
        test_start = pd.Timestamp(f"{test_year}-{test_month:02d}-01")
        train_start = test_start - relativedelta(months=12)
        train_end = test_start - relativedelta(days=1)

        train_mask = (df["date"] >= train_start) & (df["date"] <= train_end)
        test_mask = df["date"].dt.to_period("M") == test_start.to_period("M")

        df_train = df.loc[train_mask].copy()
        df_test = df.loc[test_mask].copy()

        logger.info(" Train/Test Split:")
        logger.info(
            f"   Train: {train_start.date()} → {train_end.date()} ({len(df_train):,} rows)"
        )
        logger.info(f"   Test: {test_start.strftime('%Y-%m')} ({len(df_test):,} rows)")

        return df_train, df_test

    def train_model(self, X_train: pd.DataFrame, y_train: pd.Series) -> tuple:
        """
        Train Random Forest model

        Returns:
            (model, scaler)
        """
        logger.info(" Training Random Forest...")

        # Handle inf and NaN
        X_train = X_train.replace([np.inf, -np.inf], 0).fillna(0)

        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)

        # Train model
        model_params = self.config["model"]["hyperparameters"]
        rf = RandomForestClassifier(**model_params)
        rf.fit(X_train_scaled, y_train)

        logger.info(f" Model trained with {rf.n_estimators} trees")

        return rf, scaler

    def evaluate_model(
        self, model, scaler, X_test: pd.DataFrame, y_test: pd.Series
    ) -> dict:
        """
        Evaluate model and return metrics
        """
        # Prepare test data
        X_test = X_test.replace([np.inf, -np.inf], 0).fillna(0)
        X_test_scaled = scaler.transform(X_test)

        # Predict
        y_pred = model.predict(X_test_scaled)
        y_prob = model.predict_proba(X_test_scaled)[:, 1]

        # Calculate metrics
        metrics = {
            "accuracy": accuracy_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred, zero_division=0),
            "recall": recall_score(y_test, y_pred, zero_division=0),
            "f1_score": f1_score(y_test, y_pred, zero_division=0),
            "roc_auc": roc_auc_score(y_test, y_prob),
        }

        logger.info(" Test Metrics:")
        for k, v in metrics.items():
            logger.info(f"   {k}: {v:.4f}")

        return metrics, y_pred, y_prob

    def find_optimal_threshold(
        self, model, scaler, X_train: pd.DataFrame, y_train: pd.Series
    ) -> float:
        """
        Find optimal probability threshold using precision-recall curve
        """
        X_train_scaled = scaler.transform(
            X_train.replace([np.inf, -np.inf], 0).fillna(0)
        )
        y_prob = model.predict_proba(X_train_scaled)[:, 1]

        precisions, recalls, thresholds = precision_recall_curve(y_train, y_prob)
        f1_scores = 2 * (precisions * recalls) / (precisions + recalls + 1e-9)

        best_idx = np.argmax(f1_scores)
        best_threshold = thresholds[best_idx] if len(thresholds) > 0 else 0.5

        logger.info(
            f" Optimal threshold: {best_threshold:.4f} (F1: {f1_scores[best_idx]:.4f})"
        )

        return best_threshold

    def create_plots(
        self, model, y_test, y_pred, y_prob, X_train: pd.DataFrame
    ) -> dict:
        """Create evaluation plots"""
        plots = {}

        # Confusion Matrix
        fig, ax = plt.subplots(figsize=(8, 6))
        cm = confusion_matrix(y_test, y_pred)
        sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", ax=ax)
        ax.set_title("Confusion Matrix")
        ax.set_xlabel("Predicted")
        ax.set_ylabel("Actual")
        plots["confusion_matrix"] = fig
        plt.close()

        # Feature Importance
        fig, ax = plt.subplots(figsize=(10, 8))
        importance_df = (
            pd.DataFrame(
                {
                    "feature": self.feature_names,
                    "importance": model.feature_importances_,
                }
            )
            .sort_values("importance", ascending=False)
            .head(20)
        )

        sns.barplot(data=importance_df, y="feature", x="importance", ax=ax)
        ax.set_title("Top 20 Feature Importances")
        ax.set_xlabel("Importance")
        plots["feature_importance"] = fig
        plt.close()

        # Prediction Distribution
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.hist(y_prob, bins=30, edgecolor="k", alpha=0.7)
        ax.set_title("Predicted Probability Distribution")
        ax.set_xlabel("Probability of Outperformance")
        ax.set_ylabel("Count")
        ax.axvline(0.5, color="r", linestyle="--", label="Default Threshold")
        ax.legend()
        plots["prob_distribution"] = fig
        plt.close()

        return plots

    def save_artifacts(self, model, scaler, run_id: str) -> dict:
        """
        Save model artifacts locally

        Returns:
            Dictionary of file paths
        """
        artifact_dir = ensure_dir(f"{self.data_dir}/models/{run_id}")

        paths = {
            "model": f"{artifact_dir}/model.pkl",
            "scaler": f"{artifact_dir}/scaler.pkl",
            "config": f"{artifact_dir}/config.pkl",
        }

        # Save model
        joblib.dump(model, paths["model"])
        joblib.dump(scaler, paths["scaler"])
        joblib.dump(self.config, paths["config"])

        logger.info(f" Artifacts saved to {artifact_dir}")

        return paths

    def train_with_wandb(
        self, df: pd.DataFrame, test_year: int = 2025, test_month: int = 10
    ) -> tuple:
        """
        Complete training pipeline with W&B logging

        Returns:
            (model, scaler, metrics)
        """
        # Initialize W&B
        run = wandb.init(
            project=self.config["wandb"]["project"],
            entity=self.config["wandb"]["entity"],
            tags=self.config["wandb"]["tags"],
            config={
                **self.config["model"]["hyperparameters"],
                "train_window_months": self.config["model"]["train_window_months"],
                "n_features": len(self.feature_names),
                "test_month": f"{test_year}-{test_month:02d}",
            },
        )

        logger.info(f" W&B Run: {run.name} ({run.id})")

        # Prepare features
        df_model = self.prepare_features(df)

        # Train/test split
        df_train, df_test = self.create_train_test_split(
            df_model, test_year, test_month
        )

        X_train = df_train[self.feature_names]
        y_train = df_train["label"]
        X_test = df_test[self.feature_names]
        y_test = df_test["label"]

        # Log training data as artifact instead of using DVC
        data_artifact = wandb.Artifact(
            name="training-data",
            type="dataset",
            description=f"Training data for {test_year}-{test_month:02d}",
        )

        # Save the training data temporarily
        train_data_path = (
            f"{self.data_dir}/train_data_{test_year}{test_month:02d}.parquet"
        )
        df_train.to_parquet(train_data_path, index=False)
        data_artifact.add_file(train_data_path)

        # Also log the processed full dataset
        full_data_path = f"{self.data_dir}/quantamental_monthly.parquet"
        if os.path.exists(full_data_path):
            data_artifact.add_file(full_data_path)

        run.log_artifact(data_artifact)
        logger.info(
            "Training data logged to W&B as artifact (version will auto-increment)"
        )

        # Log data statistics
        wandb.log(
            {
                "train_samples": len(X_train),
                "test_samples": len(X_test),
                "train_positive_ratio": y_train.mean(),
                "test_positive_ratio": y_test.mean(),
            }
        )

        # Train model
        model, scaler = self.train_model(X_train, y_train)

        # Find optimal threshold
        optimal_threshold = self.find_optimal_threshold(model, scaler, X_train, y_train)
        wandb.config.update({"optimal_threshold": optimal_threshold})

        # Evaluate
        metrics, y_pred, y_prob = self.evaluate_model(model, scaler, X_test, y_test)

        # Log metrics
        wandb.log(metrics)

        # Create and log plots
        plots = self.create_plots(model, y_test, y_pred, y_prob, X_train)
        for name, fig in plots.items():
            wandb.log({name: wandb.Image(fig)})

        # Log feature importance table
        importance_df = pd.DataFrame(
            {"feature": self.feature_names, "importance": model.feature_importances_}
        ).sort_values("importance", ascending=False)
        wandb.log({"feature_importance_table": wandb.Table(dataframe=importance_df)})

        # Save artifacts
        artifact_paths = self.save_artifacts(model, scaler, run.id)

        # Log artifacts to W&B
        artifact = wandb.Artifact(
            name="quantamental-model",
            type="model",
            description="Random Forest model for stock screening",
        )
        artifact.add_file(artifact_paths["model"])
        artifact.add_file(artifact_paths["scaler"])
        artifact.add_file(artifact_paths["config"])
        run.log_artifact(artifact)

        logger.info(" Model logged to W&B as artifact")

        # Log classification report
        report = classification_report(y_test, y_pred, output_dict=True)
        wandb.log({"classification_report": report})

        # Finish run
        wandb.finish()

        logger.info(" Training complete with W&B logging!")

        return model, scaler, metrics


def main():
    """Train model with W&B"""
    config = load_config()
    trainer = QuantamentalTrainer(config)

    # Load processed data
    logger.info(" Loading processed data...")
    df = pd.read_parquet(f"{config['data']['data_dir']}/quantamental_monthly.parquet")

    # Train with W&B
    model, scaler, metrics = trainer.train_with_wandb(df)

    print("\n Training complete!")
    print(f"   Accuracy: {metrics['accuracy']:.4f}")
    print(f"   F1 Score: {metrics['f1_score']:.4f}")
    print(f"   ROC AUC: {metrics['roc_auc']:.4f}")


if __name__ == "__main__":
    main()
