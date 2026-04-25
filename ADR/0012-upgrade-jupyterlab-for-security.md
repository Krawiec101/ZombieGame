# ADR 0012: Aktualizacja JupyterLab po wykryciu podatnosci

- Status: Accepted
- Data: 2026-07-18

## Kontekst

Audyt `pip-audit` blokuje pipeline CI z powodu czterech podatnosci w przypietym `jupyterlab==4.4.8`:
`PYSEC-2026-164`, `PYSEC-2026-2538`, `PYSEC-2026-2537` oraz `GHSA-vmhf-c436-hxj4`.
Najwyzsza wersja naprawiajaca wszystkie zgloszenia to 4.5.9.

## Decyzja

Aktualizujemy JupyterLab z wersji 4.4.8 do 4.5.9. Pozostawiamy dokladne przypiecie wersji, aby obrazy Docker i
lokalne srodowiska byly powtarzalne. Po aktualizacji pipeline nadal wykonuje `pip-audit` jako blokujaca bramke SCA.

## Konsekwencje

Pozytywne:

- usuniecie znanych podatnosci JupyterLab raportowanych przez `pip-audit`,
- przywrocenie przechodzacej bramki SCA,
- zachowanie powtarzalnej wersji zaleznosci.

Negatywne:

- aktualizacja minor moze zawierac zmiany zachowania interfejsu JupyterLab,
- obrazy Docker musza zostac przebudowane.

## Rozwazone alternatywy

- ignorowanie wskazanych podatnosci, odrzucone, poniewaz ukrywaloby znane ryzyko i oslabialo bramke SCA,
- usuniecie JupyterLab, odrzucone, poniewaz jest wspieranym narzedziem deweloperskim projektu,
- zastosowanie zakresu wersji zamiast przypiecia, odrzucone ze wzgledu na mniejsza powtarzalnosc buildow.
