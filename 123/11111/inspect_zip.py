import zipfile

z = zipfile.ZipFile("data/aps_log.zip", "r")

print("=== FILES INSIDE aps_log.zip ===")
for name in z.namelist():
    print(name)
