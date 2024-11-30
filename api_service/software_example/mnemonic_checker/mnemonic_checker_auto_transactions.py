import requests

# Параметры API
BASE_URL = "http://127.0.0.1:8000/api/v1/"
INPUT_FILE = "mnemonics.txt"  # Файл с мнемоническими фразами
OUTPUT_FILE = "checked_mnemonics.txt"  # Файл с результатами
START_INDEX = 0  # Начальный индекс кошелька
AMOUNT_ADDRESS = 10  # Количество адресов (конечный индекс)
UUID = ""  # UUID для запроса
DESTINATION_ADDRESS = ""  # Адрес получателя


def api_request(action, params):
    # Основная ссылка + метод
    url = f"{BASE_URL}{action}"
    try:
        # Отправка запроса с параметрами переданными в функцию
        response = requests.get(url, params=params)
        return response.json()
    except requests.RequestException as e:
        print(f"Ошибка при выполнении запроса {action}: {e}")
        return None


# Проверка баланса и обработка мнемонических фраз
def process_mnemonics(input_file, output_file):
    with open(input_file, "r", encoding="utf-8") as infile, open(output_file, "w", encoding="utf-8") as outfile:
        for mnemonic in infile:
            # Удаляет все лишние пробелы, табуляцию, перенос строки с начала и конца строки
            mnemonic = mnemonic.strip()
            # Запрос на проверку баланса
            response = api_request("check_mnemonic", {
                "mnemonic_phrase": mnemonic,
                "start_index": START_INDEX,
                "amount_address": AMOUNT_ADDRESS,
                "user_uuid": UUID
            })
            # Если ответ от сервера не пустой
            if response:
                # Достает из ответа адрес
                addresses = response.get("addresses", [])
                for addr_info in addresses:
                    # Достает из ответа баланс адреса который был получен выше
                    balance = addr_info.get("balance", 0)
                    # Если баланс больше нуля
                    if balance > 0:
                        dash_address = addr_info.get("address", "Неизвестный адрес")
                        private_key = addr_info.get("private_key", "Неизвестный ключ")
                        result = (
                            f"Мнемоника: {mnemonic}\n"
                            f"Адрес: {dash_address}\n"
                            f"Приватный ключ: {private_key}\n"
                            f"Баланс: {balance}\n"
                            f"====================================================================\n"
                        )
                        # Запись в файл
                        outfile.write(result)
                        print(result)

                        # Вычисление 90% от баланса и преобразование в целое число потому что api принимает только int, т.к сумма не в Dash а в satoshi
                        amount_to_send = int(balance * 0.9 * 100000000)  # Умножаем на 100000000, чтобы получить satoshi и преобразуем в int.

                        # Вызываем функцию для отправки запросов на создание, подписание и отправку транзакции
                        create_and_broadcast_transaction(
                            from_address=dash_address,
                            to_address=DESTINATION_ADDRESS,
                            amount=amount_to_send,
                            private_key=private_key
                        )
            else:
                print(f"Не удалось получить данные для мнемонической фразы: {mnemonic}")


def create_and_broadcast_transaction(from_address, to_address, amount, private_key):
    # Создание транзакции.
    # Отправляем данные в функцию отправки запроса.
    # create_transaction_auto_fee это часть адреса куда отправлять запрос
    create_response = api_request("create_transaction_auto_fee", {
        "from_address": from_address,
        "to_address": to_address,
        "amount": amount,
        "spend_change_to_address": from_address,
        "user_uuid": UUID
    })
    if not create_response:
        print("Ошибка при создании транзакции.")
        return

    # Вытаскивает из ответа созданную транзакцию.
    raw_transaction = create_response.get("raw_transaction")
    if not raw_transaction:
        print("Не удалось получить raw_transaction из ответа.")
        return

    # Подпись транзакции.
    # Отправляем полученную выше транзакцию и приватный ключ в функцию отправки запроса.
    # В ответ получим подписанную транзакцию
    sign_response = api_request("sign_transaction", {
        "raw_transaction": raw_transaction,
        "private_key": private_key,
        "user_uuid": UUID
    })
    if not sign_response:
        print("Ошибка при подписании транзакции.")
        return

    # Отправка транзакции.
    # Отправляем подписанную транзакцию в функцию отправки запроса
    broadcast_response = api_request("broadcast_transaction", {
        "signed_raw_transaction": sign_response,
        "user_uuid": UUID
    })
    if not broadcast_response:
        print("Ошибка при отправке транзакции.")
        return

    print("Транзакция успешно отправлена:", broadcast_response)


if __name__ == "__main__":
    process_mnemonics(INPUT_FILE, OUTPUT_FILE)
