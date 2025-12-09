from api.utils.get_gcs_bucket import get_gcs_data
import pandas as pd


def get_company_profile(ticker, df_company_profile):
    try:
        company_profile = (
            df_company_profile[df_company_profile["symbol"] == ticker.upper()].fillna("NaN").to_dict(orient="records")[0]
        )
        return company_profile
    except Exception:
        print("No company profile available")
        return 0


def get_quant_data(ticker, df_quant_model):
    try:
        quant_data = df_quant_model[df_quant_model["symbol"] == ticker.upper()].fillna("NaN").to_dict(orient="records")[0]
        return quant_data
    except Exception:
        print("No data available")
        return 0


def get_stocks_data(ticker, df_stocks):
    df_stocks_oclh = df_stocks[df_stocks["symbol"] == ticker.upper()]
    print(f"Stocks data for {ticker}, {df_stocks_oclh.shape}")
    stocks_oclh = df_stocks_oclh.fillna("NaN").to_dict(orient="list")
    return stocks_oclh


def user_pref_stock_selection(df, user_pref):
    "Used for stock selection from the model based upon user preference"
    # Long term and short term filters
    if (user_pref["long_term"] & user_pref["short_term"]) or ((not user_pref["long_term"]) & (not user_pref["short_term"])):
        long_short_crit = ["Hybrid_Score"]
        recommended_model_filter = df["H_Score Recommendation"].isin(
            ["Long-Term Buy (Fundamental)", "Short-Term Buy (Momentum)"]
        )
        print("long_short")
    elif user_pref["long_term"]:
        long_short_crit = ["Hybrid_Score"]
        recommended_model_filter = df["H_Score Recommendation"].isin(["Long-Term Buy (Fundamental)"])
        print("long_term")
        long_short_crit = ["Hybrid_Score"]
    elif user_pref["short_term"]:
        long_short_crit = ["Technical_Score"]
        recommended_model_filter = df["H_Score Recommendation"].isin(["Short-Term Buy (Momentum)"])
        print("short_term")
    # User Risk profile mapping
    if (user_pref["low_risk"] & user_pref["high_risk"]) or ((not user_pref["low_risk"]) & (not user_pref["high_risk"])):
        risk_filter = df["volatility_21d"] < 10
        print("low_high_risk")
    elif user_pref["low_risk"]:
        risk_filter = (df["volatility_21d"] < 0.03) & (df["max_drawdown"] > -0.10)
        print("low_risk")
    else:
        risk_filter = df["volatility_21d"] < 10

    # print(risk_filter)
    df_shortlisted = df[recommended_model_filter & recommended_model_filter & risk_filter].sort_values(
        by=long_short_crit, ascending=False
    )
    print(df_shortlisted.shape)
    shortlisted_stocks = df_shortlisted.fillna("NaN").to_dict(orient="list")
    return shortlisted_stocks
