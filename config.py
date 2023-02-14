from __future__ import print_function

import os.path

import boto3
from eulith_web3.kms import KmsSigner

from eulith_web3.eulith_web3 import *
from eulith_web3.signing import LocalSigner, construct_signing_middleware

# --- Uncomment if using KMS ------
# aws_credentials_profile_name = '...'
# key_name = '...'
# formatted_key_name = f'alias/{key_name}'

# session = boto3.Session(profile_name=aws_credentials_profile_name)
# client = session.client('kms')
# ---------------------------------

# ---- Choose wallet integration --
# wallet = KmsSigner(client, formatted_key_name)
# wallet = LocalSigner("...")
# ---------------------------------

network_url = "https://eth-main.eulithrpc.com/v0"
refresh_token = "..."

# default EulithWeb3 object - TODO: improve
ew3 = EulithWeb3(eulith_url=network_url,
             eulith_refresh_token=refresh_token,
             signing_middle_ware=construct_signing_middleware(wallet))
