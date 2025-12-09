from api.utils.get_gcs_bucket import get_gcs_data
import pandas as pd


def get_company_profile(ticker, df_company_profile):
    """The function gets the company ticker and return the company details"""
    company_profile = (
        df_company_profile[df_company_profile["symbol"] == ticker.upper()].fillna("NaN").to_dict(orient="records")[0]
    )
    return company_profile


def get_quant_data(ticker, df_quant_model):
    """The function gets the company ticker and return the quant model metrics"""
    company_profile = df_quant_model[df_quant_model["symbol"] == ticker.upper()].fillna("NaN").to_dict(orient="records")[0]
    return company_profile


def get_stocks_data(ticker, df_stocks):
    """The function gets the company ticker and return the stocks data"""
    stocks_oclh = df_stocks[df_stocks["symbol"] == ticker.upper()].fillna("NaN").to_dict(orient="list")
    return stocks_oclh
