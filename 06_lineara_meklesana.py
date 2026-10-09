skaitli = [4, 7, 2, 9, 7, 1]

ievade = input("Ievadi meklējamo skaitli: ").strip()

try:
    meklejamais = int(ievade)
except ValueError:
    print("Kļūda: jāievada vesels skaitlis.")
else:
    pirmais = -1
    visi = []
    for indekss in range(len(skaitli)):
        if skaitli[indekss] == meklejamais:
            if pirmais == -1:
                pirmais = indekss
            visi.append(indekss)

    if pirmais == -1:
        print("Nav atrasts")
    else:
        print(f"Pirmais indekss: {pirmais}")
        print(f"Visi indeksi: {visi}")