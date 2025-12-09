# from google.oauth2 import service_account
import pandas as pd
from google.cloud import storage
from io import BytesIO
from api.utils.get_gcs_bucket import get_gcs_data
from api.utils.detailed_page_funcs import (
    get_company_profile,
    get_quant_data,
    get_stocks_data,
    user_pref_stock_selection,
)
import uuid
from fastapi import APIRouter, Header, Request, Body, HTTPException
from fastapi.responses import JSONResponse
import ast
from typing import Any
from datetime import datetime
from collections import defaultdict


# credentials_path = "../secrets/stock-busters-service-account.json"

# file_quant_model = 'model_output/combined_quantamental_hybrid_with_factors_and_backtest.csv'
file_quant_model = "model_output/combined_quantamental_hybrid_with_factors_and_backtest_with_reasoning.csv"
file_company_profile = "model_output/company_profiles.csv"
file_stocks = "model_output/ohlcv_raw.parquet"

# Load dataframes - will return None if GCS client is not initialized (will be mocked in tests)
df_quant_model = get_gcs_data(file_quant_model)
df_company_profile = get_gcs_data(file_company_profile)
df_stocks = get_gcs_data(file_stocks, file_type="parquet")

# If dataframes are None (credentials missing), create empty dataframes to prevent errors
# These will be replaced by mocks in tests
import pandas as pd

if df_quant_model is None:
    df_quant_model = pd.DataFrame()
if df_company_profile is None:
    df_company_profile = pd.DataFrame()
if df_stocks is None:
    df_stocks = pd.DataFrame()


reports_storage = defaultdict(list)

router = APIRouter()


@router.get("/details/{ticker}")
async def get_chat(ticker: str):
    """The gets tickers and generate detailed report for the stock"""
    company_profile = get_company_profile(ticker, df_company_profile)
    stocks_data = get_stocks_data(ticker, df_stocks)
    quant_model = get_quant_data(ticker, df_quant_model)
    return {
        "company_profile": company_profile,
        "stocks_data": stocks_data,
        "quant_model": quant_model,
    }


@router.post("/{model}/chats/{chat_id}/report")
async def generate_report(
    model: str,
    chat_id: str,
    request_body: dict[str, Any] = Body(...),
    x_session_id: str = Header(None, alias="X-Session-ID"),
):
    """
    Generate investment report based on user preferences
    """
    print(f"=== GENERATE REPORT ENDPOINT HIT ===")

    try:
        # Extract user preferences
        user_preferences = request_body.get("user_pref", {})
        long_term = user_preferences.get("long_term", True)
        short_term = user_preferences.get("short_term", True)

        print(f"User preferences - Long term: {long_term}, Short term: {short_term}")

        # Get stock recommendations
        raw_recommendations = user_pref_stock_selection(df_quant_model, user_preferences)
        print("user_preferences = ", user_preferences)
        stock_symbols = raw_recommendations.get("symbol", [])
        print(raw_recommendations["symbol"])

        print(f"Found {len(stock_symbols)} stock symbols")

        # Create proper stock objects from the symbols
        recommendations = []
        for symbol in stock_symbols:
            # Get stock data from your dataframes
            stock_data = df_quant_model[df_quant_model["symbol"] == symbol]

            if len(stock_data) > 0:
                stock_info = stock_data.iloc[0]

                # Determine AI Score based on user preference
                if (short_term & long_term) or ((not short_term) & (not long_term)):
                    ai_score = float(stock_info.get("Hybrid_Score", 0)) if pd.notna(stock_info.get("Hybrid_Score")) else 0.0

                elif short_term:
                    # Use Technical_Score for short-term
                    ai_score = (
                        float(stock_info.get("Technical_Score", 0)) if pd.notna(stock_info.get("Technical_Score")) else 0.0
                    )
                elif long_term:
                    # Use Fundamental_Score for long-term
                    ai_score = (
                        float(stock_info.get("Fundamental_Score", 0)) if pd.notna(stock_info.get("Fundamental_Score")) else 0.0
                    )
                else:
                    # Use Hybrid_Score as default
                    ai_score = float(stock_info.get("Hybrid_Score", 0)) if pd.notna(stock_info.get("Hybrid_Score")) else 0.0

                recommendations.append(
                    {
                        "symbol": symbol,
                        "sector": stock_info.get("sector", stock_info.get("Sector", "N/A")),
                        # "signal": stock_info.get('signal', stock_info.get('Signal', 'NEUTRAL')),
                        "signal": stock_info.get("H_Score Recommendation"),
                        "ai_score": ai_score,  # Changed from ai_rank to ai_score
                        "sharpe": (
                            float(
                                stock_info.get(
                                    "sharpe_1m_annual",
                                    stock_info.get("sharpe_1m_annual", 0),
                                )
                            )
                            if pd.notna(
                                stock_info.get(
                                    "sharpe_1m_annual",
                                    stock_info.get("sharpe_1m_annual", 0),
                                )
                            )
                            else 0.0
                        ),
                        "cagr": (
                            float(stock_info.get("cagr", stock_info.get("CAGR", 0)))
                            if pd.notna(stock_info.get("cagr", stock_info.get("CAGR", 0)))
                            else 0.0
                        ),
                        "max_drawdown": (
                            float(stock_info.get("max_drawdown", stock_info.get("Max_Drawdown", 0)))
                            if pd.notna(stock_info.get("max_drawdown", stock_info.get("Max_Drawdown", 0)))
                            else 0.0
                        ),
                    }
                )

        # Sort by ai_score in descending order (highest scores first)
        recommendations.sort(key=lambda x: x["ai_score"], reverse=True)

        print(f"Sample recommendation (sorted): {recommendations[0] if recommendations else 'None'}")

        # Create report
        report_data = {
            "report_id": str(uuid.uuid4()),
            "chat_id": chat_id,
            "user_preferences": user_preferences,
            "generated_at": datetime.now().isoformat(),
            "status": "completed",
            "recommendations": recommendations,
            "summary": {
                "total_recommendations": len(recommendations),
                "investment_horizon": ("Long-term" if long_term else "Short-term" if short_term else "Balanced"),
                "risk_profile": ("High Risk" if user_preferences.get("high_risk") else "Low Risk"),
                "sectors": user_preferences.get("sectors", []),
            },
        }
        reports_storage[x_session_id].append(report_data)
        return {
            "success": True,
            "report": report_data,
            "message": "Report generated successfully",
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{model}/reports")
async def get_reports(model: str, limit: int = 20, x_session_id: str = Header(None, alias="X-Session-ID")):
    """ "Generates reports for specific chats"""
    session_reports = reports_storage.get(x_session_id, [])
    sorted_reports = sorted(session_reports, key=lambda x: x.get("generated_at", ""), reverse=True)[:limit]
    return sorted_reports


@router.get("/report")
async def get_recommended_stocks(user_pref: str):
    """Collects user preference and generate report as per the user preference"""
    print(user_pref)
    # converts the string to a dictionary
    user_prefs_dict = ast.literal_eval(user_pref)
    short_listed = user_pref_stock_selection(df_quant_model, user_prefs_dict)
    return {"stocks": short_listed}
