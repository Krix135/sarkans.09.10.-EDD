PAREIZA_PAROLE = "python123"
MAKS_MEGINAJUMI = 3

megijumi = 0
atlauts = False

while megijumi < MAKS_MEGINAJUMI and not atlauts:
    parole = input("Ievadi paroli: ")
    megijumi += 1

    if parole == PAREIZA_PAROLE:
        atlauts = True
    else:
        atlicis = MAKS_MEGINAJUMI - megijumi
        if atlicis > 0:
            print(f"Nepareiza parole. Atlikušo mēģinājumu skaits: {atlicis}")

if atlauts:
    print("Piekļuve atļauta")
else:
    print("Piekļuve bloķēta")