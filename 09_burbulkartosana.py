skaitli = [5, 2, 8, 1, 4]

n = len(skaitli)
print(f"Sākuma saraksts: {skaitli}")

for gajiens in range(n - 1):
    for j in range(n - 1 - gajiens):
        if skaitli[j] > skaitli[j + 1]:
            # maiņa ar pagaidu mainīgo
            pagaidu = skaitli[j]
            skaitli[j] = skaitli[j + 1]
            skaitli[j + 1] = pagaidu
    print(f"Pēc {gajiens + 1}. gājiena: {skaitli}")

print(f"Sakārtots saraksts: {skaitli}")