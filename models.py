"""
models.py
---------
Role : definir la structure des donnees manipulees par l'application,
independamment de la base de donnees et de l'interface.

Ces classes ne contiennent aucune logique d'acces aux donnees (ce role
revient a database.py, users.py, archive_manager.py, etc.) et aucune
logique d'affichage (ce role revient a app.py et admin.py). Elles
servent uniquement a representer un enregistrement de maniere typee et
lisible, et a centraliser les regles de validation simples qui leur
sont propres.

Nouveau en V2 : structure des cycles/filieres/niveaux de l'ISABEE,
champs de monetisation des documents, et dataclasses Paiement,
Message, Annonce, Notification.

Nouveau en V3 : champs de corbeille sur Document (supprime,
supprime_le, supprime_par), champs Mobile Money sur Paiement
(operateur, capture_preuve), et nouvelle dataclasse MoyenPaiement
(moyens de paiement Mobile Money configurables).
"""

from dataclasses import dataclass
from datetime import datetime
import re

# ---------------------------------------------------------------------
# Roles et comptes
# ---------------------------------------------------------------------
ROLES_VALIDES = ("administrateur", "enseignant", "etudiant", "contributeur")

LIBELLES_ROLE = {
    "administrateur": "Administrateur",
    "enseignant": "Enseignant",
    "etudiant": "Etudiant",
    "contributeur": "Contributeur",
}

THEMES_VALIDES = ("clair", "sombre")
LIBELLES_THEME = {"clair": "Theme clair", "sombre": "Theme sombre"}

LANGUES_VALIDES = ("fr", "en")
LIBELLES_LANGUE = {"fr": "Francais", "en": "English"}

# ---------------------------------------------------------------------
# Cycles, niveaux et filieres officielles de l'ISABEE
#
# Les 16 filieres ci-dessous sont communes aux deux cursus de premier
# acces : Licence en Sciences de l'Ingenieur et cycle d'Ingenieur.
# Le cycle Master (Master I / Master II) ne suit pas ce decoupage par
# filiere : aucune liste officielle de mentions de Master n'a ete
# fournie a ce jour. En attendant, le champ filiere reste en saisie
# libre pour ce cycle uniquement (voir filieres_disponibles_pour_cycle).
# ---------------------------------------------------------------------
CYCLES_VALIDES = ("Licence", "Ingenieur", "Master")

NIVEAUX_PAR_CYCLE = {
    "Licence": ("Niveau 1", "Niveau 2", "Niveau 3"),
    "Ingenieur": ("Ing 1", "Ing 2", "Ing 3", "Ing 4", "Ing 5"),
    "Master": ("Master I", "Master II"),
}

FILIERES_ISABEE = (
    "Production vegetale",
    "Production animale",
    "Protection des cultures",
    "Operations forestieres",
    "Amenagement forestier",
    "Gestion de la faune, des aires protegees et ecotourisme",
    "Sylviculture et plantations forestieres",
    "Sciences du bois",
    "Techniques specialisees en transformation du bois",
    "Genie de l'environnement",
    "Systemes agro-sylvo-pastoraux et bioenergies",
    "Bioenergies et environnement",
    "Genie energetique",
    "Agroeconomie",
    "Politique et gouvernance forestiere",
    "Etudes d'impact environnemental et social",
)

# Cycles pour lesquels la liste FILIERES_ISABEE s'applique strictement.
CYCLES_AVEC_FILIERES_FIXES = ("Licence", "Ingenieur")


def filieres_disponibles_pour_cycle(cycle: str) -> tuple[str, ...]:
    """
    Retourne la liste des filieres valides pour un cycle donne.
    Pour Licence et Ingenieur : les 16 filieres officielles de l'ISABEE.
    Pour Master : tuple vide (saisie libre tant qu'aucune liste
    officielle de mentions n'a ete communiquee).
    """
    if cycle in CYCLES_AVEC_FILIERES_FIXES:
        return FILIERES_ISABEE
    return ()


def niveaux_disponibles_pour_cycle(cycle: str) -> tuple[str, ...]:
    return NIVEAUX_PAR_CYCLE.get(cycle, ())


# ---------------------------------------------------------------------
# Documents pedagogiques
# ---------------------------------------------------------------------
TYPES_DOCUMENT = ("examen", "controle_continu", "corrige", "travaux_pratiques", "support_cours", "autre")
STATUTS_DOCUMENT = ("en_attente", "valide", "rejete")

LIBELLES_TYPE_DOCUMENT = {
    "examen": "Examen",
    "controle_continu": "Controle continu",
    "corrige": "Corrige",
    "travaux_pratiques": "Travaux pratiques",
    "support_cours": "Support de cours",
    "autre": "Autre",
}

# ---------------------------------------------------------------------
# Monetisation
#
# Deux circuits de paiement, tous deux a validation manuelle par un
# administrateur (aucune integration d'API de paiement automatisee) :
# presentiel (encaissement physique), et Mobile Money (Orange Money,
# MTN MoMo) depuis la V3 -- voir payments.py et payment_methods. Le
# prix par defaut (300 FCFA) est une valeur de depart modifiable par
# document ; il n'est pas code en dur dans la logique metier afin de
# permettre une evolution tarifaire future sans modification du code.
# ---------------------------------------------------------------------
TYPES_ACCES = ("gratuit", "payant")
LIBELLES_TYPE_ACCES = {"gratuit": "Gratuit", "payant": "Payant"}

PRIX_DOCUMENT_PAYANT_DEFAUT = 300
MODES_PAIEMENT_VALIDES = ("presentiel",)
LIBELLE_MODE_PAIEMENT = {"presentiel": "Paiement en presentiel"}

OPERATEURS_PAIEMENT_VALIDES = ("orange_money", "mtn_momo", "autre")
LIBELLES_OPERATEUR = {
    "orange_money": "Orange Money",
    "mtn_momo": "MTN MoMo",
    "autre": "Autre",
}

STATUTS_PAIEMENT = ("en_attente", "valide", "refuse")
LIBELLES_STATUT_PAIEMENT = {
    "en_attente": "En attente de validation",
    "valide": "Paiement valide",
    "refuse": "Paiement refuse",
}

MESSAGE_DOCUMENT_PAYANT = (
    "Document disponible apres paiement en presentiel ou par Mobile Money. "
    "Reglez {prix} FCFA, puis attendez la validation de votre paiement par "
    "un administrateur."
)

# ---------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------
TYPES_NOTIFICATION = ("info", "validation", "paiement", "annonce", "message", "systeme")
LIBELLES_TYPE_NOTIFICATION = {
    "info": "Information",
    "validation": "Validation de document",
    "paiement": "Paiement",
    "annonce": "Annonce",
    "message": "Message",
    "systeme": "Systeme",
}


@dataclass
class Utilisateur:
    id: int | None
    matricule: str
    nom: str
    prenom: str
    email: str
    filiere: str
    niveau: str
    role: str
    statut: str = "actif"
    photo: str | None = None
    theme: str = "clair"
    langue: str = "fr"
    date_inscription: str | None = None
    derniere_connexion: str | None = None
    bio: str | None = None

    @property
    def nom_complet(self) -> str:
        return f"{self.prenom} {self.nom}"

    @staticmethod
    def email_valide(email: str) -> bool:
        return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))

    @classmethod
    def depuis_ligne(cls, ligne) -> "Utilisateur":
        """Construit un Utilisateur a partir d'une ligne sqlite3.Row."""
        cles = ligne.keys()
        return cls(
            id=ligne["id"],
            matricule=ligne["matricule"],
            nom=ligne["nom"],
            prenom=ligne["prenom"],
            email=ligne["email"],
            filiere=ligne["filiere"],
            niveau=ligne["niveau"],
            role=ligne["role"],
            statut=ligne["statut"],
            photo=ligne["photo"] if "photo" in cles else None,
            theme=ligne["theme"] if "theme" in cles else "clair",
            langue=ligne["langue"] if "langue" in cles else "fr",
            date_inscription=ligne["date_inscription"],
            derniere_connexion=ligne["derniere_connexion"],
            bio=ligne["bio"] if "bio" in cles else None,
        )


@dataclass
class Document:
    id: int | None
    titre: str
    description: str
    type_document: str
    cycle: str
    filiere: str
    niveau: str
    annee_academique: str
    enseignant_id: int | None
    chemin_fichier: str
    taille_fichier_ko: int | None
    type_acces: str = "gratuit"
    prix: int = 0
    mode_paiement: str = "presentiel"
    statut: str = "en_attente"
    ajoute_par: int | None = None
    valide_par: int | None = None
    date_ajout: str | None = None
    date_validation: str | None = None
    motif_rejet: str | None = None
    supprime: bool = False
    supprime_le: str | None = None
    supprime_par: int | None = None
    image_couverture: str | None = None

    @property
    def libelle_type(self) -> str:
        return LIBELLES_TYPE_DOCUMENT.get(self.type_document, self.type_document)

    @property
    def est_payant(self) -> bool:
        return self.type_acces == "payant"

    @classmethod
    def depuis_ligne(cls, ligne) -> "Document":
        cles = ligne.keys()
        return cls(
            id=ligne["id"],
            titre=ligne["titre"],
            description=ligne["description"],
            type_document=ligne["type_document"],
            cycle=ligne["cycle"],
            filiere=ligne["filiere"],
            niveau=ligne["niveau"],
            annee_academique=ligne["annee_academique"],
            enseignant_id=ligne["enseignant_id"],
            chemin_fichier=ligne["chemin_fichier"],
            taille_fichier_ko=ligne["taille_fichier_ko"],
            type_acces=ligne["type_acces"] if "type_acces" in cles else "gratuit",
            prix=ligne["prix"] if "prix" in cles else 0,
            mode_paiement=ligne["mode_paiement"] if "mode_paiement" in cles else "presentiel",
            statut=ligne["statut"],
            ajoute_par=ligne["ajoute_par"],
            valide_par=ligne["valide_par"],
            date_ajout=ligne["date_ajout"],
            date_validation=ligne["date_validation"],
            motif_rejet=ligne["motif_rejet"],
            supprime=bool(ligne["supprime"]) if "supprime" in cles else False,
            supprime_le=ligne["supprime_le"] if "supprime_le" in cles else None,
            supprime_par=ligne["supprime_par"] if "supprime_par" in cles else None,
            image_couverture=ligne["image_couverture"] if "image_couverture" in cles else None,
        )


@dataclass
class Paiement:
    id: int | None
    document_id: int
    user_id: int
    montant: int
    mode_paiement: str
    statut_paiement: str
    reference_caisse: str | None
    date_demande: str | None
    date_validation: str | None
    valide_par: int | None
    operateur: str | None = None
    capture_preuve: str | None = None

    @property
    def libelle_statut(self) -> str:
        return LIBELLES_STATUT_PAIEMENT.get(self.statut_paiement, self.statut_paiement)

    @property
    def libelle_canal(self) -> str:
        """Canal de paiement utilise, pour l'affichage (presentiel ou Mobile Money)."""
        if self.operateur:
            return LIBELLES_OPERATEUR.get(self.operateur, self.operateur)
        return LIBELLE_MODE_PAIEMENT.get(self.mode_paiement, self.mode_paiement)

    @classmethod
    def depuis_ligne(cls, ligne) -> "Paiement":
        cles = ligne.keys()
        return cls(
            id=ligne["id"],
            document_id=ligne["document_id"],
            user_id=ligne["user_id"],
            montant=ligne["montant"],
            mode_paiement=ligne["mode_paiement"],
            statut_paiement=ligne["statut_paiement"],
            reference_caisse=ligne["reference_caisse"],
            date_demande=ligne["date_demande"],
            date_validation=ligne["date_validation"],
            valide_par=ligne["valide_par"],
            operateur=ligne["operateur"] if "operateur" in cles else None,
            capture_preuve=ligne["capture_preuve"] if "capture_preuve" in cles else None,
        )


@dataclass
class MoyenPaiement:
    """
    Moyen de paiement Mobile Money configurable depuis l'interface
    d'administration (voir payments.py et admin.page_gestion_moyens_paiement).
    Jamais code en dur : nom_affiche, titulaire et numero sont
    entierement modifiables sans toucher au code.
    """
    id: int | None
    nom_affiche: str
    operateur: str
    titulaire: str
    numero: str
    actif: bool = True
    ordre_affichage: int = 0
    modifie_par: int | None = None
    date_modification: str | None = None

    @property
    def libelle_operateur(self) -> str:
        return LIBELLES_OPERATEUR.get(self.operateur, self.operateur)

    @classmethod
    def depuis_ligne(cls, ligne) -> "MoyenPaiement":
        return cls(
            id=ligne["id"],
            nom_affiche=ligne["nom_affiche"],
            operateur=ligne["operateur"],
            titulaire=ligne["titulaire"],
            numero=ligne["numero"],
            actif=bool(ligne["actif"]),
            ordre_affichage=ligne["ordre_affichage"],
            modifie_par=ligne["modifie_par"],
            date_modification=ligne["date_modification"],
        )


@dataclass
class Message:
    id: int | None
    expediteur_id: int
    destinataire_id: int
    contenu: str
    lu: bool
    date_envoi: str | None

    @classmethod
    def depuis_ligne(cls, ligne) -> "Message":
        return cls(
            id=ligne["id"],
            expediteur_id=ligne["expediteur_id"],
            destinataire_id=ligne["destinataire_id"],
            contenu=ligne["contenu"],
            lu=bool(ligne["lu"]),
            date_envoi=ligne["date_envoi"],
        )


@dataclass
class Annonce:
    id: int | None
    titre: str
    contenu: str
    role_cible: str | None
    publie_par: int
    date_publication: str | None
    date_expiration: str | None

    @property
    def est_publique(self) -> bool:
        return self.role_cible is None

    @classmethod
    def depuis_ligne(cls, ligne) -> "Annonce":
        return cls(
            id=ligne["id"],
            titre=ligne["titre"],
            contenu=ligne["contenu"],
            role_cible=ligne["role_cible"],
            publie_par=ligne["publie_par"],
            date_publication=ligne["date_publication"],
            date_expiration=ligne["date_expiration"],
        )


@dataclass
class Notification:
    id: int | None
    user_id: int
    contenu: str
    type_notification: str
    lu: bool
    document_id: int | None
    date_creation: str | None

    @property
    def libelle_type(self) -> str:
        return LIBELLES_TYPE_NOTIFICATION.get(self.type_notification, self.type_notification)

    @classmethod
    def depuis_ligne(cls, ligne) -> "Notification":
        return cls(
            id=ligne["id"],
            user_id=ligne["user_id"],
            contenu=ligne["contenu"],
            type_notification=ligne["type_notification"],
            lu=bool(ligne["lu"]),
            document_id=ligne["document_id"],
            date_creation=ligne["date_creation"],
        )


@dataclass
class Commentaire:
    id: int | None
    document_id: int
    user_id: int
    contenu: str
    statut: str
    date_creation: str | None

    @classmethod
    def depuis_ligne(cls, ligne) -> "Commentaire":
        return cls(
            id=ligne["id"],
            document_id=ligne["document_id"],
            user_id=ligne["user_id"],
            contenu=ligne["contenu"],
            statut=ligne["statut"],
            date_creation=ligne["date_creation"],
        )


@dataclass
class EntreeJournal:
    id: int | None
    date_heure: str
    user_id: int | None
    matricule: str | None
    action: str
    adresse_ip: str | None
    resultat: str
    details: str | None = None


@dataclass
class Consultation:
    """
    Une ligne d'historique : un utilisateur a consulte (ouvert la fiche
    de) un document a un instant donne. Distinct d'un telechargement
    (table downloads / Document.telecharger) : consulter un document
    dans la bibliotheque ne signifie pas forcement le telecharger.
    Voir archive_manager.enregistrer_consultation et
    archive_manager.documents_recemment_consultes.
    """
    id: int | None
    document_id: int
    user_id: int
    date_consultation: str | None

    @classmethod
    def depuis_ligne(cls, ligne) -> "Consultation":
        return cls(
            id=ligne["id"],
            document_id=ligne["document_id"],
            user_id=ligne["user_id"],
            date_consultation=ligne["date_consultation"],
        )


# ---------------------------------------------------------------------
# Informations institutionnelles (pages "A propos" et "Contact")
#
# Centralisees ici plutot que codees en dur dans app.py, afin qu'une
# future evolution (changement de developpeur, de coordonnees...) ne
# necessite la modification que d'un seul endroit.
# ---------------------------------------------------------------------
INFOS_DEVELOPPEUR = {
    "nom": "Bertrand CHEMTA Caleb",
    "whatsapp": "696075660",
    "telephones": ("696075660", "654046792"),
    "email": "bertrandchemtacaleb@gmail.com",
    "facebook": "Bertrand CHEMTA Caleb",
}

VERSION_APPLICATION = "3.0"


# =====================================================================
# FAQ / base de connaissance de navigation (nouveau en V4)
#
# Centralisee ici afin d'etre partagee par deux consommateurs sans
# aucune duplication : pages_institutionnelles.page_centre_aide
# (affichage complet avec recherche libre) et assistant.repondre (le
# robot d'orientation, qui s'appuie sur les memes mots-cles pour
# trouver la reponse la plus pertinente -- voir assistant.py).
#
# Chaque entree est un tuple (question, reponse, mots_cles). Les
# mots-cles sont volontairement plus larges que les mots de la
# question elle-meme (synonymes, formulations alternatives), afin que
# le robot reconnaisse une question posee differemment de l'intitule
# exact de la FAQ.
# =====================================================================

FAQ_NAVIGATION = (
    (
        "Comment creer un compte ?",
        "Depuis la page de connexion, ouvrez l'onglet \"Creer un compte\". Choisissez "
        "votre cycle, votre filiere et votre niveau, puis remplissez le formulaire. "
        "Votre compte est actif immediatement avec le role Etudiant.",
        ("compte", "inscription", "inscrire", "creer", "creation"),
    ),
    (
        "Comment publier un document ?",
        "Si vous etes enseignant, contributeur ou administrateur, utilisez \"Deposer "
        "un document\" dans le menu lateral. Remplissez les metadonnees (titre, cycle, "
        "filiere, niveau, type), joignez votre fichier PDF, puis soumettez : le "
        "document sera visible des etudiants apres validation.",
        ("publier", "publication", "deposer", "depot", "ajouter document", "soumettre"),
    ),
    (
        "Comment telecharger un document ?",
        "Depuis la Bibliotheque, utilisez les filtres pour retrouver le document "
        "recherche, puis cliquez sur \"Telecharger\". Si le document est payant, vous "
        "devrez d'abord regler son acces (presentiel ou Mobile Money) et attendre la "
        "validation du paiement.",
        ("telecharger", "telechargement", "download"),
    ),
    (
        "Ou trouver les documents que j'ai deja telecharges ?",
        "Rendez-vous dans \"Mes telechargements\", dans le menu lateral (section "
        "Espace) : vous y retrouvez tous les documents deja telecharges, les plus "
        "recents en premier.",
        ("mes telechargements", "deja telecharge", "historique telechargement"),
    ),
    (
        "Ou voir les documents que j'ai consultes recemment ?",
        "Rendez-vous dans \"Historique\", dans le menu lateral (section Espace) : vous "
        "y retrouvez les documents recemment consultes dans la Bibliotheque. Un bouton "
        "permet d'effacer cet historique a tout moment.",
        ("historique", "consulte recemment", "recemment consulte"),
    ),
    (
        "Comment modifier mon profil ?",
        "Rendez-vous dans \"Parametres\" puis l'onglet \"Profil\" : vous pouvez y "
        "changer votre photo, votre biographie, votre nom, prenom et e-mail. Le "
        "matricule, la filiere, le niveau et le role restent geres par l'administration.",
        ("profil", "modifier profil", "photo de profil", "changer photo"),
    ),
    (
        "Comment recuperer mon mot de passe oublie ?",
        "Sur la page de connexion, ouvrez l'onglet \"Mot de passe oublie\", saisissez "
        "votre adresse e-mail, puis suivez les instructions pour generer et utiliser un "
        "jeton de reinitialisation.",
        ("mot de passe oublie", "mot de passe perdu", "reinitialiser mot de passe"),
    ),
    (
        "Comment contacter l'administration ?",
        "Utilisez la page \"Contact\" (formulaire, WhatsApp, telephone, e-mail), "
        "accessible depuis le menu lateral (section Aide), ou envoyez un message "
        "direct depuis la Messagerie a un compte administrateur.",
        ("contacter", "contact", "administration", "administrateur", "joindre"),
    ),
    (
        "Ou consulter mes notifications ?",
        "Cliquez sur \"Notifications\" dans le menu lateral (section Espace). Un badge "
        "rouge numerote apparait a cote du bouton tant que vous avez des notifications "
        "non lues.",
        ("notification", "notifications", "badge"),
    ),
    (
        "Ou consulter mes messages ?",
        "Cliquez sur \"Messagerie\" dans le menu lateral (section Espace). Un badge "
        "rouge numerote apparait a cote du bouton tant que vous avez des messages non "
        "lus.",
        ("message", "messagerie", "messages non lus"),
    ),
    (
        "Comment activer le mode sombre ?",
        "Dans \"Parametres\" > \"Preferences\", choisissez \"Theme sombre\" : le "
        "changement s'applique immediatement, sans bouton a cliquer, et votre choix "
        "est memorise pour vos prochaines connexions.",
        ("mode sombre", "theme sombre", "dark mode", "theme", "obscurite"),
    ),
    (
        "Comment ajouter un document a mes favoris ?",
        "Depuis la Bibliotheque, cliquez sur le bouton \"Favori\" sur la fiche du "
        "document souhaite. Retrouvez ensuite tous vos favoris dans \"Mes favoris\", "
        "dans le menu lateral.",
        ("favori", "favoris", "enregistrer document"),
    ),
    (
        "Comment payer un document payant ?",
        "Depuis la Bibliotheque, sur un document payant, utilisez \"Demander le "
        "paiement\" pour un reglement en presentiel, ou \"Payer par Mobile Money\" si "
        "des moyens de paiement Mobile Money sont actifs. Suivez ensuite l'avancement "
        "dans \"Mes paiements\".",
        ("payer", "paiement", "mobile money", "document payant", "prix"),
    ),
    (
        "Pourquoi mon document n'apparait-il pas dans la bibliotheque ?",
        "Tout document depose doit d'abord etre valide par un enseignant, un "
        "contributeur habilite ou un administrateur (voir \"Gestion des "
        "validations\"). Vous recevez une notification une fois la decision prise.",
        ("document n'apparait pas", "document pas visible", "en attente", "validation"),
    ),
)
