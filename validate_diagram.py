import pathlib
import re

app = pathlib.Path("app.py").read_text(encoding="utf-8")
tonto = pathlib.Path("diagrama uml/grafo.tonto.new").read_text(encoding="utf-8")

web_skills = set(re.findall(r'^    "([^"]+)":', app, re.MULTILINE))
tonto_labels = set(re.findall(r'@pt-br\s+"([^"]+)"', tonto))
missing_labels = sorted(web_skills - tonto_labels)

required_relations = [
    "HabilidadeTratamento",
    "DependenciaHabilidade",
    "AvaliacaoHabilidade",
    "Recomendacao",
]
missing_relations = [
    relation for relation in required_relations
    if f"relator {relation}" not in tonto
]

specializations = len(re.findall(
    r'^kind\s+\w+\s+specializes\s+Habilidade(?:Autocuidado|Motora)',
    tonto,
    re.MULTILINE,
))

assert not missing_labels, f"Habilidades ausentes: {missing_labels}"
assert not missing_relations, f"Relações ausentes: {missing_relations}"
assert specializations == 25, f"Especializações encontradas: {specializations}"
assert len(web_skills) == 25, f"Habilidades web encontradas: {len(web_skills)}"

print(f"PASS: {len(web_skills)} habilidades alinhadas")
print("PASS: 4 relações principais declaradas")
print(f"PASS: {specializations} especializações declaradas")
