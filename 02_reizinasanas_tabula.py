ievade = input("Ievadi veselu skaitli: ").strip()

try:
    skaitlis = int(ievade)
except ValueError:
    print("Kļūda: jāievada vesels skaitlis, nevis teksts.")
else:
    for i in range(1, 11):
        print(f"{skaitlis} x {i} = {skaitlis * i}")