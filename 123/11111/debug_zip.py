from parser.file_loader import LogFileLoader

loader = LogFileLoader("data")

print("=== FILES DETECTED BY LOADER ===")
for ftype, path in loader.iter_log_files():
    print(ftype, path)
