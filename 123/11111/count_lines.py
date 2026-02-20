import zipfile

zip_path = "data/aps_log.zip"

with zipfile.ZipFile(zip_path, "r") as z:
    # Берём первый файл внутри ZIP
    name = z.namelist()[0]
    print("Файл внутри ZIP:", name)

    count = 0
    with z.open(name, "r") as f:
        for line in f:
            count += 1

print("Всего строк:", count)
