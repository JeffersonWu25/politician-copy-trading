"""
This script creates a portfolio of stocks based on the 
transactions of a politician.
"""
from collections import defaultdict
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt

renamed_stocks = {"FB": "META"}
failed_downloads = []

def load_transactions(file_path):
    """
    Loads the transactions CSV file and returns a DataFrame.

    Args:
        file-path: Path to all congress trades file

    Returns:
        Dataframe containing the transactions
    """
    return pd.read_csv(file_path)

def clean_transactions(df, cutoff_date, renamed_stocks):
    """
    Reformats and cleans raw data for processing

    Args:
        df: Dataframe containing raw transactions
        cutoff_date: String representing earliest date
        renamed_stocks: Dictionary for renaming stock tickers

    Returns: 
        Dataframe representing cleaned data
    """
    df["ReportDate"] = pd.to_datetime(df["ReportDate"])
    df["TransactionDate"] = pd.to_datetime(df["TransactionDate"])

    df = df.loc[df["TransactionDate"] > cutoff_date]
    df.loc[~df["Transaction"].str.contains("Purchase"),
           "Amount"] = - df["Amount"]
    df.loc[:, "Ticker"] = df["Ticker"].replace(renamed_stocks)

    return df.sort_values("TransactionDate")

def choose_politician(df, politician):
    """
    Subsets dataframe for a single politician's trades

    Parameters:
        df: Dataframe of cleaned transactions
        politician: string representing politition name

    Returns:
        dataframe of trades from just imputed politician
    """
    return df.loc[(df["Representative"] == politician)]

def download_stock_data(politician_trades, cutoff_date, end_date=None):
    """
    Downloads politician traded stocks and adds it to the spy dataframe

    Args:
        portfolio: Dataframe containing politician trades
        cutoff_date: String representing earliest date
        end_date: String representing end date
    
    Returns:
        Dataframe representing stock data
    """
    tickers = politician_trades["Ticker"].unique().tolist()
    tickers.append("SPY")

    stocks = yf.download(tickers, start=cutoff_date, end=end_date, 
                         auto_adjust=True, rounding=True, progress=False)
    stocks_close = stocks['Close']

    stock_data = stocks_close.reset_index().melt(id_vars=['Date'],
                                                 var_name='Ticker',
                                                 value_name='Close')

    stock_data = stock_data.dropna(subset=['Close'])
    stock_data = stock_data.sort_values(by=['Ticker', 'Date'])
    stock_data["DailyROI"] = (
        stock_data.groupby('Ticker')['Close']
        .pct_change().fillna(0) + 1.0
    )

    return stock_data

def add_stock_amount_column(politician_trades, stock_data):
    """
    Add stock amount column to politician trade history

    Args:
        politician_trades: Dataframe containing the politician trades
        stock_data: Dataframe containg stock data

    Returns:
        Dataframe of updated politician trades
    """
    politician_trades = politician_trades.merge(stock_data, how='left', left_on=['TransactionDate', 'Ticker'], right_on=['Date', 'Ticker'])
    politician_trades.drop(columns=['Date', "DailyROI"], inplace=True)
    politician_trades["StockAmount"] = politician_trades["Amount"]/politician_trades["Close"]
    return politician_trades

def holdings(trades, cutoff_date, groupby_column = "TransactionDate", end_date=None):
    """
    Creates dataframe of politician or copy traded stock holdings on each date. 
    Each stock held on each date has own entry

    Args:
        trades: dataframe containing the politician trades
        cutoff_date: String representing earliest date
        groupby_column: String representing calculating holding 
                        for actual trades or copy trades
        end_date: String representing end date
    
    Returns:
        Dataframe representing politician or copy traded holdings
    """
    dates = yf.download("SPY", start=cutoff_date, end=end_date, auto_adjust=True, rounding=True, progress=False).index.strftime("%Y-%m-%d")
    dates = pd.to_datetime(dates)

    cumulative_holdings = defaultdict(int)
    holdings_list = []

    trades_grouped = trades.groupby(groupby_column)

    for date in dates:
        if date in trades_grouped.groups:
            day_transactions = trades_grouped.get_group(date)

            # Efficiently update cumulative holdings
            for ticker, stock_amount in day_transactions.groupby('Ticker')['StockAmount'].sum().items():
                cumulative_holdings[ticker] += stock_amount
                if cumulative_holdings[ticker] <= 0:
                    del cumulative_holdings[ticker]

        # Append the current state of holdings to the list
        for ticker, stock_amount in cumulative_holdings.items():
            holdings_list.append({
                'Date': date,
                'Ticker': ticker,
                'StockAmount': stock_amount,
            })

    # Convert the holdings list to a DataFrame
    holdings_df = pd.DataFrame(holdings_list)

    return holdings_df 

def calculate_portfolio_roi(politician_trades, cutoff_date, stock_data, groupby_column):
    """
    Calculate cumulative portfolio roi for politician 
    and copy traded portfolios

    Args:
        politician_trades: dataframe containing the politician trades
        cutoff_date: String representing earliest date
        stock_data: Dataframe containing stock data
        groupby_column: String representing calculating holding 
                        for actual trades or copy trades
    
    Returns:
        Dataframe representing politiican or copy traded holdings
        with ROI calculated
    """
    holding = holdings(politician_trades, cutoff_date, groupby_column=groupby_column)
    holding = holding.merge(stock_data, left_on=['Date', 'Ticker'], right_on=['Date', 'Ticker'])
    holding["StockValue"] = holding["StockAmount"] * holding["Close"]
    holding['TotalValue'] = holding.groupby('Date')['StockValue'].transform('sum')
    holding['ROI'] = holding['StockValue'] / holding['TotalValue'] * holding['DailyROI']
    return holding

def create_portfolio_roi(politician_trades, stock_data, cutoff_date, end_date=None):
    """
    Combines S&P500, Politiican ROI, and copy-traded ROI in one dataframe

    Args:
        politician_trades: dataframe containing the politician trades
        cutoff_date: String representing earliest date
        stock_data: Dataframe containing stock data
        end_date: String representing end date

    Returns:
        Final dataframe with cumulative ROI
    """
    politician_holdings = calculate_portfolio_roi(politician_trades, cutoff_date, stock_data, "TransactionDate")
    copytraded_holdings = calculate_portfolio_roi(politician_trades, cutoff_date, stock_data, "ReportDate")

    spy_data = yf.download("SPY", start=cutoff_date, end=end_date, auto_adjust=True, rounding=True, progress=False)
    spy_data["DailyROI"] = spy_data["Close"].pct_change().fillna(0) + 1.0
    spy_data["SPYCumROI"] = spy_data["DailyROI"].cumprod()
    spy_data.reset_index(inplace=True)
    final = spy_data[["Date", "SPYCumROI"]]

    # Select relevant columns from politician and copytraded holdings
    politician_holdings = politician_holdings[["Date", "ROI", "StockValue"]]
    copytraded_holdings = copytraded_holdings[["Date", "ROI", "StockValue"]]

    # Rename columns for merging
    copytraded_holdings.rename(columns={"ROI": "CopyTradeROI"}, inplace=True)

    # Merge all DataFrames on the 'Date' column
    final = final.merge(politician_holdings.groupby('Date')['ROI'].sum().reset_index(), on="Date", how="left")
    final = final.merge(copytraded_holdings.groupby('Date')['CopyTradeROI'].sum().reset_index(), on="Date", how="left")

    final['CopyTradeROI'] = final['CopyTradeROI'].fillna(1.0)
    final["CopyCumulativeROI"] = final["CopyTradeROI"].cumprod()

    final['ROI'] = final['ROI'].fillna(1.0)
    final["CumulativeROI"] = final["ROI"].cumprod()

    return final

def calculate_returns(politician_name, file_path, cutoff_date = pd.to_datetime('2019-01-01')):
    """
    Calculate the returns of politician, copy trading, and S&P500

    Args:
        politician_name: String representing name of politician
        cutoff_date: cutoff date for trade analysis

    Returns:
        Dataframe with cumulative ROI of portfolio, copytrade and S&P500
    """
    df = load_transactions(file_path)
    df = clean_transactions(df, cutoff_date, renamed_stocks)
    politician_trades = choose_politician(df, politician_name)
    cutoff_date = politician_trades.iloc[0]["TransactionDate"]
    stock_data = download_stock_data(politician_trades, cutoff_date)
    politician_trades = add_stock_amount_column(politician_trades, stock_data)

    return create_portfolio_roi(politician_trades, stock_data, cutoff_date)

portfolio_roi = calculate_returns("William R. Keating", "congress_trades.csv")

plt.figure(figsize=(12, 6))
plt.plot(portfolio_roi['Date'], portfolio_roi['CumulativeROI'], label='Actual ROI')
plt.plot(portfolio_roi['Date'], portfolio_roi['CopyCumulativeROI'], label='Copy Trade ROI')
plt.plot(portfolio_roi['Date'], portfolio_roi['SPYCumROI'], label='SPY ROI')
plt.xlabel('Date')
plt.ylabel('Cumulative ROI')
plt.title('Actual ROI vs Copy Trade ROI')
plt.legend()
plt.grid(True)
plt.show()
