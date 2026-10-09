# Programmēšanas un algoritmu ĢEDD

**Datums:** 09.10.2026.  
**Programmēšana I:** Gitea repozitorijs, versiju vēsture un Python pamatkonstrukcijas  
**Algoritmu pamati:** vienkāršu algoritmu īstenošana Python programmās, izsekošana un testēšana

## Sasniedzamie rezultāti

### Programmēšana I

Es izveidoju Gitea repozitoriju, pievienoju README un Python failus, saglabāju darbu loģiskos `commit` posmos un nosūtu jaunāko versiju uz serveri. Programmās izmantoju `if`, `for` un `while`.

### Algoritmu pamati

Es uzrakstu Python programmu, kas īsteno vienkāršu algoritmu, izsekoju tās mainīgo vērtības un pārbaudu programmu ar tipisku, robežas un nederīgu ievadi.

## Šodienas darba secība

1. stunda — repozitorija izveide un darba plūsmas demonstrācija.  
2. stunda — README un failu struktūras sagatavošana.  
3.–5. stunda — programmēšanas uzdevumi un regulāri `commit`.  
6. stunda — Programmēšanas ĢEDD iesniegums.  
7. stunda — algoritmiskie programmēšanas uzdevumi Python valodā.  
8. stunda — izvēlētās programmas pabeigšana, testi, izsekošana un Algoritmu pamatu ĢEDD iesniegums.

## Repozitorija struktūra

```text
README.md
TESTI.md
01_vecuma_grupa.py
02_reizinasanas_tabula.py
03_paroles_parbaude.py
04_summa_lidz_n.py
05_min_un_max.py
06_lineara_meklesana.py
07_skaitlu_analizators.py
08_mini_bankomats.py
09_burbulkartosana.py
```

## Darba noteikumi

- Veic uzdevumus pēc kārtas, kamēr tie atbilst tavam līmenim.
- Katru uzdevumu saglabā atsevišķā `.py` failā.
- Pēc katra pabeigta darba posma izveido atsevišķu `commit` un veic `push`.
- Tev nav jāpabeidz visi deviņi uzdevumi. Pirmie trīs pārbauda Python pamatprasmes. 4.–9. uzdevums palīdz noteikt, cik patstāvīgi proti veidot algoritmu.
- Algoritmu ĢEDD jābūt redzamam gan Python kodā, gan failā `TESTI.md`.
- Ja tests atklāj kļūdu, pieraksti faktisko rezultātu un izlabo programmu. Atrasta un izskaidrota kļūda nav neveiksme.

## Git darba plūsma

Pēc katra pabeigta posma:

```bash
git status
git add .
git commit -m "Īss un konkrēts paveiktā apraksts"
git push
```

## 1. uzdevums — Vecuma grupa

Izveido programmu, kas:

1. pieprasa lietotāja vecumu;
2. ar `if`, `elif` un `else` nosaka grupu;
3. izvada vienu no rezultātiem: `bērns`, `pusaudzis`, `pieaugušais` vai `seniors`.

Izvēlies un kodā skaidri norādi vecuma robežas.

**Fails:** `01_vecuma_grupa.py`  
**Ieteiktais commit:** `Pievienots vecuma grupas uzdevums ar if`

**Pārbaudes:** vecumi tieši pirms un pēc katras robežas, `0`, negatīvs skaitlis un tukša ievade.

## 2. uzdevums — Reizināšanas tabula

Izveido programmu, kas pieprasa vienu veselu skaitli un ar `for` ciklu izvada tā reizināšanas tabulu no 1 līdz 10.

Piemērs, ja ievadīts `4`:

```text
4 x 1 = 4
4 x 2 = 8
...
4 x 10 = 40
```

**Fails:** `02_reizinasanas_tabula.py`  
**Ieteiktais commit:** `Pievienota reizināšanas tabula ar for`

**Pārbaudes:** pozitīvs skaitlis, `0`, `1`, negatīvs skaitlis un teksts skaitļa vietā.

## 3. uzdevums — Paroles pārbaude

Izveido programmu, kurā pareizā parole ir saglabāta mainīgajā. Lietotājam ir ne vairāk kā trīs mēģinājumi.

Programmai:

- jāizmanto `while` cikls;
- pēc pareizas paroles jāizvada `Piekļuve atļauta`;
- pēc trim nepareiziem mēģinājumiem jāizvada `Piekļuve bloķēta`;
- pēc kļūdaina mēģinājuma jāparāda, cik mēģinājumu vēl atlicis.

**Fails:** `03_paroles_parbaude.py`  
**Ieteiktais commit:** `Pievienota paroles pārbaude ar while`

**Pārbaudes:** pareiza parole pirmajā mēģinājumā, pareiza trešajā, trīs nepareizas paroles un tukša parole.

# Algoritmiskie programmēšanas uzdevumi

Šajos uzdevumos algoritms jāīsteno Python kodā. Sāc ar 4. uzdevumu un turpini, kamēr pietiek laika.

## 4. uzdevums — Summa no 1 līdz n

Izveido programmu, kas:

1. pieprasa veselu pozitīvu skaitli `n`;
2. ar `for` vai `while` aprēķina visu skaitļu summu no `1` līdz `n`, ieskaitot `n`;
3. parāda gala summu;
4. paskaidro kļūdu, ja ievadīts `0`, negatīvs skaitlis vai nederīga vērtība.

Nelieto gatavu summēšanas funkciju. Mērķis ir pašam uzrakstīt summēšanas algoritmu.

**Piemērs:** ja `n = 5`, rezultāts ir `15`.  
**Fails:** `04_summa_lidz_n.py`  
**Ieteiktais commit:** `Pievienots summēšanas algoritms`

**Pārbaudes:** `1`, `5`, `0`, negatīvs skaitlis un tukša ievade.

## 5. uzdevums — Mazākais un lielākais skaitlis

Izveido programmu, kas pieprasa, cik skaitļus lietotājs ievadīs. Pēc tam programma ievada skaitļus pa vienam un pati atrod mazāko un lielāko vērtību.

Prasības:

- izmanto ciklu;
- salīdzini katru jauno skaitli ar pašreizējo mazāko un lielāko;
- nelieto `min()` un `max()`;
- korekti apstrādā gadījumu, ja skaitļu skaits ir `0` vai negatīvs.

**Fails:** `05_min_un_max.py`  
**Ieteiktais commit:** `Pievienots minimuma un maksimuma meklēšanas algoritms`

**Pārbaudes:** viens skaitlis, visi vienādi, tikai negatīvi skaitļi, jaukta secība un skaitļu skaits `0`.

## 6. uzdevums — Lineārā meklēšana

Izmanto doto sarakstu:

```python
skaitli = [4, 7, 2, 9, 7, 1]
```

Programma pieprasa meklējamo skaitli un ar ciklu pārbauda saraksta elementus pēc kārtas.

Programmai jāizvada:

- pirmais indekss, kurā skaitlis atrasts;
- paziņojums `Nav atrasts`, ja skaitļa sarakstā nav.

Papildu līmenis: izvada visus indeksus, kuros vērtība atrasta.

**Fails:** `06_lineara_meklesana.py`  
**Ieteiktais commit:** `Pievienots lineārās meklēšanas algoritms`

**Pārbaudes:** pirmais elements, pēdējais elements, vērtība atkārtojas, vērtības nav un nederīga ievade.

## 7. uzdevums — Skaitļu analizators

Izveido programmu, kas sākumā pajautā, cik skaitļus lietotājs ievadīs. Pēc tam programma ar ciklu pieprasa katru skaitli un beigās parāda:

- ievadīto skaitļu summu;
- pozitīvo, negatīvo un nulles vērtību skaitu;
- pāra un nepāra skaitļu skaitu;
- vidējo aritmētisko.

**Fails:** `07_skaitlu_analizators.py`  
**Ieteiktais commit:** `Pievienots skaitļu analizators`

**Pārbaudes:** viens skaitlis, tikai nulles, pozitīvi un negatīvi skaitļi, kā arī skaitļu skaits `0`.

## 8. uzdevums — Mini bankomāts

Izveido programmu ar sākuma atlikumu `100`. Programma atkārtoti rāda izvēlni:

```text
1 — apskatīt atlikumu
2 — iemaksāt naudu
3 — izņemt naudu
4 — beigt darbu
```

Prasības:

- izvēlne atkārtojas ar `while`, līdz lietotājs izvēlas 4;
- darbības izvēlas ar `if` un `elif`;
- nedrīkst izņemt vairāk naudas, nekā ir kontā;
- nedrīkst iemaksāt vai izņemt nulli vai negatīvu summu;
- pēc katras darbības parādi saprotamu paziņojumu.

**Fails:** `08_mini_bankomats.py`  
**Ieteiktais commit:** `Pievienots mini bankomāts ar izvēlni`

**Pārbaudes:** izņemt visu atlikumu, izņemt par vienu vairāk, ievadīt `0`, negatīvu summu un neesošu izvēlnes numuru.

## 9. uzdevums — Burbuļkārtošana

Šis ir padziļinātais uzdevums. Sakārto sarakstu augošā secībā, salīdzinot blakus esošus elementus un samainot tos vietām.

```python
skaitli = [5, 2, 8, 1, 4]
```

Prasības:

- izmanto divus ciklus;
- salīdzini blakus esošos elementus;
- izveido maiņu ar pagaidu mainīgo vai Python vērtību maiņu;
- pēc katra ārējā cikla izvada saraksta pašreizējo stāvokli;
- nelieto `sort()` vai `sorted()`.

**Fails:** `09_burbulkartosana.py`  
**Ieteiktais commit:** `Pievienots burbuļkārtošanas algoritms`

**Pārbaudes:** jau sakārtots saraksts, dilstoša secība, vienādas vērtības, viens elements un tukšs saraksts.

# Algoritmu pamatu ĢEDD

Izvēlies vienu no 4.–9. uzdevuma. ĢEDD pierādījumiem jābūt divos failos:

1. darbojošs vai pamatoti iesākts `.py` fails ar algoritmu;
2. `TESTI.md` ar izsekošanu un testiem.

## 1. Programmas apraksts

Norādi faila nosaukumu, ievadi, sagaidāmo rezultātu un īsi paskaidro algoritma darbības.

## 2. Izpildes izsekošana

Izvēlies vienu konkrētu ievadi un pieraksti mainīgo vērtības pa soļiem.

```markdown
| Solis | Nosacījums | Mainīgie pirms | Veiktā darbība | Mainīgie pēc | Izvade |
|------:|------------|-----------------|----------------|----------------|--------|
| 0     | —   1       |        1         | 0 +1       |   1             |   1     |
| 1     |      1      |       1          |     1+2    |   3             |   3     |
| 2     |     1       |         3        |      3+4   |     7           |  7      |  
| 3     |             |         7        |    7+8     |       15        |   15    |     
## 3. Testa piemēri

Izveido vismaz četrus atšķirīgus testus.

```markdown
| Testa veids | Ievade | Sagaidāmais rezultāts | Faktiskais rezultāts | Tests izturēts? |
|-------------|--------|-----------------------|---------------------|-----------------|
| Tipisks     |    5    |           15            |         15            |       Jā          |
| Robežgadījums |   1   |            1           |          1           |          Jā       |
| Tukša vai nederīga ievade |0 |    0             |         kļūda            |       nē           |
| Papildu tests |  -5    |          0             |          0           |           jā      |
```

## 4. Kļūda, pretpiemērs vai uzlabojums

Ja tests atklāj kļūdu, pieraksti ievadi, sagaidāmo rezultātu, faktisko rezultātu, kļūdas cēloni un labojumu.

Ja programma visus testus iztur, izvēlies agrāku kļūdainu `commit` vai paskaidro, kura ievade radītu kļūdu bez vienas no tavām pārbaudēm.

**Ieteiktais commit:** `Pievienots algoritms un tā testi`

## Programmēšanas ĢEDD iesniegšanas pārbaude

- [ ] repozitorijs atveras Gitea;
- [ ] repozitorijā ir README un sāktie `.py` faili;
- [ ] programmās redzams `if`, `for` un `while` lietojums;
- [ ] programmas ir palaistas un pārbaudītas;
- [ ] versiju vēsturē ir vismaz trīs jēgpilni `commit`;
- [ ] jaunākā versija nosūtīta ar `push`;
- [ ] repozitorija saite iesniegta skolotājam.

## Algoritmu pamatu ĢEDD iesniegšanas pārbaude

- [ ] repozitorijā ir vismaz viens 4.–9. uzdevuma `.py` fails;
- [ ] algoritms darbojas vai ir skaidri norādīta atrastā kļūda;
- [ ] kodā izmantots cikls, nosacījums un mainīgo vērtību atjaunināšana;
- [ ] failā `TESTI.md` redzama izpildes izsekošana;
- [ ] izveidoti vismaz četri atšķirīgi testi;
- [ ] ir tipiska, robežas un tukša vai nederīga ievade;
- [ ] izmaiņas saglabātas ar `commit` un `push`;
- [ ] aizpildīts pašvērtējums.
