import requests

# Параметры API
BASE_URL = "http://127.0.0.1:8000/api/v1/"
INPUT_FILE = "mnemonics.txt"  # Файл с мнемоническими фразами
OUTPUT_FILE = "checked_mnemonics.txt"  # Файл с результатами
START_INDEX = 0  # Начальный индекс кошелька
AMOUNT_ADDRESS = 10  # Количество адресов (конечный индекс)
UUID = ""  # UUID для запроса


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


def process_mnemonics(input_file, output_file):
    """Читает мнемонические фразы из файла, проверяет баланс и записывает результаты."""
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
            if response is not None:
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
            else:
                print(f"Не удалось получить данные для мнемонической фразы: {mnemonic}")


if __name__ == "__main__":
    process_mnemonics(INPUT_FILE, OUTPUT_FILE)
