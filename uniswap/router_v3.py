from web3 import AsyncWeb3
from eth_utils import to_bytes, to_checksum_address
import time
import logging

logger = logging.getLogger(__name__)

ROUTER_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "bytes", "name": "path", "type": "bytes"},
                    {"internalType": "address", "name": "recipient", "type": "address"},
                    {"internalType": "uint256", "name": "deadline", "type": "uint256"},
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "uint256", "name": "amountOutMinimum", "type": "uint256"}
                ],
                "internalType": "struct ISwapRouter.ExactInputParams",
                "name": "params",
                "type": "tuple"
            }
        ],
        "name": "exactInput",
        "outputs": [
            {"internalType": "uint256", "name": "amountOut", "type": "uint256"}
        ],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "bytes[]", "name": "data", "type": "bytes[]"}
        ],
        "name": "multicall",
        "outputs": [
            {"internalType": "bytes[]", "name": "results", "type": "bytes[]"}
        ],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "refundETH",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    }
]


async def build_exact_input_call(w3: AsyncWeb3, path: bytes, recipient: str,
                                 amount_in: int, amount_out_min: int, router_address: str) -> bytes:
    contract = w3.eth.contract(address=to_checksum_address(router_address), abi=ROUTER_ABI)
    deadline = int(time.time()) + 120
    try:
        data = contract.encodeABI(
            fn_name="exactInput",
            args=[{
                "path": path,
                "recipient": to_checksum_address(recipient),
                "deadline": deadline,
                "amountIn": amount_in,
                "amountOutMinimum": amount_out_min
            }]
        )
        return to_bytes(hexstr=data)
    except Exception as e:
        logger.error(f"❌ Ошибка при кодировании exactInput: {e}\n")
        return b""


async def build_multicall_payload(w3: AsyncWeb3, call_data_list: list[bytes], router_address: str) -> bytes:
    contract = w3.eth.contract(address=to_checksum_address(router_address), abi=ROUTER_ABI)
    try:
        return contract.encodeABI(fn_name="multicall", args=[call_data_list])
    except Exception as e:
        logger.error(f"❌ Ошибка при сборке multicall: {e}\n")
        return b""
