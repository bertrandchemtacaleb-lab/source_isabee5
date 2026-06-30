"""
apercu_documents.py
--------------------
Module ajoute apres coup au projet deja en production (voir
README.md de la V4) : genere un apercu visuel (images PNG) des
premieres pages d'un document PDF deja depose, afin qu'un utilisateur
connecte puisse voir un extrait avant de payer/telecharger le document
complet -- typiquement utile pour une epreuve, ou seules les premieres
pages (enonce) seraient montrees, jamais le corrige complet ni les
reponses.

INTEGRATION : DEJA FAITE, AUCUNE ACTION MANUELLE NECESSAIRE.
Ce module est deja branche automatiquement dans le reste du projet :
- archive_manager.ajouter_document() genere l'apercu a chaque nouveau
  depot de document (import local, jamais bloquant : un echec de
  generation d'apercu n'empeche jamais le depot du document lui-meme).
- archive_manager.supprimer_definitivement() efface aussi les images
  d'apercu quand un document est efface de la corbeille.
- app.py (page_bibliotheque) affiche l'apercu sur la carte de chaque
  document, uniquement pour un utilisateur connecte.
- admin.py (page_maintenance, onglet "Nettoyage et cache") propose un
  bouton "Generer les apercus manquants" pour les documents deposes
  avant l'ajout de cette fonctionnalite.
- requirements.txt liste deja "pymupdf" : sur Streamlit Cloud,
  l'installation se fait automatiquement a chaque deploiement/push
  GitHub, sans aucune commande a executer manuellement.

Si pymupdf n'est pas (encore) installe -- par exemple juste apres un
premier push avant que Streamlit Cloud n'ait fini de reconstruire
l'environnement -- toutes les fonctions de ce module se degradent
silencieusement (voir pymupdf_disponible) : aucune erreur visible,
l'apercu est simplement absent jusqu'au redeploiement complet.

Ce module cree et gere son propre dossier de stockage (data/apercus/),
sans toucher au schema de la base de donnees : le chemin de l'apercu
est calcule a la volee a partir de l'identifiant du document, jamais
stocke en base. Aucune migration necessaire.
"""

from pathlib import Path

import streamlit as st

from database import DOCUMENTS_DIR, BASE_DIR
from auth import utilisateur_courant
from utils import icone

APERCUS_DIR = BASE_DIR / "data" / "apercus"
APERCUS_DIR.mkdir(parents=True, exist_ok=True)

NOMBRE_PAGES_APERCU_DEFAUT = 2
DPI_RENDU_APERCU = 130  # qualite suffisante pour un apercu a l'ecran, fichier leger


def pymupdf_disponible() -> bool:
    """
    Vrai si la bibliotheque pymupdf est installee. Degradation
    silencieuse si absente : l'apercu n'est simplement pas propose,
    sans aucune erreur visible pour l'utilisateur (meme principe que
    les autres fonctionnalites optionnelles du projet, ex. la
    connexion Google/Microsoft si non configuree).
    """
    try:
        import fitz  # noqa: F401
        return True
    except ImportError:
        return False


def _chemin_apercu(document_id: int, numero_page: int) -> Path:
    return APERCUS_DIR / f"apercu_{document_id}_page{numero_page}.png"


def apercu_deja_genere(document_id: int, nombre_pages: int = NOMBRE_PAGES_APERCU_DEFAUT) -> bool:
    """Vrai si toutes les images d'apercu existent deja sur le disque pour ce document."""
    return all(_chemin_apercu(document_id, p).is_file() for p in range(1, nombre_pages + 1))


def generer_apercu(document_id: int, chemin_pdf: str,
                    nombre_pages: int = NOMBRE_PAGES_APERCU_DEFAUT) -> tuple[bool, str]:
    """
    Genere (ou regenere) les images d'apercu des premieres pages d'un
    document PDF deja enregistre sur le disque (voir
    archive_manager.ajouter_document, qui appelle enregistrer_pdf).

    Ne modifie jamais le fichier PDF d'origine : lecture seule. Si le
    PDF compte moins de pages que nombre_pages, genere un apercu pour
    toutes les pages disponibles (aucune erreur dans ce cas, juste un
    apercu plus court).

    A appeler une seule fois au moment du depot du document (voir
    POINTS D'INTEGRATION) ; peut etre rappele a tout moment pour
    regenerer l'apercu (ex. si le fichier PDF a ete remplace).
    """
    if not pymupdf_disponible():
        return False, "Apercu non disponible : la bibliotheque pymupdf n'est pas installee."

    if not Path(chemin_pdf).is_file():
        return False, "Fichier PDF introuvable."

    import fitz

    try:
        document_pdf = fitz.open(chemin_pdf)
    except Exception as erreur:
        return False, f"Impossible de lire le PDF pour generer l'apercu : {erreur}"

    try:
        nombre_pages_reel = min(nombre_pages, document_pdf.page_count)
        if nombre_pages_reel == 0:
            return False, "Le document PDF ne contient aucune page."

        zoom = DPI_RENDU_APERCU / 72  # 72 DPI est la resolution de base de PyMuPDF
        matrice = fitz.Matrix(zoom, zoom)

        for index_page in range(nombre_pages_reel):
            page = document_pdf[index_page]
            pixmap = page.get_pixmap(matrix=matrice)
            chemin_sortie = _chemin_apercu(document_id, index_page + 1)
            pixmap.save(str(chemin_sortie))
    finally:
        document_pdf.close()

    return True, f"Apercu genere ({nombre_pages_reel} page(s))."


def supprimer_apercu(document_id: int, nombre_pages_max: int = 20) -> None:
    """
    Supprime toutes les images d'apercu existantes pour un document
    (a appeler quand le document lui-meme est supprime, pour ne pas
    laisser de fichiers orphelins sur le disque -- voir
    maintenance.detecter_fichiers_orphelins, qui ne connait pas encore
    ce dossier puisqu'il a ete ajoute apres coup ; voir POINTS
    D'INTEGRATION pour l'inclure si souhaite).
    """
    for numero_page in range(1, nombre_pages_max + 1):
        chemin = _chemin_apercu(document_id, numero_page)
        if chemin.is_file():
            chemin.unlink()
        else:
            break


def afficher_apercu_document(document, nombre_pages: int = NOMBRE_PAGES_APERCU_DEFAUT) -> None:
    """
    Affiche l'apercu visuel d'un document (premieres pages, en images),
    reserve aux utilisateurs connectes -- conformement au choix retenu :
    un visiteur non connecte ne voit jamais cet apercu, meme si le
    document est par ailleurs payant ou gratuit.

    A inserer dans la carte d'un document, en complement de ce qui
    existe deja (image de couverture V4, titre, description...) : voir
    POINTS D'INTEGRATION pour l'endroit exact dans app.py.

    N'affiche rien (silencieusement) si : l'utilisateur n'est pas
    connecte, pymupdf n'est pas installe, ou l'apercu n'a pas encore
    ete genere pour ce document (cas d'un document depose avant
    l'ajout de cette fonctionnalite -- voir generer_apercus_manquants
    pour rattraper les documents existants en une fois).
    """
    if utilisateur_courant() is None:
        return
    if not apercu_deja_genere(document.id, nombre_pages):
        return

    with st.popover("Apercu de l'epreuve", icon=icone("Search"), use_container_width=False):
        st.caption(
            f"Extrait des {nombre_pages} premiere(s) page(s). Le document complet "
            f"reste soumis aux conditions d'acces habituelles (gratuit ou payant)."
        )
        for numero_page in range(1, nombre_pages + 1):
            chemin = _chemin_apercu(document.id, numero_page)
            if chemin.is_file():
                st.image(str(chemin), use_container_width=True)


def generer_apercus_manquants(limite: int = 50) -> tuple[int, int]:
    """
    Parcourt les documents deja en base et genere l'apercu pour ceux
    qui n'en ont pas encore (cas normal pour TOUS les documents
    deposes avant l'ajout de cette fonctionnalite a une application
    deja en production). A appeler une fois, depuis une page
    d'administration ou un script ponctuel -- voir POINTS
    D'INTEGRATION pour un exemple de bouton admin.

    Retourne (nombre_traites, nombre_echecs).
    """
    from database import recuperer_tous  # import local pour eviter une dependance circulaire au chargement du module

    documents = recuperer_tous(
        "SELECT id, chemin_fichier FROM subjects WHERE supprime = 0 LIMIT ?", (limite,)
    )
    nombre_traites = 0
    nombre_echecs = 0
    for ligne in documents:
        if apercu_deja_genere(ligne["id"]):
            continue
        succes, _message = generer_apercu(ligne["id"], ligne["chemin_fichier"])
        if succes:
            nombre_traites += 1
        else:
            nombre_echecs += 1
    return nombre_traites, nombre_echecs

