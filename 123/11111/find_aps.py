from parser.file_loader import LogFileLoader

loader = LogFileLoader("data")

count = 0
first_aps = None

for line in loader.iter_log_lines():
    count += 1
    if "D/APS" in line or "APSResult" in line or "glucoseStatusJson" in line:
        first_aps = (count, line)
        break

print("Всего строк:", count)
print("Первый APS найден на строке:", first_aps)
