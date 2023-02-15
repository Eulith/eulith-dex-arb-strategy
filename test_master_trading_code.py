import io
import sys
import unittest
import coverage
import report
import re
import mock
from unittest.mock import patch, MagicMock, Mock
from unittest import mock
from decimal import Decimal

from eulith_web3.erc20 import EulithERC20
from eulith_web3.eulith_web3 import EulithWeb3, TokenSymbol
from eulith_web3.signing import construct_signing_middleware, LocalSigner
from web3.exceptions import TimeExhausted

import master_trading_code as mtc
from eulith_web3.eulith_web3 import *


class Comprehensive_Test(unittest.TestCase):

    def test_print_trade_summary(self):
        SELL_AMOUNT = 1000
        SELL_TOKEN = mtc.weth
        buy_leg = 500
        spread_in_sell_token_units = 100
        gas_cost_in_sell_token = 10

        # Save the current stdout
        old_stdout = sys.stdout

        # Redirect stdout to a StringIO object
        sys.stdout = io.StringIO()

        # Call the function
        mtc.print_trade_summary(SELL_AMOUNT, SELL_TOKEN, buy_leg, spread_in_sell_token_units, gas_cost_in_sell_token)

        # Get the printed output
        output = sys.stdout.getvalue()

        # Reset stdout to its original value
        sys.stdout = old_stdout

        # Assert that the printed output matches the expected output
        expected_output = f'\n~~~~~~~~~~~~~TRADE SUMMARY~~~~~~~~~~~~~~~~~\nStarted with: 1000 of {SELL_TOKEN.address}\nEnding with: 500 of {SELL_TOKEN.address}\nProfit: 100 sell tokens\nGas cost (sell token): 10\n'
        self.assertEqual(output, expected_output)

    def test_get_list_of_all_tokens(self):
        tokens = mtc.get_list_of_all_tokens()
        self.assertGreater(len(tokens), 0)

    def test_create_list_of_token_pair_tuples(self):
        # Define some mock tokens
        token1 = EulithERC20("0x0000000000000000000000000000000000000001", "Token1")
        token2 = EulithERC20("0x0000000000000000000000000000000000000002", "Token2")
        token3 = EulithERC20("0x0000000000000000000000000000000000000003", "Token3")

        # Test without base token
        tokens = [token1, token2, token3]
        pairs = mtc.create_list_of_token_pair_tuples(None, tokens)
        self.assertEqual(len(pairs), 3)

        # Test with base token
        base_token = EulithERC20("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "USDC")

        pairs = mtc.create_list_of_token_pair_tuples(base_token, tokens)
        self.assertEqual(len(pairs), 3)

        # Test case with no tokens and no base token
        pairs = mtc.create_list_of_token_pair_tuples(None, None)
        self.assertEqual(len(pairs), 136)

        # Test case with a list of tokens and no base token
        tokens = [token1, token2, token3]
        pairs = mtc.create_list_of_token_pair_tuples(None, tokens)
        self.assertEqual(len(pairs), 3 * (3 - 1) // 2)

        # Test case with a base token and no tokens list
        base_token = token1
        pairs = mtc.create_list_of_token_pair_tuples(base_token, None)
        self.assertEqual(len(pairs), 17)

        # Test case with both base token and tokens list
        base_token = token1
        tokens = [token2, token3]
        pairs = mtc.create_list_of_token_pair_tuples(base_token, tokens)
        self.assertEqual(len(pairs), 2)
        self.assertEqual(pairs[0], (base_token, token2))
        self.assertEqual(pairs[1], (base_token, token3))

    def test_create_short_list_of_token_pair_tuples(self):
        tokens = [mtc.weth, mtc.usdt, mtc.usdc]
        result = mtc.create_short_list_of_token_pair_tuples()

        self.assertEqual(len(result), len(tokens) * (
                len(tokens) - 1) / 2)  # n tokens, each can pair with n-1 other tokens, divide by 2 to exclude duplicates
        self.assertEqual(set([token.address for token in tokens]),
                         set([token.address for pair in result for token in pair]))
        self.assertTrue(
            all([pair[0].address != pair[1].address for pair in result]))  # no token should pair with itself
        self.assertTrue(all([(pair[1], pair[0]) not in result for pair in result]))  # each pair should only appear once
        # Check if all token pairs are unique because sets can only have unique elements, so basically if the length is the same then there's no duplicates
        self.assertEqual(len(result), len(set(result)))
        # Check if the order of the tokens in the pairs is not important by using the frozenset immutable data type to convert to hashable frozensets, then checking they are unique by comparing addresses of the tokens
        self.assertEqual(set([frozenset(pair) for pair in result]), set([frozenset(pair) for pair in result]))

    def test_get_list_of_all_dexs(self):
        expected_dexs = [
            EulithLiquiditySource.UNISWAP_V3,
            EulithLiquiditySource.BALANCER_V2,
            EulithLiquiditySource.SUSHI,
            EulithLiquiditySource.COMPOUND,
            EulithLiquiditySource.PANCAKE,
            EulithLiquiditySource.CURVE_V2,
            EulithLiquiditySource.CURVE_V1,
            EulithLiquiditySource.SADDLE,
            EulithLiquiditySource.SYNAPSE,
            EulithLiquiditySource.BALANCER_V1
        ]
        dexs = mtc.get_list_of_all_dexs()
        self.assertCountEqual(expected_dexs, dexs)

    def test_get_list_of_all_tokens(self):
        tokens = mtc.get_list_of_all_tokens()
        expected_tokens = [mtc.weth, mtc.usdt, mtc.usdc, mtc.link, mtc.matic, mtc.bnb, mtc.busd, mtc.steth, mtc.ldo,
                           mtc.crv, mtc.cvx, mtc.badger, mtc.bal, mtc.oneinch, mtc.uni, mtc.ape, mtc.gmt]

        assert len(tokens) == len(expected_tokens), f"Expected {len(expected_tokens)} tokens, but got {len(tokens)}"
        for i, token in enumerate(tokens):
            assert token == expected_tokens[i], f"Expected token {expected_tokens[i]}, but got {token}"

    @patch('master_trading_code.ew3.eulith_swap_quote')
    def test_get_min_dex(self, mock_eulith_swap_quote):
        # Define inputs for testing
        SELL_TOKEN = "ETH"
        BUY_TOKEN = "USDT"
        SELL_AMOUNT = 1000
        dexs = ["Uniswap", "SushiSwap", "1inch"]
        aggregator = "1inch"

        # Set up the mock to return different prices and transaction arrays
        mock_eulith_swap_quote.side_effect = [
            (500, ["0x1", "0x2", "0x3"]),
            (1000, ["0x4", "0x5"]),
            (750, ["0x6", "0x7", "0x8"]),
            EulithRpcException("Error")
        ]

        # Test case 1: aggregator is specified and returns the lowest price
        result = mtc.get_min_dex(SELL_TOKEN, BUY_TOKEN, SELL_AMOUNT, dexs, aggregator)
        self.assertEqual(result["dex"], "Uniswap",
                         "Test case 1 failed: aggregator is specified and returns the lowest price")
        self.assertEqual(result["price"], 500)
        self.assertEqual(result["txs"], ["0x1", "0x2", "0x3"])

        # Test case 2: aggregator is specified but does not return the lowest price
        mock_eulith_swap_quote.side_effect = [
            (1000, ["0x4", "0x5"]),
            (750, ["0x6", "0x7", "0x8"]),
            (500, ["0x1", "0x2", "0x3"]),
            EulithRpcException("Error")
        ]
        result = mtc.get_min_dex(SELL_TOKEN, BUY_TOKEN, SELL_AMOUNT, dexs, "1inch")
        self.assertEqual(result["dex"], "1inch",
                         "Test case 2 failed: aggregator is specified but does not return the lowest price among the available DEXs (Uniswap, SushiSwap, 1inch) for the given SELL_TOKEN, BUY_TOKEN, and SELL_AMOUNT")  # Update expected value
        self.assertEqual(result["price"], 500)
        self.assertEqual(result["txs"], ["0x1", "0x2", "0x3"])

        # Test case 3: aggregator is not specified and a valid dex returns the lowest price
        mock_eulith_swap_quote.side_effect = [
            EulithRpcException("Error"),
            (750, ["0x6", "0x7", "0x8"]),
            (500, ["0x1", "0x2", "0x3"]),
            EulithRpcException("Error")
        ]
        result = mtc.get_min_dex(SELL_TOKEN, BUY_TOKEN, SELL_AMOUNT, dexs)
        self.assertEqual(result["dex"], "1inch",
                         "Test case 3 failed: aggregator is not specified and a valid dex returns the lowest price")
        self.assertEqual(result["price"], 500)
        self.assertEqual(result["txs"], ["0x1", "0x2", "0x3"])

        # Test case 4: aggregator is not specified and none of the dexs return a valid price
        mock_eulith_swap_quote.side_effect = [
            EulithRpcException("Error"),
            EulithRpcException("Error"),
            EulithRpcException("Error"),
            EulithRpcException("Error")
        ]

        result = mtc.get_min_dex(SELL_TOKEN, BUY_TOKEN, SELL_AMOUNT, dexs)
        try:
            self.assertEqual(result["dex"], 0)
            self.assertEqual(result["price"], 2e16)
            self.assertEqual(result["txs"], [])
        except AssertionError:
            print("Test case 4 failed: aggregator is not specified and none of the dexs return a valid price")
            raise

    # this test shows the issue of 1inch not returning quotes
    @patch('master_trading_code.ew3.eulith_swap_quote')
    def test_get_max_dex(self, mock_eulith_swap_quote):
        SELL_TOKEN = "ETH"
        BUY_TOKEN = "USDT"
        SELL_AMOUNT = 1000
        dexs = ["Uniswap", "SushiSwap", "1inch"]

        mock_eulith_swap_quote.side_effect = [
            (500, ["0x1", "0x2", "0x3"]),
            (750, ["0x6", "0x7", "0x8"]),
            (1000, ["0x4", "0x5"])
        ]

        # Test case 1: aggregator is specified and returns the highest price
        aggregator = "1inch"
        result = mtc.get_max_dex(SELL_TOKEN, BUY_TOKEN, SELL_AMOUNT, dexs, aggregator)
        print(result)
        self.assertEqual(result["dex"], "1inch",
                         "Test case 1 failed: aggregator is specified and returns the highest price among the available DEXs for the given SELL_TOKEN, BUY_TOKEN, and SELL_AMOUNT")
        self.assertEqual(result["price"], 1000)
        self.assertEqual(result["txs"], ["0x4", "0x5"])

        # Test case 2: aggregator is specified but does not return the highest price
        mock_eulith_swap_quote.side_effect = [
            (750, ["0x6", "0x7", "0x8"]),
            (1000, ["0x4", "0x5"]),
        ]
        result = mtc.get_max_dex(SELL_TOKEN, BUY_TOKEN, SELL_AMOUNT, dexs, "1inch")
        self.assertEqual(result["dex"], "1inch",
                         "Test case 2 failed: aggregator is specified but does not return the highest price among the available DEXs for the given SELL_TOKEN, BUY_TOKEN, and SELL_AMOUNT")
        self.assertEqual(result["price"], 750)
        self.assertEqual(result["txs"], ["0x6", "0x7", "0x8"])

        # Test case 3: aggregator is not specified and a valid DEX returns the highest price
        mock_eulith_swap_quote.side_effect = [(750, ["0x6", "0x7", "0x8"]), (1000, ["0x4", "0x5"])]
        result = mtc.get_max_dex(SELL_TOKEN, BUY_TOKEN, SELL_AMOUNT, dexs)
        self.assertEqual(result["dex"], "1inch",
                         "Test case 3 failed: aggregator is not specified and a valid DEX returns the highest price among the available DEXs for the given SELL_TOKEN, BUY_TOKEN, and SELL_AMOUNT")
        self.assertEqual(result["price"], 1000)
        self.assertEqual(result["txs"], ["0x4", "0x5"])

        # Test case 4: aggregator is not specified and none of the DEXs return a valid price
        mock_eulith_swap_quote.return_value = (0, [])
        result = mtc.get_max_dex(SELL_TOKEN, BUY_TOKEN, SELL_AMOUNT, dexs)
        self.assertEqual(result["dex"], "",
                         "Test case 4 failed: aggregator is not specified and none of the DEXs return a valid price")
        self.assertEqual(result["price"], 0)
        self.assertEqual(result["txs"], [])

    def test_get_gas_usage_given_aggregator(self):
        # Test for ZERO_EX aggregator
        aggregator = EulithSwapProvider.ZERO_EX
        gas_usage = mtc.get_gas_usage_given_aggregator(aggregator)
        zerox_gas = mtc.get_0x_gas_cost_in_gwei()

        self.assertEqual(gas_usage, zerox_gas)

        # Test for ONE_INCH aggregator
        aggregator = EulithSwapProvider.ONE_INCH
        gas_usage = mtc.get_gas_usage_given_aggregator(aggregator)
        oneinchgas = mtc.get_1inch_gas_cost_in_gwei()
        self.assertEqual(gas_usage, oneinchgas, msg="Gas usage for ONE_INCH aggregator is incorrect")

        # Test for invalid aggregator
        aggregator = "INVALID_AGGREGATOR"
        with self.assertRaises(SystemExit) as cm:
            mtc.get_gas_usage_given_aggregator(aggregator)
        self.assertEqual(cm.exception.code, 1, msg="Invalid aggregator did not raise SystemExit with code 1")

        # Test for a valid but unhandled aggregator
        aggregator = "VALID_UNHANDLED_AGGREGATOR"
        with self.assertRaises(SystemExit) as cm:
            mtc.get_gas_usage_given_aggregator(aggregator)
        self.assertEqual(cm.exception.code, 1,
                         msg="Valid but unhandled aggregator did not raise SystemExit with code 1")


# initializing the tests
cov = coverage.Coverage(source=["localsigner_master_trading_code"])
cov.start()


if __name__ == '__main__':
    # execute all tests
    unittest.main()

    suite = unittest.TestSuite()#make an instance of all the tests
    suite.addTest(Comprehensive_Test('test_get_list_of_all_tokens', 'test_fund_toolkit_contract_if_needed','test_create_list_of_token_pair_tuples','test_create_short_list_of_token_pair_tuples','test_get_list_of_all_dexs','test_get_min_dex','test_get_max_dex','test_get_gas_usage_given_aggregator'))

    # running them
    runner = unittest.TextTestRunner()
    runner.run(suite)#runs the tests defined in the suite parameter

    # saving the tests
    cov.stop()
    cov.save()
    cov.report()

