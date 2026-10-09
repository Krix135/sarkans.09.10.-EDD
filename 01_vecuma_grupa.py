BERNS_LIDZ = 12
PUSAUDZIS_LIDZ = 17
PIEAUGUSAIS_LIDZ = 64

ievade = input("Ievadi vecumu: ").strip()

try:
    vecums = int(ievade)
except ValueError:
    print("Kļūda: vecumam jābūt veselam skaitlim.")
else:
    if vecums < 0:
        print("Kļūda: vecums nevar būt negatīvs.")
    elif vecums <= BERNS_LIDZ:
        print("bērns")
    elif vecums <= PUSAUDZIS_LIDZ:
        print("pusaudzis")
    elif vecums <= PIEAUGUSAIS_LIDZ:
        print("pieaugušais")
    else:
        print("seniors")