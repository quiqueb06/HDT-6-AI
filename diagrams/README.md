# Diagramas de las arquitecturas

Los tres diagramas se generan con:

```bash
python diagrams/generar_diagramas.py
```

El script escribe los `.svg` (fuente) y, si `cairosvg` esta instalado, una
copia `.png` de cada uno. Los `.mmd` son la misma estructura en sintaxis
Mermaid, por si se quiere editar o ver en un visor Mermaid.

| Arquitectura | Programa | Diagrama |
|---|---|---|
| Centralizada | `architectures/centralized.py` | `arquitectura_centralizada.svg` |
| Jerarquica | `architectures/hierarchical.py` | `arquitectura_jerarquica.svg` |
| Descentralizada | `architectures/decentralized.py` | `arquitectura_descentralizada.svg` |
