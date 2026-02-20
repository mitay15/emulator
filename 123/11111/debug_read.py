from parser.file_loader import LogFileLoader

loader = LogFileLoader("data")

print("=== FIRST 50 LINES READ BY LOADER ===")
count = 0

for line in loader.iter_log_lines():
    print(line)
    count += 1
    if count >= 50:
        break

print("=== TOTAL READ BEFORE BREAK:", count)
