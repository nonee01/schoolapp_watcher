//! The student profile on /index (`schoolapp/extractors/profile.py`).
//!
//! Both blocks (Situation Administrative, Données personnelles) are vertical
//! `<tr><th>label</th><td>value</td></tr>` tables.

use std::sync::LazyLock;

use scraper::{Html, Selector};

use super::tables::{TR, field, text_of};
use crate::models::{Raw, StudentProfile};

static CELL: LazyLock<Selector> = LazyLock::new(|| Selector::parse("th, td").expect("static selector"));
static IMG: LazyLock<Selector> = LazyLock::new(|| Selector::parse("img").expect("static selector"));

pub fn parse_profile(html: &str) -> StudentProfile {
    let doc = Html::parse_document(html);
    let mut raw = Raw::new();
    for tr in doc.select(&TR) {
        let cells: Vec<_> = tr.select(&CELL).collect();
        if cells.len() != 2 || cells[0].value().name() != "th" {
            continue;
        }
        let label = text_of(cells[0]);
        let value = text_of(cells[1]);
        if label.is_empty() {
            continue;
        }
        // Duplicate labels (e.g. Lieu_Naissance twice) become "Label (2)", "Label (3)"…
        let (mut key, mut n) = (label.clone(), 2);
        while raw.get(&key).is_some_and(|existing| *existing != value) {
            key = format!("{label} ({n})");
            n += 1;
        }
        raw.insert(key, value);
    }
    let photo_url = doc
        .select(&IMG)
        .filter_map(|img| img.value().attr("src"))
        .find(|src| !src.is_empty() && !src.to_lowercase().contains("logo"))
        .unwrap_or_default()
        .to_string();
    StudentProfile {
        code: field(&raw, "Code"),
        cne_masar: field(&raw, "CNE/Masar"),
        nom: field(&raw, "Nom"),
        prenom: field(&raw, "Prénom"),
        nom_ar: field(&raw, "Nom Arabe"),
        prenom_ar: field(&raw, "Prénom Arabe"),
        cin: field(&raw, "CIN"),
        sexe: field(&raw, "Sexe"),
        date_naissance: field(&raw, "Date Naissance"),
        email: field(&raw, "Email"),
        filiere: field(&raw, "Filière"),
        niveau: field(&raw, "Niveau"),
        statut: field(&raw, "Statut"),
        section: field(&raw, "Section"),
        groupe: field(&raw, "Groupe"),
        sous_groupe: field(&raw, "Sous Groupe"),
        photo_url,
        raw,
    }
}
