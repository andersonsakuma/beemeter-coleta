# QR de acesso e etiquetas

- [acesso-android-ios.pdf](acesso-android-ios.pdf) — uma folha A4 com o QR de instalação no Android (APK)
  e o de acesso no iPhone (aplicativo web), com os passos. Para imprimir e entregar aos monitores.
- [etiquetas-colonias-kits.pdf](etiquetas-colonias-kits.pdf) — 44 etiquetas (10 por folha A4): colônias
  G01-C1 a G04-C4, pares adicionais P01-C1 a P08-C2 e kits K01 a K12.

As etiquetas trazem `CCAMPO:COL:G01-C2` (colônia) ou `CCAMPO:KIT:K01` (kit) com correção de erro alta,
para continuar legíveis com sujeira ou desgaste. No aplicativo, **Hoje → Ler etiqueta QR** abre a escolha
de ficha já com a colônia (ocupação, pesagem, manejo, extração, linha de base, instalação do kit) ou com o
kit (verificação, instalação). A câmera comum do celular só mostra o texto da etiqueta.

Imprima em papel adesivo à prova d'água ou plastifique; cole na lateral da caixa, à sombra.

Para gerar de novo (outro número de kits ou de pares):

```bash
pip install segno reportlab
python gerar_etiquetas.py --kits 12 --pares 8
```
