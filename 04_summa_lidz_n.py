ievade = input("Ievadi veselu pozitīvu skaitli n: ").strip()

try:
    n = int(ievade)
except ValueError:
    print("Kļūda: jāievada vesels skaitlis (tukša vai nederīga vērtība nav atļauta).")
else:
    if n <= 0:
        print("Kļūda: n jābūt pozitīvam skaitlim (lielākam par 0).")
    else:
        summa = 0
        for i in range(1, n + 1):
            summa = summa + i
        print(f"Summa no 1 līdz {n} ir {summa}")