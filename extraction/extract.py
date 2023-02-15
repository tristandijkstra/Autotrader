import time
from binance.client import Client
from datetime import datetime, timedelta
import pandas as pd
import pandas_ta as ta
from tqdm import tqdm as tqdm
from copy import deepcopy
import os

import extraction.generalValues as gv


def readKeys(keyfile: str, testnet: bool = False) -> Client:
    """Reads binance api keys

    Args:
        keyfile (str): keyfile path, file must have apikey on the first line and api-secret on the second.

    Returns:
        Client: Binance client object
    """
    kf = open(keyfile, "r")
    api_key, api_secret = kf.read().split("\n")
    kf.close()
    client = Client(api_key, api_secret, testnet=testnet)
    return client


def getHistoricalData(
    client, ticker: str, start: datetime, end: datetime, interval: str
) -> pd.DataFrame:
    """Retrieves historical data for single ticker from binance and returns it as a pandas dataframe


    Args:
        client (binance.client.Client): binance client object from readKeys()
        ticker (str): market ticker e.g. BNBUSDT
        start (datetime): start date in datetime format: datetime(2022,1,1,...)
        end (datetime): end date in datetime format: datetime(2022,1,1,...)
        interval (str): interval to retrieve data for: "1m", "1d" etc see options in generalValues

    Returns:
        pd.DataFrame: _description_
    """
    klines = client.get_historical_klines(ticker, interval, start, end)

    P = pd.DataFrame(klines, columns=gv.klinesIndices)

    # convert interval to pandas standard for filling gaps
    # pdInterval = interval.replace("m", "T").replace("h", "H")
    # dates = pd.date_range(start=start, end=end, freq=pdInterval)

    # Drop unnecessary columns and handle datetime
    P = (
        P.drop(["quote asset volume", "close time", "?", "??", "???"], axis=1)
        .assign(timestamp=lambda x: pd.to_datetime(x.timestamp-(time.timezone*2000), unit="ms"))
        .set_index("timestamp")
        .astype(float)
        # Handle missing dates
        # .reindex(dates)
        .fillna(method="ffill")
        # Another one if 1st value is missing:
        .fillna(-1)
    )

    return P


def genIndicatorsFromList(P: pd.DataFrame, indicators: list) -> pd.DataFrame:
    """Generates indicators from a list and adds them to the price data Dataframe

    Args:
        P (DataFrame): price data Dataframe
        indicators (list): list indicators in the form EMA40

    Returns:
        P (DataFrame): The price data Dataframe with the various indicators added to it.
    """
    for indicator in indicators:
        if indicator == "MACD":
            P.ta.macd(append=True)
        elif indicator == "OBV":
            P.ta.obv(append=True)
        elif indicator[0:3] == "EMA":
            length = int(indicator[3::])
            P.ta.ema(length=length, append=True)
        elif indicator[0:3] == "SMA":
            length = int(indicator[3::])
            P.ta.sma(length=length, append=True)
        elif indicator[0:3] == "RSI":
            length = int(indicator[3::])
            P.ta.rsi(length=length, append=True)
        elif indicator[0:6] == "BBANDS":
            length = int(indicator[6::])
            P.ta.bbands(length=length, append=True)
        elif indicator[0:6] == "ZSCORE":
            length = int(indicator[6::])
            P.ta.zscore(length=length, append=True)
        elif indicator[0:5] == "SLOPE":
            length = int(indicator[5::])
            P.ta.slope(length=length, append=True)
        else:
            print("Failure in adding indicator")

    return P


def genIndicatorsMultiple(dat: dict, timeFrame: str, indicators: list) -> dict:
    """generate indicators for a datadict

    Args:
        dat (dict): datadict in default format
        timeFrame (str): timeframe 1m 15m etc
        indicators (list): list of indicators to add

    Returns:
        dict: datadict with indicators
    """
    datTemp = deepcopy(dat)
    for key in list(datTemp.keys()):
        keyTimeframe = key.split("_")[1]
        if keyTimeframe == timeFrame:
            datTemp[key] = genIndicatorsFromList(datTemp[key], indicators)
    return datTemp


def generateBTData(
    dataSetName: str,
    client,
    coins: str,
    pair: str,
    intervals: list,
    start: datetime,
    end: datetime,
    rootfolderName: str = "data",
    forceRegen: bool = False,
    save: bool = True,
) -> dict:
    """Genereates and returns date from binance API for Backtester

    Args:
        dataSetName (str): name of dataset to save under.
        folderName (str, optional): default save rootfolder. Defaults to "data".

    Returns:
        dict: dictionary of all datasets.
    """
    saveLocation = f"{rootfolderName}/{dataSetName}"

    if not os.path.exists(saveLocation) and save:
        os.makedirs(saveLocation)

    dat = {}
    for coin in tqdm(coins):
        ticker = coin + pair
        for interval in intervals:
            datID = f"{ticker}_{interval}"
            if not os.path.exists(f"{saveLocation}/{datID}.csv") or forceRegen:
                # print(f"\nGetting data for: {datID}:")
                temp = getHistoricalData(client, ticker, start, end, interval)
                if save:
                    temp.to_csv(f"{saveLocation}/{datID}.csv")
                dat[datID] = temp
            else:
                temp = pd.read_csv(
                    f"{saveLocation}/{datID}.csv",
                    header=0,
                    index_col=0,
                    parse_dates=[0],
                )
                temp = temp.assign(
                    index=lambda x: pd.to_datetime(x.index)
                )  # , format=dform))
                dat[datID] = temp
    return dat


def initBotData(
    client, coins: list, intervals: list, pair: str, hours: int = 9
) -> dict:
    """wrapper of getHistorical to retrieve starting data for cryptobot

    Args:
        client (): binance client object
        coins (list): list of coins ["ICP","XLM"] etc
        intervals (list): list of intervals ["1m", "1h"] etc
        pair (str): pair to trade with BTC etc
        hours (int, optional): hours of data to start with. Defaults to 9.

    Returns:
        dict: _description_
    """
    end = datetime.utcnow().replace(microsecond=0, second=0)
    start = end - timedelta(hours=hours)
    print(start, end)
    dat = generateBTData(
        "cryptobot", client, coins, pair, intervals, str(start), str(end), save=False
    )
    return dat


if __name__ == "__main__":
    print("Run from test file")
    c = readKeys()
    start = str(datetime(2022, 2, 1))
    end = str(datetime(2022, 2, 2))
    intervals = ["1m", "15m", "1h"]
    pair = "BTC"
    coins = ["XLM"]
    dataSetName = "testhello"

    a = initBotData(c, coins, intervals, pair, hours=9)
