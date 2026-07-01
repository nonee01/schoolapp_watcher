from __future__ import annotations

from bs4 import BeautifulSoup

from ..models import StudentProfile
from ._tables import normalize_cell

# /index lays out both blocks (Situation Administrative, Données personnelles)
# as vertical <tr><th>label</th><td>value</td></tr> tables.

_FIELD_LABELS = {
    "code": "Code",
    "cne_masar": "CNE/Masar",
    "nom": "Nom",
    "prenom": "Prénom",
    "nom_ar": "Nom Arabe",
    "prenom_ar": "Prénom Arabe",
    "cin": "CIN",
    "sexe": "Sexe",
    "date_naissance": "Date Naissance",
    "email": "Email",
    "filiere": "Filière",
    "niveau": "Niveau",
    "statut": "Statut",
    "section": "Section",
    "groupe": "Groupe",
    "sous_groupe": "Sous Groupe",
}


def parse_profile(html: str) -> StudentProfile:
    soup = BeautifulSoup(html, "html.parser")
    raw: dict[str, str] = {}
    for tr in soup.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if len(cells) != 2 or cells[0].name != "th":
            continue
        k = normalize_cell(cells[0].get_text(" ", strip=True))
        v = normalize_cell(cells[1].get_text(" ", strip=True))
        if not k:
            continue
        key, n = k, 2
        while key in raw and raw[key] != v:  # duplicate labels (e.g. Lieu_Naissance ×2)
            key, n = f"{k} ({n})", n + 1
        raw[key] = v

    photo_url = ""
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if src and "logo" not in src.lower():
            photo_url = src
            break

    fields = {name: raw.get(label, "") for name, label in _FIELD_LABELS.items()}
    return StudentProfile(photo_url=photo_url, raw=raw, **fields)
