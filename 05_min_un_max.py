ievade = input("Cik skaitļus ievadīsi? ").strip()

try:
    skaits = int(ievade)
except ValueError:
    print("Kļūda: skaitļu skaitam jābūt veselam skaitlim.")
else:
    if skaits <= 0:
        print("Kļūda: skaitļu skaitam jābūt vismaz 1.")
    else:
        mazakais = None
        lielakais = None
        i = 1
        while i <= skaits:
            teksts = input(f"Ievadi {i}. skaitli: ").strip()
            try:
                skaitlis = float(teksts)
            except ValueError:
                print("Nederīga vērtība, mēģini vēlreiz.")
                continue

            if mazakais is None or skaitlis < mazakais:
                mazakais = skaitlis
            if lielakais is None or skaitlis > lielakais:
                lielakais = skaitlis
            i += 1

        print(f"Mazākais: {mazakais:g}")
        print(f"Lielākais: {lielakais:g}")