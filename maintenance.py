"""
maintenance.py
---------------
Role : regrouper les operations d'administration systeme attendues
d'une plateforme prete pour la commercialisation (cahier des charges
V4, point 7) :
- activer / desactiver le mode maintenance (deja existant depuis la V2
  via settings.py -- ce module n'en duplique pas la logique, voir
  admin.page_maintenance qui reutilise settings.definir_parametre) ;
- sauvegarder et restaurer la base de donnees SQLite ;
- nettoyer les fichiers orphelins (photos, preuves de paiement,
  couvertures de documents et fichiers PDF qui ne sont plus
  reference par aucune ligne en base) ;
- vider les caches Streamlit (st.cache_resource / st.cache_data) ;
- optimiser la base (VACUUM, ANALYZE) ;
- mesurer l'espace de stockage utilise par categorie.

Ce module ne realise aucun affichage : il est consomme par admin.py
(page_maintenance, reservee a l'administration). Toute action
destructrice (restauration, nettoyage) est journalisee comme les
autres actions sensibles de l'application (voir utils.journaliser).

Limite assumee, documentee pour un futur audit : la sauvegarde ne
couvre que le fichier de base de donnees SQLite (via VACUUM INTO,
copie coherente meme si l'application est en cours d'utilisation),
PAS les fichiers binaires (PDF, photos, preuves, couvertures), qui
restent a sauvegarder separement (copie de /data au niveau du systeme
de fichiers, hors du cadre de cette interface). Ce choix evite de
generer des archives potentiellement tres volumineuses depuis
l'interface web elle-meme.
"""

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

import streamlit as st

from database import (
    DB_PATH, BACKUPS_DIR, DOCUMENTS_DIR, PHOTOS_DIR, PREUVES_DIR, COUVERTURES_DIR,
    recuperer_tous,
)
from utils import journaliser

FORMAT_HORODATAGE = "%Y%m%d_%H%M%S"
NOMBRE_SAUVEGARDES_CONSERVEES = 10


# =====================================================================
# Sauvegarde et restauration de la base de donnees
# =====================================================================

def creer_sauvegarde(cree_par: int) -> tuple[bool, str]:
    """
    Cree une copie coherente de la base de donnees SQLite via
    VACUUM INTO (disponible depuis SQLite 3.27+, voir requirements de
    l'environnement d'execution) : cette methode produit une copie
    propre et utilisable meme si l'application recoit des requetes en
    parallele, contrairement a une simple copie de fichier qui
    risquerait de capturer une ecriture en cours.

    Les NOMBRE_SAUVEGARDES_CONSERVEES sauvegardes les plus recentes
    sont conservees ; les plus anciennes sont supprimees
    automatiquement afin d'eviter une croissance illimitee du dossier
    de sauvegardes.
    """
    horodatage = datetime.now().strftime(FORMAT_HORODATAGE)
    chemin_sauvegarde = BACKUPS_DIR / f"source_isabee_{horodatage}.db"
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(f"VACUUM INTO '{chemin_sauvegarde}'")
    except sqlite3.Error as erreur:
        return False, f"Echec de la sauvegarde : {erreur}"

    journaliser("Creation sauvegarde base de donnees", "succes", user_id=cree_par,
                details=chemin_sauvegarde.name)
    _purger_anciennes_sauvegardes()
    return True, f"Sauvegarde creee : {chemin_sauvegarde.name}"


def _purger_anciennes_sauvegardes() -> None:
    """Conserve uniquement les NOMBRE_SAUVEGARDES_CONSERVEES sauvegardes les plus recentes."""
    sauvegardes = sorted(BACKUPS_DIR.glob("source_isabee_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for ancienne in sauvegardes[NOMBRE_SAUVEGARDES_CONSERVEES:]:
        ancienne.unlink(missing_ok=True)


def lister_sauvegardes() -> list[dict]:
    """
    Sauvegardes disponibles, les plus recentes en premier, avec leur
    taille et date de creation, pour l'affichage administrateur.
    """
    sauvegardes = sorted(BACKUPS_DIR.glob("source_isabee_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [
        {
            "nom": p.name,
            "chemin": str(p),
            "taille_ko": p.stat().st_size // 1024,
            "date_creation": datetime.fromtimestamp(p.stat().st_mtime),
        }
        for p in sauvegardes
    ]


def restaurer_sauvegarde(nom_fichier: str, restaure_par: int) -> tuple[bool, str]:
    """
    Restaure la base de donnees a partir d'une sauvegarde existante.
    Une sauvegarde de securite de la base ACTUELLE est d'abord creee
    automatiquement (prefixe "avant_restauration_"), afin qu'une
    restauration accidentelle reste elle-meme reversible.

    Attention : cette operation remplace entierement le contenu actuel
    de la base par celui de la sauvegarde choisie. A utiliser avec
    prudence, et seulement apres avoir verifie la date de la
    sauvegarde dans lister_sauvegardes().
    """
    chemin_sauvegarde = BACKUPS_DIR / nom_fichier
    if not chemin_sauvegarde.is_file() or not nom_fichier.startswith("source_isabee_"):
        return False, "Fichier de sauvegarde introuvable ou invalide."

    horodatage = datetime.now().strftime(FORMAT_HORODATAGE)
    chemin_securite = BACKUPS_DIR / f"avant_restauration_{horodatage}.db"
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(f"VACUUM INTO '{chemin_securite}'")
    except sqlite3.Error as erreur:
        return False, f"Restauration annulee : impossible de creer la sauvegarde de securite ({erreur})."

    try:
        shutil.copyfile(chemin_sauvegarde, DB_PATH)
    except OSError as erreur:
        return False, f"Echec de la restauration : {erreur}"

    journaliser("Restauration base de donnees", "succes", user_id=restaure_par, details=nom_fichier)
    return True, (
        f"Base de donnees restauree depuis {nom_fichier}. "
        f"Une sauvegarde de l'etat precedent a ete conservee ({chemin_securite.name})."
    )


def supprimer_sauvegarde(nom_fichier: str, supprime_par: int) -> tuple[bool, str]:
    chemin = BACKUPS_DIR / nom_fichier
    if not chemin.is_file():
        return False, "Fichier de sauvegarde introuvable."
    chemin.unlink()
    journaliser("Suppression sauvegarde", "succes", user_id=supprime_par, details=nom_fichier)
    return True, "Sauvegarde supprimee."


# =====================================================================
# Nettoyage des fichiers orphelins
# =====================================================================

def _chemins_references(colonne: str, table: str) -> set[str]:
    lignes = recuperer_tous(f"SELECT {colonne} FROM {table} WHERE {colonne} IS NOT NULL")
    return {str(Path(l[colonne]).resolve()) for l in lignes if l[colonne]}


def detecter_fichiers_orphelins() -> dict[str, list[Path]]:
    """
    Recense, par categorie, les fichiers presents sur le disque mais
    qui ne sont plus reference par aucune ligne en base (le document,
    la photo ou la preuve correspondante a ete supprime de la table,
    mais le fichier physique n'avait pas ete efface -- ce qui ne
    devrait plus se produire pour les flux normaux de l'application,
    qui appellent systematiquement supprimer_fichier, mais peut rester
    necessaire apres une restauration partielle ou une migration
    manuelle).

    Ne supprime rien : seulement la detection. Voir nettoyer_fichiers_orphelins.
    """
    documents_references = _chemins_references("chemin_fichier", "subjects")
    photos_references = _chemins_references("photo", "users")
    preuves_referencees = _chemins_references("capture_preuve", "payments")
    couvertures_referencees = _chemins_references("image_couverture", "subjects")

    resultat: dict[str, list[Path]] = {"documents": [], "photos": [], "preuves": [], "couvertures": []}
    for fichier in DOCUMENTS_DIR.glob("*"):
        if fichier.is_file() and str(fichier.resolve()) not in documents_references:
            resultat["documents"].append(fichier)
    for fichier in PHOTOS_DIR.glob("*"):
        if fichier.is_file() and str(fichier.resolve()) not in photos_references:
            resultat["photos"].append(fichier)
    for fichier in PREUVES_DIR.glob("*"):
        if fichier.is_file() and str(fichier.resolve()) not in preuves_referencees:
            resultat["preuves"].append(fichier)
    for fichier in COUVERTURES_DIR.glob("*"):
        if fichier.is_file() and str(fichier.resolve()) not in couvertures_referencees:
            resultat["couvertures"].append(fichier)
    return resultat


def nettoyer_fichiers_orphelins(nettoye_par: int) -> tuple[int, int]:
    """
    Supprime du disque tous les fichiers orphelins detectes par
    detecter_fichiers_orphelins(). Retourne (nombre_fichiers_supprimes,
    espace_libere_ko).
    """
    orphelins = detecter_fichiers_orphelins()
    nombre_supprimes = 0
    espace_libere_octets = 0
    for fichiers in orphelins.values():
        for fichier in fichiers:
            try:
                espace_libere_octets += fichier.stat().st_size
                fichier.unlink()
                nombre_supprimes += 1
            except OSError:
                continue

    if nombre_supprimes:
        journaliser("Nettoyage fichiers orphelins", "succes", user_id=nettoye_par,
                    details=f"{nombre_supprimes} fichier(s) supprime(s)")
    return nombre_supprimes, espace_libere_octets // 1024


# =====================================================================
# Cache applicatif
# =====================================================================

def vider_cache(vide_par: int) -> None:
    """
    Vide tous les caches Streamlit (st.cache_resource et
    st.cache_data) de ce processus serveur. A utiliser apres une
    restauration de sauvegarde ou en cas de comportement incoherent
    de l'interface, pour forcer le recalcul de toute donnee mise en
    cache (par exemple le gestionnaire de cookies, voir
    app._gestionnaire_cookies).
    """
    st.cache_resource.clear()
    st.cache_data.clear()
    journaliser("Vidage du cache applicatif", "succes", user_id=vide_par)


# =====================================================================
# Optimisation de la base
# =====================================================================

def optimiser_base(optimise_par: int) -> tuple[bool, str]:
    """
    Execute VACUUM (defragmente le fichier, recupere l'espace des
    lignes supprimees) puis ANALYZE (met a jour les statistiques
    utilisees par le planificateur de requetes SQLite) sur la base de
    production. Operation sans risque pour les donnees (ne modifie
    aucune ligne), mais qui necessite un acces exclusif bref a la base :
    a reserver a une periode de faible activite si la plateforme est
    deja utilisee par de nombreux comptes simultanement.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("VACUUM")
            conn.execute("ANALYZE")
    except sqlite3.Error as erreur:
        return False, f"Echec de l'optimisation : {erreur}"

    journaliser("Optimisation base de donnees", "succes", user_id=optimise_par)
    return True, "Base de donnees optimisee (VACUUM + ANALYZE)."


# =====================================================================
# Stockage
# =====================================================================

def _taille_dossier_ko(dossier: Path) -> int:
    if not dossier.exists():
        return 0
    return sum(f.stat().st_size for f in dossier.glob("**/*") if f.is_file()) // 1024


def statistiques_stockage() -> dict:
    """
    Espace disque utilise par categorie (documents PDF, photos de
    profil, preuves de paiement Mobile Money, images de couverture,
    sauvegardes, base de donnees elle-meme), pour l'affichage du
    tableau de bord de maintenance.
    """
    taille_db_ko = DB_PATH.stat().st_size // 1024 if DB_PATH.exists() else 0
    return {
        "documents_ko": _taille_dossier_ko(DOCUMENTS_DIR),
        "photos_ko": _taille_dossier_ko(PHOTOS_DIR),
        "preuves_ko": _taille_dossier_ko(PREUVES_DIR),
        "couvertures_ko": _taille_dossier_ko(COUVERTURES_DIR),
        "sauvegardes_ko": _taille_dossier_ko(BACKUPS_DIR),
        "base_donnees_ko": taille_db_ko,
    }


# =====================================================================
# Utilisateurs actuellement connectes (approximation)
# =====================================================================

def utilisateurs_connectes_recents(minutes: int = 15) -> list[dict]:
    """
    Approximation des utilisateurs "actuellement connectes" : ceux dont
    la derniere connexion remonte a moins de `minutes` minutes.
    Streamlit ne fournit pas de registre centralise des sessions
    actives entre plusieurs processus serveur ; cette fonction est une
    estimation a partir des journaux d'activite, suffisante pour un
    apercu administratif, pas pour une deconnexion forcee en temps reel.
    """
    lignes = recuperer_tous(
        """
        SELECT nom, prenom, matricule, role, derniere_connexion FROM users
        WHERE derniere_connexion IS NOT NULL
          AND datetime(derniere_connexion) >= datetime('now', ?)
        ORDER BY derniere_connexion DESC
        """,
        (f"-{minutes} minutes",),
    )
    return [dict(l) for l in lignes]
