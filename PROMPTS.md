# Projet LIDA + Ollama Mistral 7B

Le mode recommandé est maintenant **notebook cell-by-cell**:

- ouvre `NOTEBOOK_BLOCKS.md`
- copie/colle les blocs Python un par un dans Jupyter
- exécute chaque cellule avec `Alt+Entrée`

`main2.py` est un module de fonctions (pas d'entrée `if __name__ == "__main__"`).

## Setup

```bash
ollama pull mistral:7b
```

## Exemples de prompts

1. `Répartition des entités par ForceIdentifier`
2. `Pie chart des DamageState`
3. `Moyenne de SimTime par ForceIdentifier`
4. `Scatter Spatial_static_WorldLocation_x vs Spatial_static_WorldLocation_y`
5. `Nombre d'entités par EntityType avec ForceIdentifier == 2`
