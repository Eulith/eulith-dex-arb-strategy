# Let's start by executing small profitable trades from and back to USDC

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
from eulith_web3.signing import construct_signing_middleware

import config
import master_trading_code as mtc

if __name__ == '__main__':
    print("Hello World - starting small USDC arb script...")

    wallet = config.wallet
    ew3 = config.ew3

    print(f"Wallet address is {wallet.address}")

     # deploy the Eulith proxy contract
    ew3.eulith_create_contract_if_not_exist(wallet.address)

    asset_pairs = mtc.create_list_of_only_usdc_pair_tuples()
    dexs = mtc.get_list_of_all_dexs()
    aggregator = EulithSwapProvider.ONE_INCH


    SELL_AMOUNT = 100
    SELL_TOKEN_DECIMALS = 1e6
    GAS_MAX_PRIORITY_FEE = 5000000000 # 5 Gwei, minner tip (in addition to base price)
    MAX_GAS_PRICE = 35000000000 # 35 Gwei

    usdc = ew3.eulith_get_erc_token(TokenSymbol.USDC)

    for asset_pair in asset_pairs:
        SELL_TOKEN = asset_pair[0] # the [0] is getting the single asset at index 0 from the asset_pair
        BUY_TOKEN = asset_pair[1]

        if(SELL_TOKEN.address != usdc.address):
            print(f"Sell token is not USDC, it is: {SELL_TOKEN.address}. Exiting...")
            exit(1)

        print(f"Sell token is: {SELL_TOKEN.address}. Buy token is: {BUY_TOKEN.address}")

        mtc.fund_toolkit_contract_if_needed(SELL_AMOUNT, SELL_TOKEN, SELL_TOKEN_DECIMALS)

        min_dex = mtc.get_min_dex(SELL_TOKEN, BUY_TOKEN, SELL_AMOUNT, dexs, aggregator)
        if min_dex == None: 
            print("Error getting min_dex. LOC 385")
            exit(1)

        # compute input to second leg
        sell_amount_of_buy_token = round(SELL_AMOUNT / min_dex["price"], 17)

        # probably need to add in swap fees

        max_dex = mtc.get_max_dex(SELL_TOKEN, BUY_TOKEN, sell_amount_of_buy_token, dexs, aggregator)
        if max_dex == None: 
            print("Error getting min_dex. LOC 398")
            exit(1)

        gas_cost_in_sell_token = mtc.get_gas_cost_in_sell_token(aggregator, MAX_GAS_PRICE, SELL_TOKEN, BUY_TOKEN)

        # check profitability condition
        buy_leg = sell_amount_of_buy_token / max_dex["price"]    # the amount of sell_token resulting from buy_token sell
        spread_in_sell_token_units = (buy_leg - SELL_AMOUNT)  # positive if profitable

        profitability = spread_in_sell_token_units - gas_cost_in_sell_token

        if(profitability > 0):
            ew3.eulith_start_transaction(wallet.address)
            ew3.eulith_send_multi_transaction(min_dex["txs"])
            ew3.eulith_send_multi_transaction(max_dex["txs"])

            mtc.print_trade_summary(SELL_AMOUNT, SELL_TOKEN, buy_leg,
                                spread_in_sell_token_units, 
                                gas_cost_in_sell_token)
            
            atomic_tx = ew3.eulith_commit_transaction()

            # setting the gas limit
            atomic_tx['maxFeePerGas'] = int(MAX_GAS_PRICE)
            atomic_tx['maxPriorityFeePerGas'] = GAS_MAX_PRIORITY_FEE
            atomic_tx['gas'] = mtc.get_gas_usage_given_aggregator(aggregator)

            # send the transaction!
            tx = ew3.eth.send_transaction(atomic_tx)
            receipt = ew3.eth.wait_for_transaction_receipt(tx)
            print(f"!! TRANSACTION EXECUTED !!\nWith receipt: {receipt['transactionHash'].hex()}")
           
            mtc.write_trade_to_gsheet(receipt, spread_in_sell_token_units,
                                        min_dex, max_dex, asset_pair[0],
                                        asset_pair[1], gas_cost_in_sell_token)

        else:
            print(f"Transaction not executed; spread is {spread_in_sell_token_units}, gas is {gas_cost_in_sell_token}")
            print(f"The sell_token right now is:",asset_pair[0].address)
            print(f"The buy_token right now is:",asset_pair[1].address)
      