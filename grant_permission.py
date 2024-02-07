import asyncio
from sys import exec_prefix

from grpc import RpcError

from pyinjective.async_client import AsyncClient
from pyinjective.constant import GAS_FEE_BUFFER_AMOUNT, GAS_PRICE
from pyinjective.core.network import Network
from pyinjective.transaction import Transaction
from pyinjective.wallet import PrivateKey
from pprint import pprint


async def main(
    private_key: str,
    granter_address: str,
    grantee_address: str,
    expire_in: int = 31536000,
) -> None:
    # select network: local, testnet, mainnet
    network = Network.mainnet()

    # initialize grpc client
    client = AsyncClient(network)
    composer = await client.composer()
    await client.sync_timeout_height()

    # load account
    priv_key = PrivateKey.from_hex(private_key)
    pub_key = priv_key.to_public_key()
    address = pub_key.to_address()
    await client.fetch_account(address.to_acc_bech32())

    # prepare tx msg

    # GENERIC AUTHZ
    msg0 = composer.MsgGrantGeneric(
        granter=granter_address,
        grantee=grantee_address,
        msg_type="/cosmos.staking.v1beta1.MsgDelegate",
        expire_in=expire_in,  # 1 year
    )
    msg1 = composer.MsgGrantGeneric(
        granter=granter_address,
        grantee=grantee_address,
        msg_type="/cosmos.distribution.v1beta1.MsgWithdrawDelegatorReward",
        expire_in=expire_in,  # 1 year
    )

    # build sim tx
    tx = (
        Transaction()
        .with_messages(*[msg0, msg1])
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
    pprint(res)
    print("gas wanted: {}".format(gas_limit))
    print("gas fee: {} INJ".format(gas_fee))


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

    private_key = os.environ.get("GRANTER_STAKING_PK")
    if private_key is None:
        print(f"{bcolors.FAIL}Error: $GRANTER_STAKING_PK is not set!{bcolors.ENDC}")
        exit()

    if not os.path.isfile("auto_staking.ini"):
        print(f"{bcolors.FAIL}Error: Couldn't find auto_staking.ini!{bcolors.ENDC}")
        exit()

    config = configparser.ConfigParser()
    config.read("auto_staking.ini")

    granter_address = config["grant"]["granter_address"]
    grantee_address = config["grant"]["grantee_address"]
    expire_in = int(config["grant"]["expire_in"])

    # asyncio.get_event_loop().run_until_complete(
    #     main(private_key, granter_address, grantee_address)
    # )
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main(private_key, granter_address, grantee_address))
    print()
    print(f"Granter: {bcolors.OKGREEN}{granter_address}{bcolors.ENDC}")
    print("granted: MsgWithdrawDelegatorReward, MsgDelegate to")
    print(f"grantee: {bcolors.OKGREEN}{grantee_address}{bcolors.OKGREEN}")
