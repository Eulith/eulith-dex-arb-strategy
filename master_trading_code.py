from __future__ import print_function

import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import datetime

import boto3
from eulith_web3.kms import KmsSigner

from eulith_web3.eulith_web3 import *
from eulith_web3.signing import construct_signing_middleware, LocalSigner


# --- GLOBAL VARIABLES ---
wallet = LocalSigner("...") #PRIVATE KEY REPLACES ...
network_url = "https://eth-main.eulithrpc.com/v0"
ew3 = EulithWeb3(eulith_url=network_url,
                 eulith_refresh_token="eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzI1NksifQ.eyJzdWIiOiJyaHNlZGRpZWh1YW5nIiwiZXhwIjoxNzA4MjAyNTgxLCJzb3VyY2VfaGFzaCI6IioiLCJzY29wZSI6IkFQSVJlZnJlc2gifQ.lmv8--6ShQe1jw6vp7cEWjp4sfrdZIg4W_Umn2VE8xhMGMdOl2ZwmPPm_FyFbqvOO-Ow6sWnDCAq2cTxJdalLRs",
                 signing_middle_ware=construct_signing_middleware(wallet))

weth = ew3.eulith_get_erc_token(TokenSymbol.WETH)
usdt = ew3.eulith_get_erc_token(TokenSymbol.USDT)
usdc = ew3.eulith_get_erc_token(TokenSymbol.USDC)
link = ew3.eulith_get_erc_token(TokenSymbol.LINK)
matic = ew3.eulith_get_erc_token(TokenSymbol.MATIC)
bnb = ew3.eulith_get_erc_token(TokenSymbol.BNB)
busd = ew3.eulith_get_erc_token(TokenSymbol.BUSD)
steth = ew3.eulith_get_erc_token(TokenSymbol.STETH)
matic = ew3.eulith_get_erc_token(TokenSymbol.MATIC)
ldo = ew3.eulith_get_erc_token(TokenSymbol.LDO)
crv = ew3.eulith_get_erc_token(TokenSymbol.CRV)
cvx = ew3.eulith_get_erc_token(TokenSymbol.CVX)
badger = ew3.eulith_get_erc_token(TokenSymbol.BADGER)
bal = ew3.eulith_get_erc_token(TokenSymbol.BAL)
oneinch = ew3.eulith_get_erc_token(TokenSymbol.ONEINCH)
uni = ew3.eulith_get_erc_token(TokenSymbol.UNI)
ape = ew3.eulith_get_erc_token(TokenSymbol.APE)
gmt = ew3.eulith_get_erc_token(TokenSymbol.GMT)


# ------------------------
def print_trade_summary(SELL_AMOUNT: int, SELL_TOKEN, buy_leg,
                        spread_in_sell_token_units,
                        gas_cost_in_sell_token):
    print('\n~~~~~~~~~~~~~TRADE SUMMARY~~~~~~~~~~~~~~~~~')
    print(f"Started with: {SELL_AMOUNT} of {SELL_TOKEN.address}")
    print(f"Ending with: {buy_leg} of {SELL_TOKEN.address}")
    print(f"Profit: {spread_in_sell_token_units} sell tokens")
    print(f"Gas cost (sell token): {gas_cost_in_sell_token}")


def fund_toolkit_contract_if_needed(proxy_amount: float, proxy_token,
                                    proxy_token_decimals: int):

    """
    Funds the toolkit contract if the balance is insufficient. proxy_token's type is Union[EulithERC20, EulithWETH]


    :param proxy_amount: The amount of the proxy token to be used in the trade.
    :type proxy_amount: float
    :param proxy_token: The token that is used as the proxy. Its type can be either EulithERC20 or EulithWETH.
    :type proxy_token: Union[EulithERC20, EulithWETH]
    :param proxy_token_decimals: The number of decimals for the proxy token.
    :type proxy_token_decimals: int

    :return: None
    :rtype: None
    """
    # create toolkit contract if it doesn't exist already
    ew3.eulith_create_contract_if_not_exist(wallet.address)

    # --- Fund Proxy Contract IF Insufficient Sell Token ---- #
    proxy_contract_address = ew3.eulith_contract_address(wallet.address)
    print("Proxy contract address is: {}".format(proxy_contract_address))
    sell_token_proxy_balance = proxy_token.balance_of(proxy_contract_address)
    # print(f"Sell token proxy balance is: {sell_token_proxy_balance}")
    sell_token_proxy_balance = sell_token_proxy_balance / proxy_token_decimals

    print("Proxy balance is {}".format(sell_token_proxy_balance))

    if sell_token_proxy_balance < proxy_amount:
        print(f"Funding toolkit contract...")
        if proxy_token.address == "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2":  # WETH address
            print("Sell token address is WETH, converting ETH to WETH")
            # convert eth to weth to prepare for the swap
            # eth_to_weth_tx = weth.deposit_eth(proxy_amount)
            eth_to_weth_tx = weth.deposit_wei(int(proxy_amount * proxy_token_decimals))
            eth_to_weth_tx['from'] = wallet.address

            print(f"Proxy amount is: {proxy_amount}")
            print(f"Wallet address is: {wallet.address}")

            gas_max_priority_fee = 7000000000 # 5 Gwei, minner tip (in addition to base price)
            max_gas_price = 35000000000 # 35 Gwei
            eth_to_weth_tx['maxFeePerGas'] = int(max_gas_price)
            eth_to_weth_tx['maxPriorityFeePerGas'] = gas_max_priority_fee

            rec = ew3.eth.send_transaction(eth_to_weth_tx)
            receipt = ew3.eth.wait_for_transaction_receipt(rec)

        amount_to_send_in_sell_token = proxy_amount - sell_token_proxy_balance
        print("Funding Proxy with {} in token type {}".format(amount_to_send_in_sell_token, proxy_token.address))
        tx = proxy_token.transfer(proxy_contract_address, int(amount_to_send_in_sell_token * proxy_token_decimals))
        tx['from'] = wallet.address

        rec = ew3.eth.send_transaction(tx)
        receipt = ew3.eth.wait_for_transaction_receipt(rec)

        print(f"Funding Proxy hash: {receipt['transactionHash'].hex()}")

    else:
        print("Proxy balance does not need funding.")
    # --------------------------- #


def create_list_of_token_pair_tuples(base_token, tokens):
    """
    Here I am using nested for loops to get the grid of all possible tuple combinations of the token objects from tokens,
    which is 136 combinations. There are 17 coins currently, can't pair with itself so 16 coins it can pair with,
    resulting in pairing a with b then b with a, so dividing by 2 to eliminate duplicates. aka 17 choose 2.

    :param base_token: The base token to be used.
    :type base_token: Union[EulithERC20, EulithWETH]
    :param tokens: The list of tokens.
    :type tokens: List[Union[EulithERC20, EulithWETH]]
    :return: A list of token pair tuples.
    :rtype: List[Tuple[Union[EulithERC20, EulithWETH]]]
    """

    if tokens == None:
        tokens = get_list_of_all_tokens()

    pairs = []

    if base_token:
        print(f"\nCreating list of tuples with base token: {base_token.address}")
        for i in range(len(tokens)):
            pairs.append((base_token, tokens[i]))

    else:
        print(f"\nCreating list of tuples without base token representing all possible combinations")
        for i in range(len(tokens)):
            for j in range(i + 1, len(tokens)):
                pairs.append((tokens[i], tokens[j]))

    return pairs


def create_list_of_only_usdc_pair_tuples():
    '''
    Creating a list of pairs (as tuples), where the first element in tuple is USDC and the second is another token
    All tokens defined as global variables should be in the tokens list (except usdc)
    '''

    usdc = ew3.eulith_get_erc_token(TokenSymbol.USDC)
    return create_list_of_token_pair_tuples(usdc, None)


def create_short_list_of_token_pair_tuples():
    """
    Returns a list of token pair tuples that includes ETH, USDT, and USDC.

    :return: List of token pair tuples.
    :rtype: List[Tuple[str, str]]
    """

    tokens = [weth, usdt, usdc]
    return create_list_of_token_pair_tuples(None, tokens)


def get_list_of_all_dexs():
    """
    Returns a list of all supported decentralized exchanges.

    :return: List of all supported decentralized exchanges.
    :rtype: List[str]
    """

    dexs = [EulithLiquiditySource.UNISWAP_V3,
            EulithLiquiditySource.BALANCER_V2,
            EulithLiquiditySource.SUSHI,
            EulithLiquiditySource.COMPOUND,
            EulithLiquiditySource.PANCAKE,
            EulithLiquiditySource.CURVE_V2,
            EulithLiquiditySource.CURVE_V1,
            EulithLiquiditySource.SADDLE,
            EulithLiquiditySource.SYNAPSE,
            EulithLiquiditySource.BALANCER_V1]

    return dexs


def get_list_of_all_tokens():
    """
    Returns a list of all supported tokens.

    :return: List of all supported tokens.
    :rtype: List[str]
    """

    # These are Python bindings around the whole ERC20 contract.
    tokens = [weth, usdt, usdc, link, matic, bnb, busd, steth, ldo, crv, cvx, badger, bal, oneinch, uni, ape, gmt]
    return tokens


def get_min_dex(SELL_TOKEN, BUY_TOKEN, SELL_AMOUNT, dexs, aggregator=None):
    """
    Get the best price and associated DEX for a given token pair and sell amount.

    :param sell_token: address of the token to be sold
    :param buy_token: address of the token to be bought
    :param sell_amount: amount of sell_token to be sold
    :param decentralized_exchanges: array of DEX names to check
    :param aggregator: name of aggregator to route through (optional)
    :return: dictionary with the best DEX, price, and swap transactions
    """
    INITIAL_PRICE = 2e16

    # INITAL_PRICE is used to guarantee that the first iteration of the loop will replace the value with a real price obtained from the decentralized exchange
    min_dex = {"dex": 0, "price": INITIAL_PRICE, "txs": []}

    for dex in dexs:
        print(f'Requesting buy leg quote from: {dex}')
        # set the swap parameters
        swap_params = -1

        if aggregator == None:
            swap_params = EulithSwapRequest(
                sell_token=SELL_TOKEN,
                buy_token=BUY_TOKEN,
                sell_amount=SELL_AMOUNT,
                liquidity_source=dex,
                recipient=ew3.eulith_contract_address(wallet.address)
            )
        else:
            swap_params = EulithSwapRequest(
                sell_token=SELL_TOKEN,
                buy_token=BUY_TOKEN,
                sell_amount=SELL_AMOUNT,
                liquidity_source=dex,
                recipient=ew3.eulith_contract_address(wallet.address),
                route_through=aggregator)

        try:
            # this is just to make it easy to read later
            # get a swap quote
            # txs is an array of transactions that make up the swap
            buy_leg_price, buy_leg_txs = ew3.eulith_swap_quote(swap_params)

            # get the min price and associated DEX
            if (buy_leg_price != None) and buy_leg_price < min_dex["price"]:
                min_dex["dex"] = dex
                min_dex["price"] = buy_leg_price
                min_dex["txs"] = buy_leg_txs

        except EulithRpcException:
            continue

    return min_dex


def get_max_dex(SELL_TOKEN, BUY_TOKEN, SELL_AMOUNT, dexs, aggregator=None):
    """
    Loops over the `decentralized_exchanges` and we find the best quote for selling `sell_token` for `buy_token`
    by sending a request for a swap quote using the `eulith_swap_quote` method.

    :param sell_token: An instance of the token that you want to sell.
    :param buy_token: An instance of the token that you want to buy.
    :param sell_amount: The amount of `sell_token` that you want to sell.
    :param decentralized_exchanges: A list of decentralized exchanges to query for quotes.
    :param aggregator: (optional) An instance of an aggregator to route the swap through.
    :return: A dictionary containing the best quote found from the decentralized exchanges, with keys:
        - `dex`: The address of the decentralized exchange where the best quote was found.
        - `price`: The price for selling `sell_token` for `buy_token` in units of `buy_token`.
        - `txs`: A list of transactions required to complete the swap.
    """

    INITIAL_PRICE = 2e16 # INITAL_PRICE is used to guarantee that the first iteration of the loop will replace the value with a real price obtained from the decentralized exchange
    max_dex = {"dex": 0, "price": INITIAL_PRICE, "txs": []}

    for dex in dexs:
        print(f'Requesting sell leg quote from: {dex}')
        swap_params = -1

        if aggregator == None:
            swap_params = EulithSwapRequest(
                sell_token=BUY_TOKEN,
                buy_token=SELL_TOKEN,
                sell_amount=SELL_AMOUNT,
                liquidity_source=dex)
        else:
            swap_params = EulithSwapRequest(
                sell_token=BUY_TOKEN,
                buy_token=SELL_TOKEN,
                sell_amount=SELL_AMOUNT,
                liquidity_source=dex,
                route_through=aggregator)

        try:
            sell_leg_price, sell_leg_txs = ew3.eulith_swap_quote(swap_params)
            if sell_leg_price < max_dex["price"]:
                max_dex["dex"] = dex
                max_dex["price"] = sell_leg_price
                max_dex["txs"] = sell_leg_txs

        except EulithRpcException:
            continue

    return max_dex



def get_0x_gas_cost_in_gwei():
    endpoint = "https://api.0x.org/swap/v1/quote"
    params = {
        "sellToken": "0x6B3595068778DD592e39A122f4f5a5cF09C90fE2",
        "buyToken": "0xb9871cB10738eADA636432E86FC0Cb920Dc3De24",
        "sellAmount": "1000000000000000000"
    }

    response = requests.get(endpoint, params=params)
    data = response.json()

    # Extracting gas price and estimated gas limit
    gas_price = data["gasPrice"] #live 0x gas price
    gas_limit = data["gas"] #this is the 0x estimated quantity of gas needed to guaranteee transaction execution
    WEI_AND_GWEI_CONVERSION_RATE = 10e9

    gas_cost_in_gwei = (int(gas_price)*int(gas_limit))/WEI_AND_GWEI_CONVERSION_RATE
    return gas_cost_in_gwei

def get_1inch_gas_cost_in_gwei():
    endpoint = "https://api.1inch.io/v5.0/1/swap"
    params = {
            "fromTokenAddress": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
            "toTokenAddress": "0x111111111117dc0aa78b770fa6a738034120c302",
            "amount": "10000000000000000",
            "fromAddress": "0xBAFe448C52BFA4C64bA9671DF5ceb3bE1188b962",
            "slippage": "1"
    }
    response = requests.get(endpoint, params=params)
    data = response.json()

    # Extracting gas price and estimated gas limit
    gas_price = int(data["tx"]["gasPrice"])
    gas_limit = int(data["tx"]["gas"])
    WEI_AND_GWEI_CONVERSION_RATE = 10e9

    gas_cost_in_gwei = (gas_price * gas_limit) / WEI_AND_GWEI_CONVERSION_RATE
    return gas_cost_in_gwei

def get_gas_usage_given_aggregator(aggregator: EulithSwapProvider) -> int:
    '''
    Given an aggregator from the EulithSwapProvider enumeration, returns the estimated gas usage.

    :param aggregator: An enumeration member of EulithSwapProvider representing the aggregator to use.
    :return: An int representing the estimated gas usage.
    '''
    gas_usage = -1  # initiate variable to check later, reject txn if wrong
    if aggregator == EulithSwapProvider.ZERO_EX:
        zerox_gas_cost = get_0x_gas_cost_in_gwei()
        gas_usage = zerox_gas_cost
    elif aggregator == EulithSwapProvider.ONE_INCH:
        oneinch_gas_cost = get_1inch_gas_cost_in_gwei()
        gas_usage = oneinch_gas_cost
    else:
        print("!! Gas calculation ERROR. !!")
        exit(1)

    return gas_usage


def get_gas_cost_in_sell_token(aggregator, max_gas_price, sell_token, buy_token):
    """
    Calculate the gas cost for a given transaction, in terms of the sell token. We calculate the gas cost of a transaction given a maximum gas price and the sell token. The
    gas cost is returned in terms of the sell token. If the sell token is WETH, then the gas cost is returned
    in ETH. If the sell token is not WETH, the price of the sell token to WETH is first calculated, and then the
    gas cost is calculated in terms of the sell token.

    :param aggregator: The aggregator to use for the transaction.
    :param max_gas_price: The maximum gas price to pay for the transaction.
    :param sell_token: The sell token for the transaction.
    :param buy_token: The buy token for the transaction.
    :return: The gas cost of the transaction in terms of the sell token.
    """
    WEI_AND_ETH_CONVERSION_RATE = 1e18
    gas_usage = get_gas_usage_given_aggregator(aggregator)
    # convert max_gas_price from wei to ETH: 1 ETH → 10^18 Wei and 1 Gwei → 10^9 Wei
    # calculation of the gas cost in the sell token requires knowing the price of the sell token to ETH. If the sell token is WETH, then the calculation is done in ETH, so the conversion back to wei is unnecessary, which is why we divide by 1e18 first
    max_gas_price = max_gas_price / WEI_AND_ETH_CONVERSION_RATE
    gas_cost_in_eth = max_gas_price * gas_usage

    # convert max_gas_price back to wei
    max_gas_price = max_gas_price * WEI_AND_ETH_CONVERSION_RATE

    if sell_token.address != "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2":
        # if the sell token is not WETH, calculate the price of the sell token to WETH
        print(f"sell_token is not WETH")

        # get the price of the sell token to WETH
        swap_params = EulithSwapRequest(
            sell_token=sell_token,
            buy_token=weth,
            sell_amount=1.0  # value doesn't matter here
        )

        try:
            sell_token_to_eth_price, txs = ew3.eulith_swap_quote(swap_params)
        except EulithRpcException as e:
            print(f"An error occurred while fetching the price for {sell_token.address}: {e}")
            sell_token_to_eth_price = 0

        # calculate the gas cost in terms of the sell token
        gas_cost_in_sell_token = gas_cost_in_eth * sell_token_to_eth_price

        # if the sell token to ETH price is zero, then the sell token may not be supported by any liquidity sources
        if sell_token_to_eth_price == 0:
            gas_cost_in_sell_token = 0

    else:
        # if the sell token is WETH, skip the pricing and calculation steps
        gas_cost_in_sell_token = gas_cost_in_eth

    return gas_cost_in_sell_token


if __name__ == '__main__':
    print("Hello World- The New World Order is Beginning...")