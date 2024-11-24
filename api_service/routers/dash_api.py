import secrets
from fastapi import HTTPException, Query, Depends, APIRouter
from sqlalchemy.orm import Session
from models import User, get_db, DWallet
import time
import requests

router = APIRouter()

# Настройки для RPC
URL = "http://localhost:9998/"
LOGIN = "rpcuser"
PASSWORD = "rpcpassword"

def rpc_call(method: str, params: list = None, wallet_name: str = None):
    if params is None:
        params = []

    # Если в функцию передается wallet_name=wallet_name, то тогда обычный адрес к rpc серверу меняется на адрес + /wallet/{wallet_name}
    # Это нужно для того что выполнять команды к конкретному кошельку созданному локально
    rpc_url = f"{URL}wallet/{wallet_name}" if wallet_name else URL

    # Тело запроса
    data = {
        "id": str(time.time()),
        "jsonrpc": "1.0",
        "method": method,
        "params": params
    }

    try:
        # Отправка запроса в ноду по RPC
        response = requests.post(rpc_url, json=data, auth=(LOGIN, PASSWORD))
        # Возвращает ответ функции которая вызвала rpc_call
        return response.json()
    except requests.RequestException as e:
        return {"error": str(e)}


# Функция для проверки UUID пользователя
def verify_user_uuid(user_uuid: str, db: Session = Depends(get_db)):
    # Создается запрос к таблице из модели (класса) User и ищется поле unique_id с таким же значением как передаваемый user_uuid
    db_user = db.query(User).filter(User.unique_id == user_uuid).first()
    if not db_user:
        # Если uuid не найден, то выводить ошибку
        raise HTTPException(status_code=403, detail="Invalid or unauthorized UUID.")
    return db_user


@router.get("/api/v1/create_wallet", tags=["DASH WALLET"])  # Параметр tags=["DASH WALLET"] позволяет выносить этот блок в отдельный раздел в документации
async def create_wallet(user_uuid: str = Query(..., description="UUID"), db: Session = Depends(get_db)):
    # Вызов функции проверки uuid, передавая в нее user_uuid из запроса и сессию
    verify_user_uuid(user_uuid, db)

    # Проверка количества кошельков для данного пользователя
    wallet_count = db.query(DWallet).filter(DWallet.user_unique_id == user_uuid).count()
    if wallet_count >= 5:
        return {"error": "Превышен лимит кошельков. У пользователя не может быть более 5 кошельков."}

    # Генерация случайного имени кошелька
    wallet_name = "dwallet_" + secrets.token_hex(8)  # Генерация случайного имени кошелька

    # Создание нового кошелька через отправку команды RCP в ноду
    method = "createwallet"
    params = [wallet_name]  # Имя кошелька
    rpc_call(method, params)  # Вызов метода для отправки команды RCP в ноду

    # Добавление кошелька в базу данных
    new_wallet = DWallet(wallet_name=wallet_name, user_unique_id=user_uuid)
    db.add(new_wallet)
    db.commit()
    db.refresh(new_wallet)

    # Получение адреса кошелька
    method = "getnewaddress"
    params = [wallet_name]  # Имя кошелька
    # Указываем имя кошелька и параметр wallet_name=wallet_name что бы rcp_call, сделал кастомный запрос именно для этой команды
    new_address = rpc_call(method, params, wallet_name=wallet_name)
    # Парсит ответа от rcp_call и вытаскивает из него значение ключа ["result"]
    address = new_address["result"]

    # Получение приватного ключа
    method = "dumpprivkey"
    params = [address]  # Сгенерированный выше кошелек
    # Указываем имя кошелька и параметр wallet_name=wallet_name что бы rcp_call, сделал кастомный запрос именно для этой команды
    privkey_result = rpc_call(method, params, wallet_name=wallet_name)
    # Парсит ответа от rcp_call и вытаскивает из него значение ключа ["result"]
    privkey = privkey_result["result"]


    # Получение публичного ключа
    method = "getaddressinfo"
    params = [address]  # Сгенерированный выше кошелек
    # Указываем имя кошелька и параметр wallet_name=wallet_name что бы rcp_call, сделал кастомный запрос именно для этой команды
    pubkey_result = rpc_call(method, params, wallet_name=wallet_name)
    # Парсит ответа от rcp_call и вытаскивает из него ключа ["result"] и из него вытаскивает значение ключа ("pubkey")
    pubkey = pubkey_result["result"].get("pubkey")


    # Возвращаем все данные
    return {
        "wallet_name": wallet_name,
        "address": address,
        "private_key": privkey,
        "public_key": pubkey
    }


@router.get("/api/v1/import_private_key", tags=["DASH WALLET"])
async def import_private_key(
    wallet_name: str = Query(..., description="Название кошелька"),
    private_key: str = Query(..., description="Приватный ключ кошелька"),
    user_uuid: str = Query(..., description="UUID"),
    db: Session = Depends(get_db)
):
    # Проверка UUID пользователя
    verify_user_uuid(user_uuid, db)

    # Проверка, принадлежит ли кошелек указанному пользователю
    wallet = db.query(DWallet).filter(DWallet.wallet_name == wallet_name, DWallet.user_unique_id == user_uuid).first()

    if not wallet:
        return {"error": "Кошелек с указанным именем не найден у пользователя с данным UUID."}

    # Импорт приватного ключа в новый кошелек
    method = "importprivkey"
    params = [private_key, ""]
    result = rpc_call(method, params, wallet_name=wallet_name)

    # Проверка на ошибки
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    # Если результат отсутствует (null), возвращаем подтверждение импорта
    if result.get("result") is None:
        return {"status": "success", "message": f"Приватный ключ успешно импортирован в кошелек {wallet_name}."}

    # Возвращаем оригинальный результат в случае наличия данных
    return {"status": "success", "data": result["result"]}


@router.get("/api/v1/check_balance_wallet", tags=["DASH WALLET"])
async def check_balance_wallet(
    wallet_name: str = Query(..., description="Название кошелька"),
    user_uuid: str = Query(..., description="UUID"),
    db: Session = Depends(get_db)
):
    # Проверка UUID пользователя
    verify_user_uuid(user_uuid, db)

    # Проверка, принадлежит ли кошелек указанному пользователю
    wallet = db.query(DWallet).filter(DWallet.wallet_name == wallet_name, DWallet.user_unique_id == user_uuid).first()

    if not wallet:
        return {"error": "Кошелек с указанным именем не найден у пользователя с данным UUID."}

    # Получение информации о кошельке
    method = "getwalletinfo"
    params = []
    result = rpc_call(method, params, wallet_name=wallet_name)

    # Проверка наличия ключа "result" и "balance"
    if not result or "result" not in result:
        return {"error": "Ошибка получения данных от RPC. Ответ: {}".format(result)}

    balance = result["result"].get("balance")
    if balance is None:
        return {"error": "Баланс не найден в ответе RPC. Ответ: {}".format(result)}

    # Возвращаем баланс
    return {
        "wallet_name": wallet_name,
        "balance": balance
    }


@router.get("/api/v1/send_transaction_wallet", tags=["DASH WALLET"])
async def send_transaction_wallet(
    wallet_name: str = Query(..., description="Название кошелька"),
    to_address: str = Query(..., description="Адрес получателя"),
    amount: float = Query(..., description="Сумма для отправки в dash"),
    user_uuid: str = Query(..., description="UUID"),
    db: Session = Depends(get_db)
):
    # Проверка UUID пользователя
    verify_user_uuid(user_uuid, db)

    # Проверка, принадлежит ли кошелек указанному пользователю
    wallet = db.query(DWallet).filter(DWallet.wallet_name == wallet_name, DWallet.user_unique_id == user_uuid).first()

    if not wallet:
        return {"error": "Кошелек с указанным именем не найден у пользователя с данным UUID."}

    # Отправка средств
    method = "sendtoaddress"
    params = [to_address, amount]
    result = rpc_call(method, params, wallet_name=wallet_name)

    if result.get("error") is not None:
        raise HTTPException(status_code=400, detail=result["error"])

    return result["result"]


@router.get("/api/v1/check_balance", tags=["DASH"])
async def check_balance(
    address: str = Query(..., description="Адрес для проверки баланса"),
    user_uuid: str = Query(..., description="UUID"),
    db: Session = Depends(get_db)
):
    # Вызов функции проверки uuid, передавая в нее user_uuid из запроса и сессию
    verify_user_uuid(user_uuid, db)

    # Передача данных в функцию отправки запроса на ноду (rpc_call)
    method = "getaddressbalance" # Команда для получения баланса
    params = [address] # Кошелек чей баланс нужно получить
    # Вызов rcp_call с отправкой в него метода и параметра для вызова RCP команды в ноду
    result = rpc_call(method, params)

    if result.get("error") is not None:
        raise HTTPException(status_code=400, detail=result["error"])

    if not isinstance(result.get("result"), dict):
        raise HTTPException(status_code=400, detail="Неверный формат данных в ответе RPC.")

    return result["result"]  # Возвращает баланс кошелька


@router.get("/api/v1/check_transaction", tags=["DASH"])
async def check_transaction(
    tx_hash: str = Query(..., description="Хэш транзакции"),
    user_uuid: str = Query(..., description="UUID"),
    db: Session = Depends(get_db)
):
    # Вызов функции проверки uuid, передавая в нее user_uuid из запроса и сессию
    verify_user_uuid(user_uuid, db)

    # Передача данных в функцию отправки запроса на ноду (rpc_call)
    method = "getrawtransaction" # Команда для получения информации о транзакции по ее хэшу
    params = [tx_hash, True] # Хэш транзакции
    # Вызов rcp_call с отправкой в него метода и параметра для вызова RCP команды в ноду
    result = rpc_call(method, params)

    if result.get("error") is not None:
        raise HTTPException(status_code=400, detail=result["error"])

    if not isinstance(result.get("result"), dict):
        raise HTTPException(status_code=400, detail="Неверный формат данных в ответе RPC.")

    return result["result"]  # Возвращает информацию о транзакции


@router.get("/api/v1/check_utxo", tags=["DASH"])
async def check_utxo(
    addresses: str = Query(..., description="Список адресов через запятую"),
    user_uuid: str = Query(..., description="UUID"),
    db: Session = Depends(get_db)
):
    # Вызов функции проверки uuid, передавая в нее user_uuid из запроса и сессию
    verify_user_uuid(user_uuid, db)
    address_list = addresses.split(",") # Разбивает кошельки через запятую чтобы была возможность отправлять несколько сразу

    # Передача данных в функцию отправки запроса на ноду (rpc_call)
    method = "getaddressutxos"
    params = [{"addresses": address_list}]  # Объект с адресами
    # Вызов rcp_call с отправкой в него метода и параметра для вызова RCP команды в ноду
    result = rpc_call(method, params)

    if result.get("error") is not None:
        raise HTTPException(status_code=400, detail=result["error"])

    if not isinstance(result.get("result"), list):
        raise HTTPException(status_code=400, detail="Неверный формат данных в ответе RPC.")

    return result["result"] # Возвращает информацию о входах (нетронутые пришедшие на кошелек транзакции)


@router.get("/api/v1/balance_history", tags=["DASH"])
async def balance_history(
    addresses: str = Query(..., description="Список адресов через запятую"),
    user_uuid: str = Query(..., description="UUID"),
    db: Session = Depends(get_db)
):
    # Вызов функции проверки uuid, передавая в нее user_uuid из запроса и сессию
    verify_user_uuid(user_uuid, db)
    address_list = addresses.split(",")  # Разбивает кошельки через запятую чтобы была возможность отправлять несколько сразу

    # Передача данных в функцию отправки запроса на ноду (rpc_call)
    method = "getaddressdeltas"
    params = [{"addresses": address_list}]  # Объект с адресами
    # Вызов rcp_call с отправкой в него метода и параметра для вызова RCP команды в ноду
    result = rpc_call(method, params)

    if result.get("error") is not None:
        raise HTTPException(status_code=400, detail=result["error"])

    if not isinstance(result.get("result"), list):
        raise HTTPException(status_code=400, detail="Неверный формат данных в ответе RPC.")

    return result["result"]


# Создание транзакции с авто подсчетом комиссии
@router.get("/api/v1/create_transaction_auto_fee", tags=["DASH"])
async def create_transaction_auto_fee(
        from_address: str = Query(..., description="Адрес отправителя"),
        to_address: str = Query(..., description="Адрес получателя"),
        spend_change_to_address: str = Query(..., description="Адрес для сдачи"),
        amount: int = Query(..., description="Сумма перевода в Satoshi"),
        user_uuid: str = Query(..., description="UUID пользователя"),
        db: Session = Depends(get_db)
):
    # Вызов функции проверки uuid, передавая в нее user_uuid из запроса и сессию
    verify_user_uuid(user_uuid, db)

    # Передача данных в функцию отправки запроса на ноду (rpc_call)
    method = "getaddressutxos"  # Команда для получения всех входов конкретного кошелька
    params = [{"addresses": [from_address]}]  # Кошелек
    # Вызов rcp_call с отправкой в него метода и параметра для вызова RCP команды в ноду
    result = rpc_call(method, params)

    if result.get("error") is not None:
        raise HTTPException(status_code=400, detail=result["error"])

    if not isinstance(result.get("result"), list):
        raise HTTPException(status_code=400, detail="Неверный формат данных в ответе RPC.")

    # Баланс по умолчанию
    total_balance = 0

    # Формируем объект для записи всех входов
    inputs = []

    # Формируем выходы
    outputs = [{to_address: amount / 100000000}]  # В выход записывается кошелек для перевода и деленная сумма в сатоши для получения суммы в Dash

    # Перебираем все элементы из списка result["result"]
    for new_utxo in result["result"]:
        # Берем из каждого элемента ключ ["satoshis"] и его значение добавляем в переменную total_balance что бы потом получить баланс со всех входов
        total_balance += new_utxo["satoshis"]
        # Добавляем входы в список
        inputs.append({
            "txid": new_utxo["txid"],
            "vout": new_utxo["outputIndex"]
        })

    # Расчет комиссии на основе количества входов и выходов
    input_count = len(inputs)
    output_count = len(outputs)
    fee_rate = 10 + (input_count * 148) + (output_count * 34)  # Общий размер транзакции

    # Если комиссия меньше 227, округляем до 227
    if fee_rate < 227:
        fee_rate = 227

    # Если баланс меньше чем сумма отправки, то ошибка
    if total_balance < amount + fee_rate:
        raise HTTPException(status_code=400, detail=f"Недостаточно средств для транзакции. "
                                                    f"Максимальная сумма для перевода: "
                                                    f"{total_balance - fee_rate} Satoshi")

    # Если остаток баланса после вычитания суммы перевода и комиссии больше нуля
    if total_balance - amount - fee_rate > 0 :
        fee_rate += 34  # Общий размер транзакции + 34 байта за дополнительный вход для сдачи
        spend_change = total_balance - amount - fee_rate  # Вычисляем остаток
        # Добавляем на выход кошелек для сдачи и остаток сатоши конвертированный в Dash
        outputs.append({spend_change_to_address: spend_change / 100000000})
    else:
        spend_change = 0


    # Передача данных в функцию отправки запроса на ноду (rpc_call)
    method = "createrawtransaction"  # Команды создания необработанной транзакции
    params = [inputs, outputs] # Входы (не тронутые транзакции на кошельке) и выходы (куда отправлять и сколько денег)
    # Вызов rcp_call с отправкой в него метода и параметра для вызова RCP команды в ноду
    result = rpc_call(method, params)

    if result.get("error") is not None:
        raise HTTPException(status_code=400, detail=result["error"])

    if not isinstance(result.get("result"), str):
        raise HTTPException(status_code=400, detail="Неверный формат данных в ответе RPC.")

    return {
        "raw_transaction": result["result"],
        "total_balance": total_balance,
        "amount": amount,
        "fee_rate": fee_rate,
        "spend_change": spend_change,
        "total_balance_satoshi": total_balance / 100000000,
        "amount_satoshi": amount / 100000000,
        "fee_rate_satoshi": fee_rate / 100000000,
        "spend_change_satoshi": spend_change / 100000000
    }


# Создание транзакции с конкретной комиссией
@router.get("/api/v1/create_transaction", tags=["DASH"])
async def create_transaction(
        from_address: str = Query(..., description="Адрес отправителя"),
        to_address: str = Query(..., description="Адрес получателя"),
        spend_change_to_address: str = Query(..., description="Адрес для сдачи"),
        amount: int = Query(..., description="Сумма перевода в Satoshi"),
        user_uuid: str = Query(..., description="UUID пользователя"),
        fee_rate: int = Query(5000, description="Комиссия"),
        db: Session = Depends(get_db)
):
    # Вызов функции проверки uuid, передавая в нее user_uuid из запроса и сессию
    verify_user_uuid(user_uuid, db)

    # Передача данных в функцию отправки запроса на ноду (rpc_call)
    method = "getaddressutxos"  # Команда для получения всех входов конкретного кошелька
    params = [{"addresses": [from_address]}]  # Кошелек
    # Вызов rcp_call с отправкой в него метода и параметра для вызова RCP команды в ноду
    result = rpc_call(method, params)

    if result.get("error") is not None:
        raise HTTPException(status_code=400, detail=result["error"])

    if not isinstance(result.get("result"), list):
        raise HTTPException(status_code=400, detail="Неверный формат данных в ответе RPC.")

    # Баланс по умолчанию
    total_balance = 0

    # Формируем объект для записи всех входов
    inputs = []

    # Формируем выходы
    outputs = [{to_address: amount / 100000000}]  # В выход записывается кошелек для перевода и деленная сумма в сатоши для получения суммы в Dash

    # Перебираем все элементы из списка result["result"]
    for new_utxo in result["result"]:
        # Берем из каждого элемента ключ ["satoshis"] и его значение добавляем в переменную total_balance что бы потом получить баланс со всех входов
        total_balance += new_utxo["satoshis"]
        # Добавляем входы в список
        inputs.append({
            "txid": new_utxo["txid"],
            "vout": new_utxo["outputIndex"]
        })

    # Если комиссия меньше
    if fee_rate < 227:
        fee_rate = 227

    # Если баланс меньше чем сумма отправки + начальная комиссия, то ошибка
    if total_balance < amount + fee_rate :
        raise HTTPException(status_code=400, detail=f"Недостаточно средств для транзакции. "
                                                    f"Максимальная сумма для перевода: "
                                                    f"{total_balance - fee_rate} Satoshi")

    # Если остаток баланса после вычитания суммы перевода и комиссии больше нуля
    if total_balance - amount - fee_rate > 0 :
        spend_change = total_balance - amount - fee_rate  # Вычисляем остаток
        # Добавляем на выход кошелек для сдачи и остаток сатоши конвертированный в Dash
        outputs.append({spend_change_to_address: spend_change / 100000000})
    else:
        spend_change = 0

    # Передача данных в функцию отправки запроса на ноду (rpc_call)
    method = "createrawtransaction"  # Команды создания необработанной транзакции
    params = [inputs, outputs] # Входы (не тронутые транзакции на кошельке) и выходы (куда отправлять и сколько денег)
    # Вызов rcp_call с отправкой в него метода и параметра для вызова RCP команды в ноду
    result = rpc_call(method, params)

    if result.get("error") is not None:
        raise HTTPException(status_code=400, detail=result["error"])

    if not isinstance(result.get("result"), str):
        raise HTTPException(status_code=400, detail="Неверный формат данных в ответе RPC.")

    return {
        "raw_transaction": result["result"],
        "total_balance": total_balance,
        "amount": amount,
        "fee_rate": fee_rate,
        "spend_change": spend_change,
        "total_balance_satoshi": total_balance / 100000000,
        "amount_satoshi": amount / 100000000,
        "fee_rate_satoshi": fee_rate / 100000000,
        "spend_change_satoshi": spend_change / 100000000
    }


# Подписывает заявку на транзакцию
@router.get("/api/v1/sign_transaction", tags=["DASH"])
async def sign_transaction(
    raw_transaction: str = Query(..., description="Транзакция в hex формате"),
    user_uuid: str = Query(..., description="UUID"),
    private_key: str = Query(..., description="Приватный ключ кошелька"),
    db: Session = Depends(get_db)
):
    # Вызов функции проверки uuid, передавая в нее user_uuid из запроса и сессию
    verify_user_uuid(user_uuid, db)

    method = "signrawtransactionwithkey"  # RCP команда для подписания транзакций
    params = [raw_transaction, [private_key]]  # Передача хэша транзакции и првиатного ключа необходимого для подписания
    # Вызов rcp_call с отправкой в него метода и параметра для вызова RCP команды в ноду
    result = rpc_call(method, params)

    if result.get("error") is not None:
        raise HTTPException(status_code=400, detail=result["error"])

    if not isinstance(result.get("result"), dict):
        raise HTTPException(status_code=400, detail="Неверный формат данных в ответе RPC.")

    return result["result"]["hex"]


# Заливает транзакцию в блок для обработки мастер нодами
@router.get("/api/v1/broadcast_transaction", tags=["DASH"])
async def broadcast_transaction(
    signed_raw_transaction: str = Query(..., description="Подписанная транзакция в hex формате"),
    user_uuid: str = Query(..., description="UUID"),
    db: Session = Depends(get_db)
):
    # Вызов функции проверки uuid, передавая в нее user_uuid из запроса и сессию
    verify_user_uuid(user_uuid, db)

    method = "sendrawtransaction"  # RCP команда для отправки подписанной транзакции в блок
    params = [str(signed_raw_transaction), 0, False, False]  # Передается подписанная транзакция
    result = rpc_call(method, params)
    return result


@router.get("/api/v1/block_info", tags=["DASH"])
async def block_info(
    block_hash: str = Query(..., description="Хэш блока"),
    user_uuid: str = Query(..., description="UUID"),
    db: Session = Depends(get_db)
):
    # Вызов функции проверки uuid, передавая в нее user_uuid из запроса и сессию
    verify_user_uuid(user_uuid, db)

    method = "getblock"  # Команда для получения информации о блоке по его хэшу
    params = [block_hash]
    result = rpc_call(method, params)

    if result.get("error") is not None:
        raise HTTPException(status_code=400, detail=result["error"])

    if not isinstance(result.get("result"), dict):
        raise HTTPException(status_code=400, detail="Неверный формат данных в ответе RPC.")

    return result["result"]


@router.get("/api/v1/sync_status", tags=["DASH NODE"])
async def sync_status(
    user_uuid: str = Query(..., description="UUID"),
    db: Session = Depends(get_db)
):
    # Вызов функции проверки uuid, передавая в нее user_uuid из запроса и сессию
    verify_user_uuid(user_uuid, db)

    method = "getblockchaininfo"  # Команда для получения информации о ноде
    result = rpc_call(method)

    if result.get("error") is not None:
        raise HTTPException(status_code=400, detail=result["error"])

    if not isinstance(result.get("result"), dict):
        raise HTTPException(status_code=400, detail="Неверный формат данных в ответе RPC.")

    return result["result"]


@router.get("/api/v1/start_mixing", tags=["DASH COINJOIN"])
async def start_mixing(
    wallet_name: str = Query(..., description="Название кошелька"),
    coinjoin_amount: int = Query(..., description="Лимит монет для микширования"),
    coinjoin_rounds: int = Query(..., description="Количество раундов для микширования"),
    user_uuid: str = Query(..., description="UUID"),
    db: Session = Depends(get_db)
):
    # Проверка UUID пользователя
    verify_user_uuid(user_uuid, db)

    # Проверка, принадлежит ли кошелек указанному пользователю
    wallet = db.query(DWallet).filter(DWallet.wallet_name == wallet_name, DWallet.user_unique_id == user_uuid).first()

    if not wallet:
        return {"error": "Кошелек с указанным именем не найден у пользователя с данным UUID."}

    # Проверка значения coinjoin_amount
    if coinjoin_amount > 100:
        return {"error": "Значение лимита монет для микширования не может быть больше 100."}

    # Проверка значения coinjoin_rounds
    if coinjoin_rounds > 16:
        return {"error": "Количество раундов для микширования не может быть больше 16."}

    # Установка лимита монет для микширования
    method = "setcoinjoinamount"
    params = [coinjoin_amount]
    rpc_call(method, params, wallet_name=wallet_name)

    # Установка количества раундов для микширования
    method = "setcoinjoinrounds"
    params = [coinjoin_rounds]
    rpc_call(method, params, wallet_name=wallet_name)

    # Запуск микшера
    method = "coinjoin"
    params = ["start"]
    result = rpc_call(method, params, wallet_name=wallet_name)

    return {"status": result["result"],
            "wallet_name": wallet_name}


@router.get("/api/v1/stop_mixing", tags=["DASH COINJOIN"])
async def stop_mixing(
    wallet_name: str = Query(..., description="Название кошелька"),
    user_uuid: str = Query(..., description="UUID"),
    db: Session = Depends(get_db)
):
    # Проверка UUID пользователя
    verify_user_uuid(user_uuid, db)

    # Проверка, принадлежит ли кошелек указанному пользователю
    wallet = db.query(DWallet).filter(DWallet.wallet_name == wallet_name, DWallet.user_unique_id == user_uuid).first()

    if not wallet:
        return {"error": "Кошелек с указанным именем не найден у пользователя с данным UUID."}

    # Остановка микшера
    method = "coinjoin"
    params = ["stop"]
    result = rpc_call(method, params, wallet_name=wallet_name)
    print(result)

    return {
        "status": "CoinJoin stopped",
        "wallet_name": wallet_name
    }