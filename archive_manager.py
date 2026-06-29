"""
archive_manager.py
-------------------
Role : gerer le cycle de vie complet des documents pedagogiques
(epreuves, examens, corriges, travaux pratiques, supports de cours)
stockes dans la table subjects.

Responsabilites :
- ajout d'un document avec son fichier PDF et sa regle d'acces
  (gratuit ou payant) ;
- modification des metadonnees ;
- suppression (fichier + enregistrement) ;
- circuit de validation avant publication, avec notification
  automatique de l'auteur ;
- recherche multicritere paginee (cycle, filiere, niveau, annee,
  type, enseignant) ;
- gestion des favoris et des telechargements.

Ce module ne realise aucun affichage : il est consomme par app.py
(espace etudiant/enseignant) et par admin.py (moderation).

Correctifs apportes en V2 (voir audit) :
- le fichier televerse est desormais reellement valide (extension,
  taille, signature binaire) avant tout enregistrement sur le disque,
  via utils.fichier_est_pdf_valide. En V1, cette fonction existait
  mais n'etait jamais appelee : seul le filtre d'extension du widget
  Streamlit agissait, et un fichier renomme passait sans controle.
- rechercher_documents() accepte desormais une pagination (limite,
  decalage) : en V1, une recherche sans filtre renvoyait l'integralite
  de la table, ce qui devient inexploitable a l'echelle d'un
  etablissement.

Nouveau en V3 (corbeille, voir audit-isabee-v2.md) :
- supprimer_document() ne supprime plus immediatement et
  definitivement un document : il le deplace vers la corbeille
  (suppression reversible). Le fichier PDF reste sur le disque tant
  que le document est dans la corbeille.
- toutes les fonctions de listage destinees a un affichage normal
  (rechercher_documents, documents_recents, documents_en_attente,
  favoris_utilisateur) excluent desormais les documents en corbeille,
  afin qu'un document "supprime" disparaisse bien de la bibliotheque
  comme avant -- seul son emplacement de stockage a change.
- voir documents_dans_corbeille, restaurer_document,
  supprimer_definitivement et vider_corbeille pour la gestion de la
  corbeille (reservee a l'administration, voir admin.py).

Nouveau en V3, deuxieme vague :
- la recherche par terme libre (rechercher_documents, compter_documents)
  utilise desormais la recherche plein texte (FTS5) quand elle est
  disponible sur l'installation (voir database.recherche_plein_texte_disponible),
  avec repli automatique et transparent sur l'ancienne recherche LIKE
  sinon -- signature et comportement strictement identiques pour
  tous les appelants existants.
- rechercher_documents/compter_documents acceptent un parametre
  optionnel tag_id pour filtrer par tag (voir creer_tag, tags_disponibles,
  associer_tags_document).
- importer_documents_en_masse() permet de deposer plusieurs PDF en une
  seule operation, en reutilisant entierement ajouter_document (aucune
  regle de validation dupliquee).
"""

from datetime import datetime

import database
from database import executer, recuperer_un, recuperer_tous
from models import Document, PRIX_DOCUMENT_PAYANT_DEFAUT
from utils import (
    enregistrer_pdf, supprimer_fichier, journaliser, fichier_est_pdf_valide,
    fichier_est_couverture_valide, enregistrer_image_couverture,
)
import communication

FORMAT_DATE_HEURE = "%Y-%m-%d %H:%M:%S"


def ajouter_document(titre: str, description: str, type_document: str, cycle: str,
                      filiere: str, niveau: str, annee_academique: str,
                      enseignant_id: int | None, fichier_televerse,
                      ajoute_par: int, type_acces: str = "gratuit",
                      prix: int = 0, taille_max_pdf_mo: int = 25,
                      image_couverture_televersee=None) -> tuple[bool, str]:
    """
    Enregistre un nouveau document. Le document est cree avec le statut
    'en_attente' : il ne sera visible des etudiants qu'apres validation
    par un enseignant, un contributeur habilite ou un administrateur.

    Le fichier est verifie (extension, taille, signature binaire
    reelle) avant tout enregistrement sur le disque. Un document
    payant sans prix renseigne recoit le prix par defaut de la
    plateforme plutot que d'etre enregistre a 0 FCFA par erreur.

    image_couverture_televersee est entierement optionnel (nouveau en
    V4) : un visuel de presentation affiche dans la bibliotheque, en
    complement du fichier PDF (jamais a sa place). Si fourni mais
    invalide (format ou taille), le document est tout de meme enregistre
    sans couverture plutot que de faire echouer tout le depot pour un
    champ secondaire -- seul un message d'avertissement est renvoye.
    """
    valide, message_erreur = fichier_est_pdf_valide(fichier_televerse, taille_max_pdf_mo)
    if not valide:
        return False, message_erreur

    if type_acces == "payant" and prix <= 0:
        prix = PRIX_DOCUMENT_PAYANT_DEFAUT

    chemin_couverture = None
    avertissement_couverture = ""
    if image_couverture_televersee is not None:
        couverture_valide, message_couverture = fichier_est_couverture_valide(image_couverture_televersee)
        if couverture_valide:
            chemin_couverture = enregistrer_image_couverture(image_couverture_televersee)
        else:
            avertissement_couverture = f" (image de couverture ignoree : {message_couverture})"

    chemin_fichier, taille_ko = enregistrer_pdf(fichier_televerse)
    executer(
        """
        INSERT INTO subjects (titre, description, type_document, cycle, filiere, niveau,
                               annee_academique, enseignant_id, chemin_fichier,
                               taille_fichier_ko, type_acces, prix, mode_paiement,
                               statut, ajoute_par, image_couverture)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'presentiel', 'en_attente', ?, ?)
        """,
        (titre, description, type_document, cycle, filiere, niveau, annee_academique,
         enseignant_id, chemin_fichier, taille_ko, type_acces,
         prix if type_acces == "payant" else 0, ajoute_par, chemin_couverture),
    )
    journaliser("Ajout document", "succes", user_id=ajoute_par, details=titre)
    return True, f"Document soumis. Il sera visible apres validation.{avertissement_couverture}"


def modifier_document(document_id: int, modifie_par: int, **champs) -> tuple[bool, str]:
    champs_autorises = {
        "titre", "description", "type_document", "cycle", "filiere",
        "niveau", "annee_academique", "enseignant_id", "type_acces", "prix",
        "image_couverture",
    }
    a_mettre_a_jour = {k: v for k, v in champs.items() if k in champs_autorises}
    if not a_mettre_a_jour:
        return False, "Aucun champ valide a mettre a jour."

    assignations = ", ".join(f"{champ} = ?" for champ in a_mettre_a_jour)
    valeurs = list(a_mettre_a_jour.values()) + [document_id]
    executer(f"UPDATE subjects SET {assignations} WHERE id = ?", tuple(valeurs))
    journaliser("Modification document", "succes", user_id=modifie_par, details=str(document_id))
    return True, "Document mis a jour."


def supprimer_document(document_id: int, supprime_par: int) -> tuple[bool, str]:
    """
    Deplace un document vers la corbeille (suppression reversible),
    au lieu de l'effacer immediatement et definitivement comme en V2.
    Le fichier PDF reste sur le disque tant que le document est dans
    la corbeille : seule supprimer_definitivement l'efface vraiment.
    Voir aussi restaurer_document.
    """
    document = obtenir_document(document_id)
    if document is None:
        return False, "Document introuvable."
    if document.supprime:
        return False, "Ce document est deja dans la corbeille."
    executer(
        "UPDATE subjects SET supprime = 1, supprime_le = ?, supprime_par = ? WHERE id = ?",
        (datetime.now().strftime(FORMAT_DATE_HEURE), supprime_par, document_id),
    )
    journaliser("Mise en corbeille document", "succes", user_id=supprime_par, details=document.titre)
    return True, "Document deplace vers la corbeille."


def documents_dans_corbeille() -> list[dict]:
    """
    Documents actuellement dans la corbeille, avec l'identite de qui
    les a supprimes, pretes pour l'affichage administrateur (voir
    admin.page_gestion_corbeille).
    """
    lignes = recuperer_tous(
        """
        SELECT s.*, u.nom AS nom_suppresseur, u.prenom AS prenom_suppresseur
        FROM subjects s
        LEFT JOIN users u ON u.id = s.supprime_par
        WHERE s.supprime = 1
        ORDER BY s.supprime_le DESC
        """
    )
    return [dict(l) for l in lignes]


def nombre_documents_corbeille() -> int:
    ligne = recuperer_un("SELECT COUNT(*) AS total FROM subjects WHERE supprime = 1")
    return ligne["total"] if ligne else 0


def restaurer_document(document_id: int, restaure_par: int) -> tuple[bool, str]:
    """Sort un document de la corbeille et lui rend sa visibilite normale."""
    document = obtenir_document(document_id)
    if document is None:
        return False, "Document introuvable."
    if not document.supprime:
        return False, "Ce document n'est pas dans la corbeille."
    executer(
        "UPDATE subjects SET supprime = 0, supprime_le = NULL, supprime_par = NULL WHERE id = ?",
        (document_id,),
    )
    journaliser("Restauration document", "succes", user_id=restaure_par, details=document.titre)
    return True, "Document restaure."


def supprimer_definitivement(document_id: int, supprime_par: int) -> tuple[bool, str]:
    """
    Efface irreversiblement un document deja present dans la
    corbeille (fichier PDF + enregistrement en base). Reserve a
    l'administration : a la difference de supprimer_document (mise en
    corbeille, reversible), cette action ne peut plus etre annulee.
    """
    document = obtenir_document(document_id)
    if document is None:
        return False, "Document introuvable."
    if not document.supprime:
        return False, "Seul un document deja present dans la corbeille peut etre supprime definitivement."
    supprimer_fichier(document.chemin_fichier)
    executer("DELETE FROM subjects WHERE id = ?", (document_id,))
    journaliser("Suppression definitive document", "succes", user_id=supprime_par, details=document.titre)
    return True, "Document supprime definitivement."


def vider_corbeille(supprime_par: int) -> int:
    """
    Supprime definitivement tous les documents actuellement en
    corbeille. Retourne le nombre de documents traites.
    """
    documents = documents_dans_corbeille()
    for d in documents:
        supprimer_definitivement(d["id"], supprime_par)
    return len(documents)


def valider_document(document_id: int, valide_par: int) -> tuple[bool, str]:
    document = obtenir_document(document_id)
    executer(
        "UPDATE subjects SET statut = 'valide', valide_par = ?, date_validation = ? WHERE id = ?",
        (valide_par, datetime.now().strftime(FORMAT_DATE_HEURE), document_id),
    )
    journaliser("Validation document", "succes", user_id=valide_par, details=str(document_id))
    if document and document.ajoute_par:
        communication.creer_notification(
            document.ajoute_par,
            f'Votre document "{document.titre}" a ete valide et publie.',
            "validation", document_id,
        )
    return True, "Document valide et publie."


def rejeter_document(document_id: int, rejete_par: int, motif: str) -> tuple[bool, str]:
    document = obtenir_document(document_id)
    executer(
        """
        UPDATE subjects SET statut = 'rejete', valide_par = ?, date_validation = ?, motif_rejet = ?
        WHERE id = ?
        """,
        (rejete_par, datetime.now().strftime(FORMAT_DATE_HEURE), motif, document_id),
    )
    journaliser("Rejet document", "succes", user_id=rejete_par, details=f"{document_id} - {motif}")
    if document and document.ajoute_par:
        communication.creer_notification(
            document.ajoute_par,
            f'Votre document "{document.titre}" a ete rejete. Motif : {motif}',
            "validation", document_id,
        )
    return True, "Document rejete."


def obtenir_document(document_id: int) -> Document | None:
    ligne = recuperer_un("SELECT * FROM subjects WHERE id = ?", (document_id,))
    return Document.depuis_ligne(ligne) if ligne else None


def documents_en_attente() -> list[Document]:
    lignes = recuperer_tous(
        "SELECT * FROM subjects WHERE statut = 'en_attente' AND supprime = 0 ORDER BY date_ajout"
    )
    return [Document.depuis_ligne(l) for l in lignes]


def documents_recents(limite: int = 10) -> list[Document]:
    lignes = recuperer_tous(
        "SELECT * FROM subjects WHERE statut = 'valide' AND supprime = 0 ORDER BY date_ajout DESC LIMIT ?",
        (limite,),
    )
    return [Document.depuis_ligne(l) for l in lignes]


def _construire_requete_fts(terme: str) -> str:
    """
    Construit une requete FTS5 sure a partir d'un terme de recherche
    libre saisi par l'utilisateur : chaque mot est mis entre guillemets
    (neutralise les caracteres speciaux de la syntaxe FTS5 tels que
    *, -, : ...) et suivi d'un asterisque pour une correspondance par
    prefixe ; les mots sont implicitement combines par ET.
    """
    mots = [m.replace('"', '""') for m in terme.split() if m]
    return " ".join(f'"{m}"*' for m in mots) if mots else '""'


def _construire_conditions(terme: str, cycle: str, filiere: str, niveau: str, annee: str,
                            type_document: str, enseignant_id: int | None,
                            uniquement_valides: bool, tag_id: int | None = None) -> tuple[list[str], list]:
    """
    Factorise la construction des criteres communs a
    rechercher_documents et compter_documents.

    Exclut toujours les documents en corbeille (supprime = 0) : ces
    deux fonctions servent a l'affichage normal (bibliotheque,
    gestion des documents), jamais a la corbeille elle-meme, qui
    dispose de sa propre fonction dediee (documents_dans_corbeille).
    """
    conditions = ["supprime = 0"]
    parametres: list = []

    if uniquement_valides:
        conditions.append("statut = 'valide'")
    if terme:
        if database.recherche_plein_texte_disponible():
            conditions.append("id IN (SELECT rowid FROM subjects_fts WHERE subjects_fts MATCH ?)")
            parametres.append(_construire_requete_fts(terme))
        else:
            conditions.append("(titre LIKE ? OR description LIKE ?)")
            parametres += [f"%{terme}%", f"%{terme}%"]
    if tag_id is not None:
        conditions.append("id IN (SELECT document_id FROM document_tags WHERE tag_id = ?)")
        parametres.append(tag_id)
    if cycle:
        conditions.append("cycle = ?")
        parametres.append(cycle)
    if filiere:
        conditions.append("filiere = ?")
        parametres.append(filiere)
    if niveau:
        conditions.append("niveau = ?")
        parametres.append(niveau)
    if annee:
        conditions.append("annee_academique = ?")
        parametres.append(annee)
    if type_document:
        conditions.append("type_document = ?")
        parametres.append(type_document)
    if enseignant_id:
        conditions.append("enseignant_id = ?")
        parametres.append(enseignant_id)

    return conditions, parametres


def rechercher_documents(terme: str = "", cycle: str = "", filiere: str = "",
                          niveau: str = "", annee: str = "", type_document: str = "",
                          enseignant_id: int | None = None,
                          uniquement_valides: bool = True,
                          limite: int | None = 20, decalage: int = 0,
                          tag_id: int | None = None) -> list[Document]:
    """
    Recherche multicritere parmi les documents. Tous les criteres sont
    optionnels et combinables (ET logique). Par defaut, seuls les
    documents valides sont retournes (consultation cote etudiant).

    Paginee par defaut (20 resultats) : passer limite=None pour
    desactiver la pagination (usage interne uniquement, a eviter pour
    tout affichage destine a un utilisateur).

    Le terme libre utilise la recherche plein texte (FTS5) si elle est
    disponible sur l'installation, avec repli automatique sur
    l'ancienne recherche LIKE sinon (voir _construire_conditions).
    """
    conditions, parametres = _construire_conditions(
        terme, cycle, filiere, niveau, annee, type_document, enseignant_id, uniquement_valides, tag_id
    )
    clause_where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    requete = f"SELECT * FROM subjects {clause_where} ORDER BY date_ajout DESC"
    if limite is not None:
        requete += " LIMIT ? OFFSET ?"
        parametres = parametres + [limite, decalage]
    lignes = recuperer_tous(requete, tuple(parametres))
    return [Document.depuis_ligne(l) for l in lignes]


def compter_documents(terme: str = "", cycle: str = "", filiere: str = "",
                       niveau: str = "", annee: str = "", type_document: str = "",
                       enseignant_id: int | None = None,
                       uniquement_valides: bool = True,
                       tag_id: int | None = None) -> int:
    """Nombre total de resultats pour les memes criteres que rechercher_documents, pour la pagination."""
    conditions, parametres = _construire_conditions(
        terme, cycle, filiere, niveau, annee, type_document, enseignant_id, uniquement_valides, tag_id
    )
    clause_where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    ligne = recuperer_un(f"SELECT COUNT(*) AS total FROM subjects {clause_where}", tuple(parametres))
    return ligne["total"] if ligne else 0


def enregistrer_telechargement(document_id: int, user_id: int, adresse_ip: str) -> None:
    executer(
        "INSERT INTO downloads (document_id, user_id, adresse_ip) VALUES (?, ?, ?)",
        (document_id, user_id, adresse_ip),
    )
    journaliser("Telechargement document", "succes", user_id=user_id, details=str(document_id))


def basculer_favori(document_id: int, user_id: int) -> bool:
    """Ajoute ou retire un document des favoris. Retourne le nouvel etat (True = favori)."""
    existe = recuperer_un(
        "SELECT id FROM favorites WHERE user_id = ? AND document_id = ?",
        (user_id, document_id),
    )
    if existe:
        executer("DELETE FROM favorites WHERE id = ?", (existe["id"],))
        return False
    executer("INSERT INTO favorites (user_id, document_id) VALUES (?, ?)", (user_id, document_id))
    return True


def favoris_utilisateur(user_id: int) -> list[Document]:
    lignes = recuperer_tous(
        """
        SELECT s.* FROM subjects s
        JOIN favorites f ON f.document_id = s.id
        WHERE f.user_id = ? AND s.supprime = 0
        ORDER BY f.date_ajout DESC
        """,
        (user_id,),
    )
    return [Document.depuis_ligne(l) for l in lignes]


def documents_telecharges_par(user_id: int, limite: int = 100) -> list[Document]:
    """
    Documents deja telecharges par un utilisateur (page "Mes
    telechargements", nouveau en V4), les plus recents en premier,
    sans doublon (un meme document telecharge plusieurs fois n'apparait
    qu'une fois, a la date de son telechargement le plus recent). Sur
    le meme principe que favoris_utilisateur et
    documents_recemment_consultes : exclut les documents passes en
    corbeille.
    """
    lignes = recuperer_tous(
        """
        SELECT s.*, MAX(d.date_telechargement) AS dernier_telechargement
        FROM subjects s
        JOIN downloads d ON d.document_id = s.id
        WHERE d.user_id = ? AND s.supprime = 0
        GROUP BY s.id
        ORDER BY dernier_telechargement DESC
        LIMIT ?
        """,
        (user_id, limite),
    )
    return [Document.depuis_ligne(l) for l in lignes]


# =====================================================================
# Tags (nouveau en V3, deuxieme vague)
# =====================================================================

def creer_tag(nom: str, couleur: str = "#2563EB") -> tuple[bool, str]:
    nom = (nom or "").strip()
    if not nom:
        return False, "Le nom du tag est obligatoire."
    if recuperer_un("SELECT id FROM tags WHERE nom = ?", (nom,)):
        return False, "Ce tag existe deja."
    executer("INSERT INTO tags (nom, couleur) VALUES (?, ?)", (nom, couleur))
    return True, "Tag cree."


def supprimer_tag(tag_id: int) -> None:
    executer("DELETE FROM tags WHERE id = ?", (tag_id,))


def tags_disponibles() -> list[dict]:
    return [dict(l) for l in recuperer_tous("SELECT * FROM tags ORDER BY nom")]


def tags_document(document_id: int) -> list[dict]:
    lignes = recuperer_tous(
        """
        SELECT t.* FROM tags t
        JOIN document_tags dt ON dt.tag_id = t.id
        WHERE dt.document_id = ?
        ORDER BY t.nom
        """,
        (document_id,),
    )
    return [dict(l) for l in lignes]


def associer_tags_document(document_id: int, tag_ids: list[int]) -> None:
    """
    Remplace l'ensemble des tags d'un document par la liste fournie
    (supprime toute association existante puis recree celles
    demandees) : semantique simple et previsible pour un widget de
    selection multiple cote administration.
    """
    executer("DELETE FROM document_tags WHERE document_id = ?", (document_id,))
    for tag_id in tag_ids:
        executer(
            "INSERT OR IGNORE INTO document_tags (document_id, tag_id) VALUES (?, ?)",
            (document_id, tag_id),
        )


# =====================================================================
# Import massif de PDF (nouveau en V3, deuxieme vague)
# =====================================================================

def importer_documents_en_masse(fichiers_televerses: list, metadonnees_communes: dict,
                                  ajoute_par: int, taille_max_pdf_mo: int = 25) -> list[tuple[str, bool, str]]:
    """
    Depose plusieurs fichiers PDF en une seule operation, en
    reutilisant entierement ajouter_document pour chacun (aucune regle
    de validation dupliquee : meme controle de signature PDF, meme
    limite de taille, meme circuit de validation ensuite).

    metadonnees_communes doit fournir les champs partages par tous les
    fichiers de l'import (type_document, cycle, filiere, niveau,
    annee_academique, enseignant_id, type_acces, prix) : seul le titre
    differe d'un fichier a l'autre, derive automatiquement du nom du
    fichier (sans son extension).

    Retourne la liste (nom_fichier, succes, message) pour chaque
    fichier, dans l'ordre fourni, afin que l'appelant puisse afficher
    un compte-rendu detaille plutot qu'un seul message global.
    """
    resultats: list[tuple[str, bool, str]] = []
    for fichier in fichiers_televerses:
        titre_derive = fichier.name.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").strip() or fichier.name
        succes, message = ajouter_document(
            titre=titre_derive,
            description=metadonnees_communes.get("description", ""),
            type_document=metadonnees_communes["type_document"],
            cycle=metadonnees_communes["cycle"],
            filiere=metadonnees_communes["filiere"],
            niveau=metadonnees_communes["niveau"],
            annee_academique=metadonnees_communes["annee_academique"],
            enseignant_id=metadonnees_communes.get("enseignant_id"),
            fichier_televerse=fichier,
            ajoute_par=ajoute_par,
            type_acces=metadonnees_communes.get("type_acces", "gratuit"),
            prix=metadonnees_communes.get("prix", 0),
            taille_max_pdf_mo=taille_max_pdf_mo,
        )
        resultats.append((fichier.name, succes, message))
    return resultats


# =====================================================================
# Historique de consultation (nouveau en V4)
#
# Distinct des telechargements (table downloads) : consulter un
# document dans la bibliotheque (ouvrir sa fiche, voir ses details) ne
# signifie pas forcement le telecharger. Alimente la page "Documents
# recemment consultes" (voir app.page_historique).
# =====================================================================

def enregistrer_consultation(document_id: int, user_id: int) -> None:
    """
    Enregistre qu'un utilisateur a consulte ce document a l'instant
    present. A appeler depuis la bibliotheque a l'affichage de la
    fiche d'un document (pas necessairement a chaque rafraichissement
    de page : voir l'appelant pour la frequence exacte retenue).
    """
    executer(
        "INSERT INTO consultations (document_id, user_id) VALUES (?, ?)",
        (document_id, user_id),
    )


def documents_recemment_consultes(user_id: int, limite: int = 30) -> list[Document]:
    """
    Documents recemment consultes par un utilisateur, les plus
    recents en premier, sans doublon (si un document a ete consulte
    plusieurs fois, seule sa consultation la plus recente determine
    son rang dans la liste). Exclut les documents passes en corbeille,
    sur le meme principe que rechercher_documents et favoris_utilisateur.
    """
    lignes = recuperer_tous(
        """
        SELECT s.*, MAX(c.date_consultation) AS derniere_consultation
        FROM subjects s
        JOIN consultations c ON c.document_id = s.id
        WHERE c.user_id = ? AND s.supprime = 0
        GROUP BY s.id
        ORDER BY derniere_consultation DESC
        LIMIT ?
        """,
        (user_id, limite),
    )
    return [Document.depuis_ligne(l) for l in lignes]


def effacer_historique_consultation(user_id: int) -> None:
    """Efface tout l'historique de consultation d'un utilisateur (action volontaire depuis la page Historique)."""
    executer("DELETE FROM consultations WHERE user_id = ?", (user_id,))
