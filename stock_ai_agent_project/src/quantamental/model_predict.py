"""
Model Prediction Module
- Load model from W&B artifacts
- Generate predictions for next month
- Rank stocks by outperformance probability
"""

import pandas as pd
import numpy as np
import joblib
from datetime import datetime
import wandb
import logging

from utils import load_config, get_feature_list

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QuantamentalPredictor:
    """Generate predictions using trained model"""

    def __init__(self, config: dict):
        self.config = config
        self.data_dir = config["data"]["data_dir"]
        self.feature_names = get_feature_list(config)
        self.tech_cols = config["features"]["technical"]
        self.fund_cols = config["features"]["fundamental"]
        self.model = None
        self.scaler = None

        logger.info("🔮 Quantamental Predictor initialized")

    def load_model_from_wandb(
        self, artifact_name: str = "quantamental-model:latest"
    ) -> tuple:
        """
        Load model and scaler from W&B artifacts

        Args:
            artifact_name: W&B artifact name with optional version (e.g., "model:latest" or "model:v0")

        Returns:
            (model, scaler)
        """
        logger.info(f"📥 Loading model from W&B: {artifact_name}")

        # Initialize W&B (without creating a new run)
        api = wandb.Api()

        # Download artifact
        artifact = api.artifact(
            f"{self.config['wandb']['project']}/{artifact_name}", type="model"
        )
        artifact_dir = artifact.download()

        # Load model and scaler
        model = joblib.load(f"{artifact_dir}/model.pkl")
        scaler = joblib.load(f"{artifact_dir}/scaler.pkl")

        logger.info(f"✅ Model loaded from {artifact_dir}")

        self.model = model
        self.scaler = scaler

        return model, scaler

    def load_model_local(self, model_path: str, scaler_path: str) -> tuple:
        """
        Load model and scaler from local files (fallback)

        Args:
            model_path: Path to model.pkl
            scaler_path: Path to scaler.pkl

        Returns:
            (model, scaler)
        """
        logger.info("📥 Loading model from local files...")

        model = joblib.load(model_path)
        scaler = joblib.load(scaler_path)

        logger.info("✅ Model loaded from local files")

        self.model = model
        self.scaler = scaler

        return model, scaler

    def prepare_prediction_data(
        self, df: pd.DataFrame, predict_month: pd.Timestamp = None
    ) -> pd.DataFrame:
        """
        Prepare data for prediction
        - Create lagged technical features
        - Forward-fill fundamentals
        - Get latest month's data
        """
        logger.info("🔧 Preparing prediction data...")

        df = df.copy()

        # Create lagged technical features
        for col in self.tech_cols:
            df[f"{col}_lag1"] = df.groupby("symbol")[col].shift(1)

        # Forward-fill fundamentals
        df[self.fund_cols] = df.groupby("symbol")[self.fund_cols].ffill()

        # Get latest available month if not specified
        if predict_month is None:
            latest_period = df["date"].dt.to_period("M").max()
            df_predict = df[df["date"].dt.to_period("M") == latest_period].copy()
            predict_month_str = latest_period.strftime("%Y-%m")
        else:
            df_predict = df[
                df["date"].dt.to_period("M") == predict_month.to_period("M")
            ].copy()
            predict_month_str = predict_month.strftime("%Y-%m")

        # Drop rows with missing features
        df_predict = df_predict.dropna(subset=self.feature_names)

        logger.info(f"✅ Prediction data prepared for {predict_month_str}")
        logger.info(f"   {len(df_predict)} stocks with complete features")

        return df_predict

    def predict(self, df_predict: pd.DataFrame) -> pd.DataFrame:
        """
        Generate predictions

        Returns:
            DataFrame with predictions added
        """
        if self.model is None or self.scaler is None:
            raise RuntimeError("Model not loaded. Call load_model_from_wandb() first.")

        logger.info("🎯 Generating predictions...")

        # Prepare features
        X = df_predict[self.feature_names]
        X = X.replace([np.inf, -np.inf], 0).fillna(0)
        X_scaled = self.scaler.transform(X)

        # Predict probabilities
        pred_prob = self.model.predict_proba(X_scaled)[:, 1]

        # Add predictions to dataframe
        df_predict["pred_prob"] = pred_prob
        df_predict["pred_rank"] = df_predict["pred_prob"].rank(ascending=False)

        logger.info("✅ Predictions generated")
        logger.info(f"   Mean probability: {pred_prob.mean():.4f}")
        logger.info(f"   Std probability: {pred_prob.std():.4f}")

        return df_predict

    def get_top_stocks(self, df_predict: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
        """
        Get top N predicted outperformers

        Args:
            df_predict: DataFrame with predictions
            top_n: Number of top stocks to return

        Returns:
            DataFrame with top N stocks
        """
        top_stocks = df_predict.nlargest(top_n, "pred_prob")[
            ["symbol", "date", "close", "pred_prob", "pred_rank"]
        ].copy()

        logger.info(f"📊 Top {top_n} predicted outperformers:")
        for idx, row in top_stocks.iterrows():
            logger.info(f"   {row['symbol']}: {row['pred_prob']:.4f}")

        return top_stocks

    def predict_next_month(
        self, df: pd.DataFrame, top_n: int = 10, use_wandb: bool = True
    ) -> tuple:
        """
        Complete prediction pipeline

        Args:
            df: Processed monthly data
            top_n: Number of top stocks to return
            use_wandb: Whether to load model from W&B

        Returns:
            (predictions_df, top_stocks_df)
        """
        logger.info("🚀 Starting prediction pipeline...")

        # Load model
        if use_wandb:
            self.load_model_from_wandb()

        # Prepare prediction data
        df_predict = self.prepare_prediction_data(df)

        # Generate predictions
        df_predict = self.predict(df_predict)

        # Get top stocks
        top_stocks = self.get_top_stocks(df_predict, top_n)

        logger.info("✅ Prediction pipeline complete!")

        return df_predict, top_stocks

    def save_predictions(
        self, df_predict: pd.DataFrame, output_path: str = None
    ) -> str:
        """
        Save predictions to file

        Args:
            df_predict: DataFrame with predictions
            output_path: Optional custom output path

        Returns:
            Path to saved file
        """
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            predict_month = df_predict["date"].dt.to_period("M").iloc[0]
            output_path = f"{self.data_dir}/predictions_{predict_month}_{timestamp}.csv"

        # Select important columns
        output_df = df_predict[
            ["symbol", "date", "close", "pred_prob", "pred_rank"]
        ].copy()
        output_df = output_df.sort_values("pred_rank")

        # Save
        output_df.to_csv(output_path, index=False)
        logger.info(f"💾 Predictions saved to {output_path}")

        return output_path


def main():
    """Test prediction pipeline"""
    config = load_config()
    predictor = QuantamentalPredictor(config)

    # Load processed data
    logger.info("📂 Loading processed data...")
    df = pd.read_parquet(f"{config['data']['data_dir']}/quantamental_monthly.parquet")

    # Generate predictions
    df_predict, top_stocks = predictor.predict_next_month(df, top_n=10)

    # Save predictions
    output_path = predictor.save_predictions(df_predict)

    print("\n✅ Prediction complete!")
    print("\n📊 Top 10 Stocks:")
    print(top_stocks.to_string(index=False))
    print(f"\n💾 Full predictions saved to: {output_path}")


if __name__ == "__main__":
    main()
