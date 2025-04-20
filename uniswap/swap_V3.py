from eth_typing import Address
from eth_utils import to_checksum_address
from client.client import Client
from uniswap.router_v3 import build_exact_input_call, build_multicall_payload
from utils.logger import logger


async def swap_tokens_v3(
    client: Client,
    path: bytes,
    recipient: Address | str,
    amount_in: int,
    amount_out_min: int,
    router_address: str,
    native_token: bool = False
) -> str:
    try:
        logger.info("\u23e9 Формирование вызова exactInput...\n")
        exact_input_call = await build_exact_input_call(client.w3, path, recipient, amount_in, amount_out_min,
                                                        router_address)

        logger.info("\u23e9 Формирование multicall payload...\n")
        calls = [exact_input_call]

        if native_token:
            # Добавляем вызов refundETH (возможно unwrapWETH позже)
            calls.append(client.w3.eth.contract(
                address=to_checksum_address(router_address),
                abi=[{
                    "inputs": [],
                    "name": "refundETH",
                    "outputs": [],
                    "stateMutability": "payable",
                    "type": "function"
                }]
            ).encodeABI(fn_name="refundETH"))

        multicall_data = await build_multicall_payload(client.w3, calls, router_address)

        tx = {"from": to_checksum_address(recipient),
              "to": to_checksum_address(router_address),
              "data": multicall_data,
              "value": amount_in if native_token else 0,
              "chainId": await client.w3.eth.chain_id,
              "nonce": await client.w3.eth.get_transaction_count(recipient)
              }

        tx["gas"] = int(await client.w3.eth.estimate_gas(tx) * 1.25)
        tx["maxFeePerGas"] = await client.w3.eth.gas_price * 2
        tx["maxPriorityFeePerGas"] = await client.w3.eth.max_priority_fee
        tx["type"] = 2

        signed = client.w3.eth.account.sign_transaction(tx, private_key=client.private_key)
        tx_hash = await client.w3.eth.send_raw_transaction(signed.raw_transaction)
        logger.info(f"\u2705 Транзакция отправлена: {client.w3.to_hex(tx_hash)}\n")
        return client.w3.to_hex(tx_hash)

    except Exception as e:
        logger.error(f"\u274c Ошибка при отправке multicall: {e}\n")
        return ""
