from parser.file_loader import LogFileLoader
from parser.log_parser_json import AAPS34JSONParser


def process_logs(folder: str):
    loader = LogFileLoader(folder)
    parser = AAPS34JSONParser()

    print("\n=== ДИАГНОСТИКА JSON-ПАРСЕРА ===\n")

    count_lines = 0
    count_glucose = 0
    count_profile = 0
    count_result = 0
    count_suggested = 0

    for line in loader.iter_log_lines():
        count_lines += 1

        if "glucoseStatusJson" in line:
            print("\n[FOUND glucoseStatusJson]")
            print(line[:300])
            g = parser.parse_glucose(line)
            print("parsed:", g)
            count_glucose += 1

        if "profileJson" in line:
            print("\n[FOUND profileJson]")
            print(line[:300])
            p = parser.parse_profile(line)
            print("parsed:", p)
            count_profile += 1

        if "resultJson" in line:
            print("\n[FOUND resultJson]")
            print(line[:300])
            r = parser.parse_result(line)
            print("parsed:", r)
            count_result += 1

        if " suggested={" in line:
            print("\n[FOUND suggested]")
            print(line[:300])
            s = parser.parse_suggested(line)
            print("parsed:", s)
            count_suggested += 1

        # ограничим вывод
        if count_lines > 2000:
            break

    print("\n=== ИТОГ ===")
    print("Всего строк:", count_lines)
    print("glucoseStatusJson:", count_glucose)
    print("profileJson:", count_profile)
    print("resultJson:", count_result)
    print("suggested:", count_suggested)


if __name__ == "__main__":
    process_logs("data")
