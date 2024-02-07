import asyncio
import uuid
import requests
from pprint import pprint

from grpc import RpcError

from pyinjective.async_client import AsyncClient
from pyinjective.constant import GAS_FEE_BUFFER_AMOUNT, GAS_PRICE
from pyinjective.core.network import Network
from pyinjective.transaction import Transaction
from pyinjective.wallet import Address, PrivateKey


async def withdraw_staking_rewards(
    grantee_pk: str, grantee: str, granter: str, delegator: str, validator: str
) -> None:
    # select network: local, testnet, mainnet
    network = Network.testnet()

    # initialize grpc client
    client = AsyncClient(network)
    composer = await client.composer()
    await client.sync_timeout_height()

    # load account
    priv_key = PrivateKey.from_hex(grantee_pk)
    pub_key = priv_key.to_public_key()
    address = pub_key.to_address()
    await client.fetch_account(address.to_acc_bech32())

    granter_address = Address.from_acc_bech32(granter)
    granter_subaccount_id = granter_address.get_subaccount_id(index=0)

    msg0 = composer.MsgWithdrawDelegatorReward(
        delegator_address=delegator, validator_address=validator
    )
    rewards_amount = 100000  # FIXME amount

    msg = composer.MsgExec(grantee=grantee, msgs=[msg0])

    # build sim tx
    tx = (
        Transaction()
        .with_messages(msg)
        .with_sequence(client.get_sequence())
        .with_account_num(client.get_number())
        .with_chain_id(network.chain_id)
    )
    sim_sign_doc = tx.get_sign_doc(pub_key)
    sim_sig = priv_key.sign(sim_sign_doc.SerializeToString())
    sim_tx_raw_bytes = tx.get_tx_data(sim_sig, pub_key)

    # simulate tx
    try:
        sim_res = await client.simulate(sim_tx_raw_bytes)
    except RpcError as ex:
        print(ex)
        return

    sim_res_msgs = sim_res["result"]["msgResponses"]
    data = sim_res_msgs[0]
    unpacked_msg_res = composer.unpack_msg_exec_response(
        underlying_msg_type=msg0.__class__.__name__, msg_exec_response=data
    )
    print("simulation msg response")
    print(unpacked_msg_res)

    # build tx
    gas_price = GAS_PRICE
    gas_limit = (
        int(sim_res["gasInfo"]["gasUsed"]) + GAS_FEE_BUFFER_AMOUNT
    )  # add buffer for gas fee computation
    gas_fee = "{:.18f}".format((gas_price * gas_limit) / pow(10, 18)).rstrip("0")
    fee = [
        composer.Coin(
            amount=gas_price * gas_limit,
            denom=network.fee_denom,
        )
    ]
    tx = (
        tx.with_gas(gas_limit)
        .with_fee(fee)
        .with_memo("")
        .with_timeout_height(client.timeout_height)
    )
    sign_doc = tx.get_sign_doc(pub_key)
    sig = priv_key.sign(sign_doc.SerializeToString())
    tx_raw_bytes = tx.get_tx_data(sig, pub_key)

    # broadcast tx: send_tx_async_mode, send_tx_sync_mode, send_tx_block_mode
    res = await client.broadcast_tx_sync_mode(tx_raw_bytes)
    print(res)
    print("gas wanted: {}".format(gas_limit))
    print("gas fee: {} INJ".format(gas_fee))


async def reward_delegate(
    grantee_pk: str,
    grantee: str,
    granter: str,
    delegator: str,
    validator: str,
    amount: float,
) -> None:
    # select network: local, testnet, mainnet
    network = Network.testnet()

    # initialize grpc client
    client = AsyncClient(network)
    composer = await client.composer()
    await client.sync_timeout_height()

    # load account
    priv_key = PrivateKey.from_hex(grantee_pk)
    pub_key = priv_key.to_public_key()
    address = pub_key.to_address()
    await client.fetch_account(address.to_acc_bech32())

    granter_address = Address.from_acc_bech32(granter)
    granter_subaccount_id = granter_address.get_subaccount_id(index=0)

    # msg0 = composer.MsgWithdrawDelegatorReward(
    #     delegator_address=delegator, validator_address=validator
    # )
    # rewards_amount = 100000  # FIXME amount

    msg0 = composer.MsgDelegate(
        delegator_address=delegator,
        validator_address=validator,
        amount=amount,
    )

    msg = composer.MsgExec(grantee=grantee, msgs=[msg0])

    # build sim tx
    tx = (
        Transaction()
        .with_messages(msg)
        .with_sequence(client.get_sequence())
        .with_account_num(client.get_number())
        .with_chain_id(network.chain_id)
    )
    sim_sign_doc = tx.get_sign_doc(pub_key)
    sim_sig = priv_key.sign(sim_sign_doc.SerializeToString())
    sim_tx_raw_bytes = tx.get_tx_data(sim_sig, pub_key)

    # simulate tx
    try:
        sim_res = await client.simulate(sim_tx_raw_bytes)
    except RpcError as ex:
        print(ex)
        return

    sim_res_msgs = sim_res["result"]["msgResponses"]
    data = sim_res_msgs[0]
    unpacked_msg_res = composer.unpack_msg_exec_response(
        underlying_msg_type=msg0.__class__.__name__, msg_exec_response=data
    )
    print("simulation msg response")
    print(unpacked_msg_res)

    # build tx
    gas_price = GAS_PRICE
    gas_limit = (
        int(sim_res["gasInfo"]["gasUsed"]) + GAS_FEE_BUFFER_AMOUNT
    )  # add buffer for gas fee computation
    gas_fee = "{:.18f}".format((gas_price * gas_limit) / pow(10, 18)).rstrip("0")
    fee = [
        composer.Coin(
            amount=gas_price * gas_limit,
            denom=network.fee_denom,
        )
    ]
    tx = (
        tx.with_gas(gas_limit)
        .with_fee(fee)
        .with_memo("")
        .with_timeout_height(client.timeout_height)
    )
    sign_doc = tx.get_sign_doc(pub_key)
    sig = priv_key.sign(sign_doc.SerializeToString())
    tx_raw_bytes = tx.get_tx_data(sig, pub_key)

    # broadcast tx: send_tx_async_mode, send_tx_sync_mode, send_tx_block_mode
    res = await client.broadcast_tx_sync_mode(tx_raw_bytes)
    print(res)
    print("gas wanted: {}".format(gas_limit))
    print("gas fee: {} INJ".format(gas_fee))


def get_staking_reward_amount(delegator_address: str, validator_address: str) -> float:
    # FIXME: I think we should staking all the INJ in the account, not sure
    response = requests.get(
        f"https://sentry.lcd.injective.network/cosmos/distribution/v1beta1/delegators/{delegator_address}/rewards/{validator_address}"
    )
    pprint(response)
    return 0.0


class bcolors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


if __name__ == "__main__":
    import os
    import configparser

    grantee_private_key = os.environ.get("GRANTEE_STAKING_PK")
    if grantee_private_key is None:
        print(f"{bcolors.FAIL}Error: $GRANTEE_STAKING_PK is not set!{bcolors.ENDC}")
        exit()

    if not os.path.isfile("auto_staking.ini"):
        print(f"{bcolors.FAIL}Error: Couldn't find auto_staking.ini!{bcolors.ENDC}")
        exit()

    config = configparser.ConfigParser()
    config.read("auto_staking.ini")

    granter = config["grant"]["granter_address"]
    grantee = config["grant"]["grantee_address"]

    withdraw_delegator_address = config["reward.withdraw"]["delegator_address"]
    withdraw_validator_address = config["reward.withdraw"]["validator_address"]

    asyncio.get_event_loop().run_until_complete(
        withdraw_staking_rewards(
            grantee_private_key,
            grantee,
            granter,
            delegator=withdraw_delegator_address,
            validator=withdraw_validator_address,
        )
    )

    delegate_delegator_address = config["reward.delegate"]["delegator_address"]
    delegate_validator_address = config["reward.delegate"]["validator_address"]
    auto_delegate_freq = config["reward.delegate"]["max_reward_auto_delegate_freq"]

    amount = 1000.0
    asyncio.get_event_loop().run_until_complete(
        reward_delegate(
            grantee_private_key,
            grantee,
            granter,
            delegator=withdraw_delegator_address,
            validator=withdraw_validator_address,
            amount=amount,
        )
    )
