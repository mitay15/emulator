import zipfile

z = zipfile.ZipFile("data/AndroidAPS.zip")   # <-- имя твоего архива
for name in z.namelist():
    print(name)
