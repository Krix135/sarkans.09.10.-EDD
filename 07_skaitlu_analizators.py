ievade = input("Cik skaitļus ievadīsi? ").strip()

try:
    skaits = int(ievade)
except ValueError:
    print("Kļūda: skaitļu skaitam jābūt veselam skaitlim.")
else:
    if skaits <= 0:
        print("Kļūda: skaitļu skaitam jābūt vismaz 1.")
    else:
        summa = 0
        pozitivi = 0
        negativi = 0
        nulles = 0
        pari = 0
        nepari = 0

        i = 1
        while i <= skaits:
            teksts = input(f"Ievadi {i}. veselo skaitli: ").strip()
            try:
                skaitlis = int(teksts)
            except ValueError:
                print("Nederīga vērtība, mēģini vēlreiz.")
                continue

            summa += skaitlis
            if skaitlis > 0:
                pozitivi += 1
            elif skaitlis < 0:
                negativi += 1
            else:
                nulles += 1

            if skaitlis % 2 == 0:
                pari += 1
            else:
                nepari += 1
            i += 1

        videjais = summa / skaits
        print(f"Summa: {summa}")
        print(f"Pozitīvi: {pozitivi}, negatīvi: {negativi}, nulles: {nulles}")
        print(f"Pāra: {pari}, nepāra: {nepari}")
        print(f"Vidējais aritmētiskais: {videjais:.2f}")