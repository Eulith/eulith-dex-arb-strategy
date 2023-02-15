from __future__ import print_function

import os.path

import boto3
from eulith_web3.kms import KmsSigner

from eulith_web3.eulith_web3 import *
from eulith_web3.signing import LocalSigner, construct_signing_middleware

# For custody, we recommend KMS, but you can use LocalSigner for testing.
# We also integrate with other custody solutions, i.e. Fireblocks, GnosisSafe,
# those are not shown here (they're in the docs)

# --- Uncomment if using KMS ------
# aws_credentials_profile_name = '...'
# key_name = '...'
# formatted_key_name = f'alias/{key_name}'

# session = boto3.Session(profile_name=aws_credentials_profile_name)
# client = session.client('kms')
# ---------------------------------

# ---- Choose wallet integration --
# wallet = KmsSigner(client, formatted_key_name)
WALLET = LocalSigner("d1e3aea22ed3b8f5a2596a51ab41d4fee1f9ff5d050cee7d3bbf3bd7a48f451f")
# ---------------------------------
NETWORK_URL = "https://eth-main.eulithrpc.com/v0"
refresh_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzI1NksifQ.eyJzdWIiOiJyaHNlZGRpZWh1YW5nIiwiZXhwIjoxNzA4MTMyMDAzLCJzb3VyY2VfaGFzaCI6IioiLCJzY29wZSI6IkFQSVJlZnJlc2gifQ.09R02UBbSQP8f3pdvJ3O0AnlIuXE4-JWTgCDxRkzwp4KlOR-H7wl0qkrvV7o9DiiHcY2FSYtTVLPOUcI6seorBs"



# default EulithWeb3 object - TODO: improve
ew3 = EulithWeb3(eulith_url=NETWORK_URL,
             eulith_refresh_token=refresh_token,
             signing_middle_ware=construct_signing_middleware(WALLET))


