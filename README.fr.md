# Daikin Cycle ML — version française (fork azsono03)

Copie de [elRadix/daikin_cycle_ml](https://github.com/elRadix/daikin_cycle_ml)
avec l'interface en français et quelques corrections (voir `CHANGELOG.md`,
entrée `1.22.0-fr.1`).

## Installation
HACS → menu ⋮ → Dépôts personnalisés → `https://github.com/azsono03/daikin_cycle_ml`,
catégorie **Intégration**, télécharger, redémarrer Home Assistant.

## Langue
Options de l'intégration → Notifications → Contenu et langue →
**Langue des notifications : Français**. Les cartes du tableau de bord
suivent ce réglage (ou `lang_override: 'fr'` dans leurs variables).

## Suivre les mises à jour du développeur
```
git remote add upstream https://github.com/elRadix/daikin_cycle_ml.git
git fetch upstream && git merge upstream/main
python3 scripts/build_fr_translation.py custom_components/daikin_cycle_ml   # complète fr.json
python3 scripts/translate_cards_fr.py                                       # cartes (sur des cartes non traduites)
```
`build_fr_translation.py` liste les textes ajoutés en amont et pas encore traduits.
