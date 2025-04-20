from web3 import AsyncWeb3
from eth_utils import to_bytes, to_checksum_address
import logging

QUOTER_ABI = [
    {
        "inputs": [
            {"internalType": "bytes", "name": "path", "type": "bytes"},
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"}
        ],
        "name": "quoteExactInput",
        "outputs": [
            {"internalType": "uint256", "name": "amountOut", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]

logger = logging.getLogger(__name__)


def build_path(token_in: str, token_out: str, fee: int) -> bytes:
    """Формирует путь байтов для Uniswap V3"""
    path = (
        to_bytes(hexstr=token_in)
        + fee.to_bytes(3, byteorder="big")
        + to_bytes(hexstr=token_out)
    )
    logger.debug(f"Path bytes: {path.hex()}")
    return path


async def quote_exact_input(w3: AsyncWeb3, path: bytes, amount_in: int, quoter_address: str) -> int:
    """Вычисляет количество output токенов через quoteExactInput"""
    try:
        contract = w3.eth.contract(address=to_checksum_address(quoter_address), abi=QUOTER_ABI)
        amount_out = await contract.functions.quoteExactInput(path, amount_in).call()
        return amount_out
    except Exception as e:
        logger.error(f"Ошибка в quoteExactInput: {e}")
        return 0
