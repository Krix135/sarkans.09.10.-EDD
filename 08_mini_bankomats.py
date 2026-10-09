atlikums = 100
darbojas = True


def nolasit_summu():
    """Nolasa summu; atgriež skaitli vai None, ja ievade nederīga."""
    teksts = input("Ievadi summu: ").strip()
    try:
        return float(teksts)
    except ValueError:
        return None


while darbojas:
    print()
    print("1 — apskatīt atlikumu")
    print("2 — iemaksāt naudu")
    print("3 — izņemt naudu")
    print("4 — beigt darbu")
    izvele = input("Izvēle: ").strip()

    if izvele == "1":
        print(f"Tavs atlikums: {atlikums:g}")
    elif izvele == "2":
        summa = nolasit_summu()
        if summa is None:
            print("Kļūda: summai jābūt skaitlim.")
        elif summa <= 0:
            print("Kļūda: summai jābūt lielākai par nulli.")
        else:
            atlikums += summa
            print(f"Iemaksāts: {summa:g}. Jaunais atlikums: {atlikums:g}")
    elif izvele == "3":
        summa = nolasit_summu()
        if summa is None:
            print("Kļūda: summai jābūt skaitlim.")
        elif summa <= 0:
            print("Kļūda: summai jābūt lielākai par nulli.")
        elif summa > atlikums:
            print(f"Kļūda: nepietiek līdzekļu. Atlikums: {atlikums:g}")
        else:
            atlikums -= summa
            print(f"Izņemts: {summa:g}. Jaunais atlikums: {atlikums:g}")
    elif izvele == "4":
        print("Paldies, uz redzēšanos!")
        darbojas = False
    else:
        print("Kļūda: neesoša izvēle, ievadi 1, 2, 3 vai 4.")