import asyncio
import json
from config.configvalidator import ConfigValidator
from client.client import Client
from uniswap.quoter import build_path, quote_exact_input
from uniswap.swap_V3 import swap_tokens_v3
from utils.logger import logger


async def main():
    logger.info("\U0001F680 Запуск свапа PancakeSwap V3...\n")
    # Загрузка параметров
    validator = ConfigValidator("config/settings.json")
    settings = await validator.validate_config()

    with open("constants/networks_data.json", "r", encoding="utf-8") as f:
        networks_data = json.load(f)
    network = networks_data[settings["network"]]
    quoter_address = network["quoter_address"]

    # Загрузка адресов токенов
    with open("constants/tokens.json", "r") as file:
        tokens = json.load(file)

    network_name = settings["network"]
    from_token_symbol = settings["from_token"]
    to_token_symbol = settings["to_token"]

    from_token_address = tokens[network_name][from_token_symbol]
    to_token_address = tokens[network_name][to_token_symbol]

    client = Client(
        from_address=from_token_address,
        to_address=to_token_address,
        chain_id=network["chain_id"],
        rpc_url=network["rpc_url"],
        private_key=settings["private_key"],
        amount=float(settings["amount"]),
        router_address=network["router_address"],
        explorer_url=network["explorer_url"],
        proxy=settings["proxy"]
    )

    amount_in = await client.to_wei_main(client.amount, client.from_address)
    path = build_path(client.from_address, client.to_address, 100)  # fee = 0.01%

    # Проверка баланса исходящего токена
    erc20_balance = await client.get_erc20_balance()

    if from_token_symbol in ["ETH", "BNB", "MATIC", "OP"]:
        if erc20_balance < amount_in:
            logger.info("⛓  Врапаем нативный токен в wrapped...\n")
            native_balance = await client.get_native_balance()
            gas_cost = await client.get_tx_fee()

            if native_balance < amount_in + gas_cost:
                logger.error(
                    f"[{network_name}] Недостаточно средств: баланс"
                    f" {client.from_wei_main(native_balance)}")
                return

            wrap_tx_hash = await client.wrap_native(amount_wei=amount_in, token_address=client.from_address)
            await client.wait_tx(wrap_tx_hash, client.explorer_url)
    else:
        if erc20_balance < amount_in:
            logger.error(
                f"[{network_name}] Недостаточно средств: баланс"
                f" {client.from_wei_main(erc20_balance)}")

    # Проверка, что есть достаточно средств на оплату газа
    gas_fee = await client.get_tx_fee()
    native_balance = await client.get_native_balance()
    if native_balance < gas_fee:
        logger.error(f"[{network_name}] Недостаточно средств на газ: {client.from_wei_main(native_balance)}")
        return

    logger.info("\U0001F522 Запрашиваем котировку...\n")
    amount_out_estimated_wei = await quote_exact_input(client.w3, path, amount_in, quoter_address)
    if amount_out_estimated_wei == 0:
        logger.error("\u274c Не удалось получить котировку. Прерываем свап.")
        return

    slippage = settings.get("slippage", 1.0)
    amount_out_min_wei = int(amount_out_estimated_wei * (1 - slippage / 100))

    amount_out_estimated = await client.from_wei_main(amount_out_estimated_wei, to_token_address)
    amount_out_min = await client.from_wei_main(amount_out_min_wei, to_token_address)

    logger.info(f"\U0001F4B8 Ожидаемый output: {amount_out_estimated:.8f}, с учетом slippage: {amount_out_min:.8f}\n")

    logger.info("\U0001F9F9 Отправка multicall...\n")

    allowance = await client.get_allowance(
        token_address=from_token_address,
        owner=client.address,
        spender=client.router_address
    )

    if allowance < amount_in:
        logger.info("\U0001F522 Производим аппрув...\n")
        approve_tx = await client.build_approve_tx(
            token_address=from_token_address,
            spender=client.router_address,
            amount=amount_in
        )
        approve_hash = await client.sign_and_send_tx(approve_tx)
        await client.wait_tx(approve_hash, client.explorer_url)

    tx_hash = await swap_tokens_v3(
        client=client,
        path=path,
        recipient=client.address,
        amount_in=amount_in,
        amount_out_min=amount_out_min_wei,
        native_token=False,
        router_address=client.router_address
    )

    # Выполняем unwrap, если свап прошёл
    if tx_hash:
        logger.info(f"✅ Swap завершён: {client.explorer_url}/tx/{tx_hash}\n")

        logger.info("💸 Выполняем unwrap...\n")
        wrapped_balance = await client.get_erc20_balance()
        if wrapped_balance > 0:
            unwrap_tx = await client.unwrap_native(wrapped_balance)
            await client.wait_tx(unwrap_tx, client.explorer_url)
            logger.info("✅ Unwrap завершён")
    else:
        logger.warning("\u274c Swap не был отправлен")


if __name__ == "__main__":
    asyncio.run(main())
