""" app.py ------ Role : point d'entree unique de l'application Streamlit. Responsabilites : - configuration de la page et chargement de la feuille de style (claire, et sombre en complement selon la preference utilisateur) ; - initialisation de la base de donnees au premier lancement ; - creation guidee du premier compte administrateur si la base est vide ; - affichage de l'ecran de connexion (logo et titre institutionnel centres, formulaire de connexion inchange) ; - verification de l'expiration de session a chaque chargement de page ; - routage vers les pages selon le role de l'utilisateur connecte ; - pages communes : bibliotheque, depot de document, favoris, mes paiements, messagerie, annonces, notifications, parametres personnels. Les pages reservees a l'administration sont deleguees a admin.py. Nouveau en V2 (voir audit et cahier des charges) : - sidebar compacte avec logo, dans l'esprit des tableaux de bord administratifs modernes ; - renommage "Bibliotheque numerique" -> "Bibliotheque" ; - circuit complet de monetisation (acces gratuit/payant, demande et suivi de paiement en presentiel) ; - espace communautaire (messagerie, annonces, notifications, commentaires) ; - page Parametres personnelle (profil, photo, preferences, securite, deconnexion), distincte de la Configuration systeme reservee a l'administration ; - garde de session (auth.verifier_session_active), absente en V1. Nouveau en V3 (voir audit-isabee-v2.md) : - page de connexion enrichie d'onglets Inscription et Mot de passe oublie, en complement (jamais en remplacement) de la connexion par matricule ; - connexion Google et Microsoft (authentification OIDC native de Streamlit, voir auth.py et secrets.toml.example), elle aussi en complement de la connexion par matricule -- invisible et sans aucun effet si elle n'est pas configuree ; - paiement Mobile Money (Orange Money, MTN MoMo) propose en option a cote du paiement en presentiel, jamais a sa place ; - entrees Corbeille et Moyens de paiement dans le menu d'administration. """

import streamlit as st
import extra_streamlit_components as stx
from pathlib import Path

from database import initialiser_base, recuperer_un
import settings as parametres_systeme
import archive_manager
import payments
import communication
import users as gestion_utilisateurs
import admin
import auth
import icons
import assistant
import pages_institutionnelles
from models import (
    LIBELLES_ROLE, LIBELLES_TYPE_DOCUMENT, TYPES_DOCUMENT,
    CYCLES_VALIDES, filieres_disponibles_pour_cycle, niveaux_disponibles_pour_cycle,
    TYPES_ACCES, LIBELLES_TYPE_ACCES, PRIX_DOCUMENT_PAYANT_DEFAUT, MESSAGE_DOCUMENT_PAYANT,
    THEMES_VALIDES, LIBELLES_THEME, LANGUES_VALIDES, LIBELLES_LANGUE,
)
from utils import (
    charger_css, icone, formater_date, adresse_ip_client,
    fichier_est_photo_valide, enregistrer_photo,
    fichier_est_couverture_valide, enregistrer_image_couverture,
)

# Chemin absolu, base sur l'emplacement reel de ce fichier (app.py),
# et non sur le dossier de lancement du processus : un chemin relatif
# simple ("assets/logo.png") ne fonctionne que si "streamlit run" est
# execute depuis l'interieur du dossier du projet, ce qui depend de la
# methode de deploiement choisie. Avec st.image, qui accepte un objet
# Path directement, cette resolution absolue elimine ce risque
# d'echec silencieux (le logo restait invisible sans aucune erreur
# visible, uniquement attrape par les try/except defensifs ci-dessous).
CHEMIN_LOGO = Path(__file__).resolve().parent / "assets" / "logo.png"

st.set_page_config(
    page_title="SOURCE ISABEE",
    # Favicon : utilise le logo institutionnel s'il est present sur le
    # disque (voir CHEMIN_LOGO ci-dessus, remplacable par
    # l'administration sans toucher au code), avec repli automatique
    # sur l'icone Material par defaut si le fichier est absent --
    # set_page_config echoue sinon au tout premier chargement du
    # module, avant qu'aucun try/except applicatif ne puisse intervenir.
    page_icon=str(CHEMIN_LOGO) if CHEMIN_LOGO.is_file() else ":material/school:",
    layout="wide",
)

NOM_COOKIE_SESSION = "isabee_session"


def _gestionnaire_cookies() -> stx.CookieManager:
    """ Instance unique (memorisee dans st.session_state, propre a chaque session de navigateur) du gestionnaire de cookies, pour la connexion persistante ("se souvenir de moi", voir auth.generer_jeton_session). Important : NE PAS utiliser @st.cache_resource ici. CookieManager cree un widget interne (composant Streamlit cote navigateur), et Streamlit interdit explicitement tout widget a l'interieur d'une fonction mise en cache (CachedWidgetWarning, qui devient une veritable erreur bloquante dans les versions recentes) : le widget ne s'executerait qu'au premier appel ("cache miss"), ce qui romprait la synchronisation des cookies a chaque rafraichissement suivant. st.session_state est le mecanisme correct pour conserver une instance unique par session sans declencher cette restriction. """
    if "gestionnaire_cookies" not in st.session_state:
        st.session_state["gestionnaire_cookies"] = stx.CookieManager()
    return st.session_state["gestionnaire_cookies"]


def _initialiser_application() -> None:
    initialiser_base()
    parametres_systeme.initialiser_parametres_par_defaut()
    try:
        charger_css("assets/style.css")
    except FileNotFoundError:
        pass


def _aucun_compte_existant() -> bool:
    return recuperer_un("SELECT id FROM users LIMIT 1") is None


def _afficher_en_tete_publique() -> None:
    """ En-tete affichee uniquement sur les ecrans pre-authentification (configuration initiale et connexion) : logo, titre institutionnel et message d'accueil animes, tous centres. N'affecte aucun autre element de la page de connexion (le formulaire reste celui defini par page_connexion). Nouveau en V4 : une photo ronde (CHEMIN_LOGO, reutilise comme visuel d'accueil tant qu'aucun autre visuel dedie n'est fourni) est placee en haut a droite du titre principal, et le texte d'accueil apparait avec une legere animation de fondu (CSS, voir assets/style.css : .message-accueil). """
    _, colonne_centre, _ = st.columns([1, 2, 1])
    with colonne_centre:
        colonne_titre, colonne_photo_ronde = st.columns([5, 1])
        with colonne_titre:
            try:
                st.image(CHEMIN_LOGO, width=96)
            except Exception:
                pass
        with colonne_photo_ronde:
            try:
                st.markdown(
                    f'<div class="photo-ronde-connexion">'
                    f'<img src="data:image/png;base64,{_logo_base64()}" alt="" /></div>',
                    unsafe_allow_html=True,
                )
            except Exception:
                pass
        st.markdown(
            """ <div class="en-tete-connexion"> <h1>SOURCE ISABEE</h1> <p>Plateforme de gestion des ressources pédagogiques</p> </div> <div class="message-accueil"> Bienvenue sur votre espace numérique ISABEE — retrouvez vos documents, échangez avec votre communauté académique et suivez vos ressources pédagogiques en toute confiance. </div> """,
            unsafe_allow_html=True,
        )


@st.cache_data
def _logo_base64() -> str:
    """ Encode le logo institutionnel en base64 pour l'inserer directement dans un bloc HTML personnalise (photo ronde de la page de connexion), ce que st.image seul ne permet pas de positionner librement. Mis en cache (le fichier ne change pas en cours d'execution) afin de ne relire le disque qu'une seule fois. """
    import base64
    with open(CHEMIN_LOGO, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _afficher_barre_superieure() -> None:
    """Barre superieure discrete, affichee une fois connecte : logo en haut a gauche."""
    colonne_logo, colonne_titre = st.columns([1, 8])
    with colonne_logo:
        try:
            st.image(CHEMIN_LOGO, width=40)
        except Exception:
            pass
    with colonne_titre:
        st.markdown('<div class="barre-superieure-titre">SOURCE ISABEE</div>', unsafe_allow_html=True)
    st.divider()


def page_initialisation() -> None:
    """Affichee une seule fois : creation du premier compte administrateur."""
    st.subheader("Configuration initiale")
    st.write(
        "Aucun compte n'existe encore sur cette installation. "
        "Creez le premier compte administrateur pour commencer."
    )
    with st.form("formulaire_initialisation"):
        colonne_gauche, colonne_droite = st.columns(2)
        with colonne_gauche:
            matricule = st.text_input("Matricule")
            nom = st.text_input("Nom")
            email = st.text_input("Adresse e-mail")
        with colonne_droite:
            prenom = st.text_input("Prenom")
            mot_de_passe = st.text_input("Mot de passe", type="password")
            confirmation = st.text_input("Confirmer le mot de passe", type="password")

        valide = st.form_submit_button("Creer le compte administrateur")
        if valide:
            if mot_de_passe != confirmation:
                st.error("Les mots de passe ne correspondent pas.")
            elif not all([matricule, nom, prenom, email, mot_de_passe]):
                st.error("Tous les champs sont obligatoires.")
            else:
                succes, message = gestion_utilisateurs.creer_utilisateur(
                    matricule=matricule, nom=nom, prenom=prenom, email=email,
                    filiere="-", niveau="-", role="administrateur",
                    mot_de_passe=mot_de_passe,
                )
                if succes:
                    st.success("Compte administrateur cree. Vous pouvez vous connecter.")
                else:
                    st.error(message)


def page_connexion() -> None:
    onglet_connexion, onglet_inscription, onglet_oubli = st.tabs(
        ["Connexion", "Creer un compte", "Mot de passe oublie"]
    )

    with onglet_connexion:
        with st.form("formulaire_connexion"):
            matricule = st.text_input("Matricule")
            mot_de_passe = st.text_input("Mot de passe", type="password")
            se_souvenir = st.checkbox("Se souvenir de moi (rester connecte 30 jours)")
            valide = st.form_submit_button("Se connecter")
            if valide:
                succes, message = auth.authentifier(matricule.strip(), mot_de_passe)
                if succes:
                    utilisateur_connecte = auth.utilisateur_courant()
                    jeton = auth.generer_jeton_session(utilisateur_connecte.id, se_souvenir=se_souvenir)
                    duree_max_age = (
                        auth.DUREE_COOKIE_SOUVENIR_JOURS * 24 * 3600 if se_souvenir
                        else auth.DUREE_COOKIE_SESSION_HEURES * 3600
                    )
                    _gestionnaire_cookies().set(NOM_COOKIE_SESSION, jeton, max_age=duree_max_age)
                    st.rerun()
                else:
                    st.error(message)

        fournisseurs = auth.fournisseurs_oidc_configures()
        if fournisseurs:
            st.divider()
            st.caption("Ou connectez-vous avec :")
            libelles_oidc = {"google": "Se connecter avec Google", "microsoft": "Se connecter avec Microsoft"}
            colonnes_oidc = st.columns(len(fournisseurs))
            for colonne, fournisseur in zip(colonnes_oidc, sorted(fournisseurs)):
                with colonne:
                    if st.button(libelles_oidc.get(fournisseur, fournisseur), key=f"oidc_{fournisseur}",
                                 use_container_width=True):
                        try:
                            st.login(fournisseur)
                        except Exception as e:
                            st.error(f"Connexion {fournisseur} indisponible pour le moment : {e}")

    with onglet_inscription:
        st.caption(
            "Tout compte cree ici est immediatement actif avec le role Etudiant. "
            "Un administrateur peut ensuite vous attribuer un role superieur si necessaire."
        )
        colonne_cycle, colonne_filiere = st.columns(2)
        with colonne_cycle:
            cycle_inscription = st.selectbox("Cycle", list(CYCLES_VALIDES), key="inscription_cycle")
        with colonne_filiere:
            filieres_possibles = filieres_disponibles_pour_cycle(cycle_inscription)
            if filieres_possibles:
                filiere_inscription = st.selectbox("Filiere", filieres_possibles, key="inscription_filiere")
            else:
                filiere_inscription = st.text_input("Filiere (saisie libre)", key="inscription_filiere_libre")
        niveaux_possibles = niveaux_disponibles_pour_cycle(cycle_inscription)
        niveau_inscription = (
            st.selectbox("Niveau", niveaux_possibles, key="inscription_niveau") if niveaux_possibles else "-"
        )
        st.caption(
            "Le cycle, la filiere et le niveau sont choisis ici, en dehors du formulaire "
            "ci-dessous, afin que la liste des filieres se mette a jour immediatement."
        )

        with st.form("formulaire_inscription", clear_on_submit=True):
            colonne_1, colonne_2 = st.columns(2)
            with colonne_1:
                matricule_inscription = st.text_input("Matricule", key="inscription_matricule")
                nom_inscription = st.text_input("Nom", key="inscription_nom")
            with colonne_2:
                prenom_inscription = st.text_input("Prenom", key="inscription_prenom")
                email_inscription = st.text_input("Adresse e-mail", key="inscription_email")
            mot_de_passe_inscription = st.text_input(
                "Mot de passe", type="password", key="inscription_mdp",
                help="Au moins 8 caracteres, avec au moins une lettre et un chiffre.",
            )
            valide_inscription = st.form_submit_button("Creer mon compte")
            if valide_inscription:
                if not all([matricule_inscription, nom_inscription, prenom_inscription,
                            email_inscription, mot_de_passe_inscription]):
                    st.error("Tous les champs obligatoires doivent etre renseignes.")
                else:
                    succes, message = gestion_utilisateurs.inscription_libre(
                        matricule=matricule_inscription, nom=nom_inscription, prenom=prenom_inscription,
                        email=email_inscription, filiere=filiere_inscription or "-",
                        niveau=niveau_inscription or "-", mot_de_passe=mot_de_passe_inscription,
                    )
                    if succes:
                        st.success(f"{message} Vous pouvez maintenant vous connecter avec votre matricule.")
                    else:
                        st.error(message)

    with onglet_oubli:
        st.caption(
            "Saisissez votre adresse e-mail. Si elle correspond a un compte, un jeton "
            "de reinitialisation est genere ci-dessous."
        )
        email_oubli = st.text_input("Adresse e-mail", key="oubli_email")
        if st.button("Generer le jeton de reinitialisation", key="oubli_demander"):
            succes, message, jeton = auth.demander_reinitialisation_mot_de_passe(email_oubli)
            st.info(message)
            if jeton:
                st.code(jeton, language=None)
                st.caption(
                    f"Copiez ce jeton et saisissez-le ci-dessous (valable "
                    f"{auth.DUREE_VALIDITE_JETON_RESET_MINUTES} minutes). En production, ce "
                    "jeton serait transmis par e-mail plutot qu'affiche directement ici."
                )

        st.divider()
        with st.form("formulaire_reinitialisation", clear_on_submit=True):
            jeton_saisi = st.text_input("Jeton recu")
            nouveau_mdp_oubli = st.text_input(
                "Nouveau mot de passe", type="password",
                help="Au moins 8 caracteres, avec au moins une lettre et un chiffre.",
            )
            valide_reset = st.form_submit_button("Reinitialiser le mot de passe")
            if valide_reset:
                succes, message = auth.reinitialiser_mot_de_passe_par_jeton(jeton_saisi, nouveau_mdp_oubli)
                (st.success if succes else st.error)(message)


# =====================================================================
# Bibliotheque (anciennement "Bibliotheque numerique")
# =====================================================================

def page_bibliotheque() -> None:
    st.subheader("Bibliotheque")
    utilisateur = auth.utilisateur_courant()

    # Message d'accueil anime (nouveau en V4), affiche une seule fois
    # par session (et non a chaque rafraichissement de la bibliotheque,
    # ce qui serait redondant pour l'utilisateur) : voir
    # assets/style.css, classe .message-accueil, pour l'effet de fondu.
    if not st.session_state.get("accueil_bibliotheque_affiche"):
        st.markdown(
            f'<div class="message-accueil">'
            f"Bienvenue, {utilisateur.prenom} — découvrez les dernières ressources "
            f"pédagogiques disponibles pour votre filière.</div>",
            unsafe_allow_html=True,
        )
        st.session_state["accueil_bibliotheque_affiche"] = True

    with st.expander("Filtres de recherche", expanded=True, icon=icone("Search")):
        colonne_1, colonne_2, colonne_3 = st.columns(3)
        with colonne_1:
            cycle = st.selectbox("Cycle", ["Tous"] + list(CYCLES_VALIDES), key="bib_cycle")
        with colonne_2:
            filieres_possibles = filieres_disponibles_pour_cycle(cycle) if cycle != "Tous" else ()
            if filieres_possibles:
                filiere = st.selectbox("Filiere", ["Toutes"] + list(filieres_possibles), key="bib_filiere")
                filiere = "" if filiere == "Toutes" else filiere
            else:
                filiere = st.text_input("Filiere (mot-cle)", key="bib_filiere_libre")
        with colonne_3:
            niveaux_possibles = niveaux_disponibles_pour_cycle(cycle) if cycle != "Tous" else ()
            if niveaux_possibles:
                niveau = st.selectbox("Niveau", ["Tous"] + list(niveaux_possibles), key="bib_niveau")
                niveau = "" if niveau == "Tous" else niveau
            else:
                niveau = ""

        colonne_4, colonne_5 = st.columns(2)
        with colonne_4:
            type_document = st.selectbox(
                "Type", ["Tous"] + list(TYPES_DOCUMENT), key="bib_type",
                format_func=lambda v: "Tous" if v == "Tous" else LIBELLES_TYPE_DOCUMENT.get(v, v),
            )
        with colonne_5:
            annee = st.text_input("Annee academique", placeholder="ex. 2025-2026", key="bib_annee")
        terme = st.text_input("Mots-cles", placeholder="Titre ou description du document", key="bib_terme")

        tags_existants = archive_manager.tags_disponibles()
        tag_choisi = None
        if tags_existants:
            options_tag = ["Tous"] + [t["nom"] for t in tags_existants]
            nom_tag_choisi = st.selectbox("Tag", options_tag, key="bib_tag")
            if nom_tag_choisi != "Tous":
                tag_choisi = next(t["id"] for t in tags_existants if t["nom"] == nom_tag_choisi)

    cycle_filtre = "" if cycle == "Tous" else cycle
    type_document_filtre = "" if type_document == "Tous" else type_document

    page_courante = st.session_state.get("bib_page", 0)
    taille_page = 10
    total = archive_manager.compter_documents(
        terme=terme, cycle=cycle_filtre, filiere=filiere, niveau=niveau,
        annee=annee, type_document=type_document_filtre, tag_id=tag_choisi,
    )
    resultats = archive_manager.rechercher_documents(
        terme=terme, cycle=cycle_filtre, filiere=filiere, niveau=niveau,
        annee=annee, type_document=type_document_filtre, tag_id=tag_choisi,
        limite=taille_page, decalage=page_courante * taille_page,
    )

    st.caption(f"{total} document(s) trouve(s)")

    for document in resultats:
        with st.container(border=True):
            # Enregistre la consultation (nouveau en V4, voir
            # archive_manager.enregistrer_consultation) : la fiche du
            # document vient d'etre affichee dans la bibliotheque.
            # N'affecte aucun autre comportement existant de la carte.
            archive_manager.enregistrer_consultation(document.id, utilisateur.id)

            if document.image_couverture:
                colonne_couverture, colonne_info, colonne_action = st.columns([1, 3, 1])
            else:
                colonne_info, colonne_action = st.columns([4, 1])
                colonne_couverture = None

            if colonne_couverture is not None:
                with colonne_couverture:
                    # Vignette HD avec coins arrondis et ombre legere
                    # (voir assets/style.css, classe .vignette-couverture).
                    # Le clic ouvre l'image en plein ecran via le
                    # zoom natif de st.image (parametre
                    # use_container_width seul ; Streamlit affiche une
                    # icone d'agrandissement au survol qui ouvre la
                    # vue plein ecran sans code supplementaire).
                    st.markdown('<div class="vignette-couverture">', unsafe_allow_html=True)
                    try:
                        st.image(document.image_couverture, use_container_width=True)
                    except Exception:
                        pass
                    st.markdown('</div>', unsafe_allow_html=True)

            with colonne_info:
                st.markdown(f"**{document.titre}**")
                badge_acces = f"Payant - {document.prix} FCFA" if document.est_payant else "Gratuit"
                st.caption(
                    f"{document.libelle_type} - {document.cycle} - {document.filiere} - "
                    f"{document.niveau} - {document.annee_academique} - {badge_acces}"
                )
                tags_du_document = archive_manager.tags_document(document.id)
                if tags_du_document:
                    st.caption("Tags : " + ", ".join(t["nom"] for t in tags_du_document))
                if document.description:
                    st.write(document.description)

                # Apercu visuel des premieres pages du document (nouveau,
                # ajoute apres la mise en production initiale -- voir
                # apercu_documents.py). N'affiche rien si l'apercu n'a
                # pas encore ete genere pour ce document (cas des
                # documents deposes avant l'ajout de cette
                # fonctionnalite, voir admin.page_maintenance pour les
                # generer en une fois) ou si la bibliotheque pymupdf
                # n'est pas disponible : import local, jamais bloquant
                # pour le reste de l'affichage de la bibliotheque.
                try:
                    import apercu_documents
                    apercu_documents.afficher_apercu_document(document)
                except Exception:
                    pass

            with colonne_action:
                acces_autorise = True
                if document.est_payant:
                    statut_paie = payments.statut_paiement_utilisateur(document.id, utilisateur.id)
                    if statut_paie == "valide":
                        acces_autorise = True
                    elif statut_paie == "en_attente":
                        acces_autorise = False
                        st.info("Paiement en attente de validation.")
                    else:
                        acces_autorise = False
                        st.warning(MESSAGE_DOCUMENT_PAYANT.format(prix=document.prix))
                        if st.button("Demander le paiement", key=f"payer_{document.id}"):
                            succes, message = payments.demander_paiement(document.id, utilisateur.id)
                            (st.success if succes else st.error)(message)
                            st.rerun()

                        moyens_actifs = payments.moyens_paiement_actifs()
                        if moyens_actifs:
                            with st.popover("Payer par Mobile Money", icon=icone("Wallet")):
                                moyen_choisi = st.selectbox(
                                    "Moyen de paiement", moyens_actifs,
                                    format_func=lambda m: f"{m.libelle_operateur} - {m.numero} ({m.titulaire})",
                                    key=f"moyen_{document.id}",
                                )
                                st.image(
                                    payments.qrcode_moyen_paiement(moyen_choisi, document.prix), width=160
                                )
                                st.caption(f"Montant a transferer : {document.prix} FCFA")
                                capture_preuve = st.file_uploader(
                                    "Capture de la preuve de paiement", type=["jpg", "jpeg", "png"],
                                    key=f"preuve_{document.id}",
                                )
                                if st.button("Envoyer la preuve", key=f"envoyer_preuve_{document.id}"):
                                    if capture_preuve is None:
                                        st.error("Veuillez joindre une capture de la preuve de paiement.")
                                    else:
                                        succes, message = payments.demander_paiement_mobile_money(
                                            document.id, utilisateur.id, moyen_choisi.operateur, capture_preuve
                                        )
                                        (st.success if succes else st.error)(message)
                                        if succes:
                                            st.rerun()

                if acces_autorise:
                    with open(document.chemin_fichier, "rb") as fichier:
                        if st.download_button(
                            "Telecharger", data=fichier, file_name=f"{document.titre}.pdf",
                            mime="application/pdf", key=f"telecharger_{document.id}",
                            icon=icone("Download"),
                        ):
                            archive_manager.enregistrer_telechargement(
                                document.id, utilisateur.id, adresse_ip_client()
                            )
                if st.button("Favori", key=f"favori_{document.id}"):
                    archive_manager.basculer_favori(document.id, utilisateur.id)
                    st.rerun()

            with st.expander("Commentaires et avis"):
                commentaires = communication.commentaires_document(document.id)
                if not commentaires:
                    st.caption("Aucun commentaire pour le moment.")
                for c in commentaires:
                    colonne_avatar, colonne_texte = st.columns([1, 11])
                    with colonne_avatar:
                        if c.get("photo_auteur"):
                            try:
                                st.image(c["photo_auteur"], width=28)
                            except Exception:
                                pass
                    with colonne_texte:
                        st.markdown(f"**{c['prenom_auteur']} {c['nom_auteur']}** : {c['contenu']}")
                nouveau_commentaire = st.text_area(
                    "Ajouter un commentaire", key=f"commentaire_{document.id}",
                    label_visibility="collapsed", placeholder="Votre commentaire ou avis...",
                )
                if st.button("Publier", key=f"publier_commentaire_{document.id}"):
                    succes, message = communication.ajouter_commentaire(
                        document.id, utilisateur.id, nouveau_commentaire
                    )
                    (st.success if succes else st.error)(message)
                    if succes:
                        st.rerun()

    colonne_prec, colonne_suiv = st.columns(2)
    with colonne_prec:
        if page_courante > 0 and st.button("Page precedente", key="bib_page_prec"):
            st.session_state["bib_page"] = page_courante - 1
            st.rerun()
    with colonne_suiv:
        if (page_courante + 1) * taille_page < total and st.button("Page suivante", key="bib_page_suiv"):
            st.session_state["bib_page"] = page_courante + 1
            st.rerun()


# =====================================================================
# Depot de documents
# =====================================================================

def page_depot_document() -> None:
    st.subheader("Depot de documents")
    utilisateur = auth.utilisateur_courant()

    cycle = st.selectbox("Cycle", list(CYCLES_VALIDES), key="depot_cycle")
    filieres_possibles = filieres_disponibles_pour_cycle(cycle)
    if filieres_possibles:
        filiere = st.selectbox("Filiere", filieres_possibles, key="depot_filiere")
    else:
        filiere = st.text_input(
            "Filiere (saisie libre - aucune liste officielle de mentions de Master n'est encore definie)",
            key="depot_filiere_libre",
        )
    niveaux_possibles = niveaux_disponibles_pour_cycle(cycle)
    niveau = st.selectbox("Niveau", niveaux_possibles, key="depot_niveau") if niveaux_possibles else "-"
    st.caption(
        "Le cycle, la filiere et le niveau sont choisis ici, en dehors du formulaire ci-dessous, "
        "afin que la liste des filieres se mette a jour immediatement selon le cycle selectionne "
        "(un formulaire Streamlit ne se met a jour qu'a la soumission)."
    )

    with st.form("formulaire_depot", clear_on_submit=True):
        titre = st.text_input("Titre du document")
        description = st.text_area("Description", height=80)
        colonne_1, colonne_2 = st.columns(2)
        with colonne_1:
            annee_academique = st.text_input("Annee academique", placeholder="ex. 2025-2026")
        with colonne_2:
            type_document = st.selectbox(
                "Type de document", list(TYPES_DOCUMENT),
                format_func=lambda v: LIBELLES_TYPE_DOCUMENT.get(v, v),
            )

        colonne_acces, colonne_prix = st.columns(2)
        with colonne_acces:
            type_acces = st.radio(
                "Acces", list(TYPES_ACCES), format_func=lambda v: LIBELLES_TYPE_ACCES.get(v, v), horizontal=True
            )
        with colonne_prix:
            prix_defaut = parametres_systeme.obtenir_parametre_entier(
                "prix_document_payant_defaut", PRIX_DOCUMENT_PAYANT_DEFAUT
            )
            prix = st.number_input(
                "Prix (FCFA)", min_value=0, value=prix_defaut, step=50,
                help="Ignore si l'acces est gratuit.",
            )

        fichier = st.file_uploader("Fichier PDF", type=["pdf"])
        image_couverture = st.file_uploader(
            "Image de couverture (optionnelle)", type=["jpg", "jpeg", "png"],
            help=(
                "Visuel affiche dans la bibliotheque en complement du PDF "
                "(ex. page de garde, illustration). Totalement facultatif."
            ),
        )

        valide = st.form_submit_button("Soumettre pour validation")
        if valide:
            if not all([titre, filiere, annee_academique, fichier]):
                st.error("Veuillez renseigner les champs obligatoires et joindre un fichier PDF.")
            else:
                taille_max = parametres_systeme.obtenir_parametre_entier("taille_max_pdf_mo", 25)
                succes, message = archive_manager.ajouter_document(
                    titre=titre, description=description, type_document=type_document,
                    cycle=cycle, filiere=filiere, niveau=niveau,
                    annee_academique=annee_academique,
                    enseignant_id=utilisateur.id if utilisateur.role == "enseignant" else None,
                    fichier_televerse=fichier, ajoute_par=utilisateur.id,
                    type_acces=type_acces, prix=int(prix), taille_max_pdf_mo=taille_max,
                    image_couverture_televersee=image_couverture,
                )
                (st.success if succes else st.error)(message)

    with st.expander("Import massif (plusieurs PDF a la fois)", icon=icone("FileText")):
        st.caption(
            "Le cycle, la filiere, le niveau, le type et l'acces choisis ci-dessus s'appliquent "
            "a tous les fichiers importes. Le titre de chaque document est derive automatiquement "
            "du nom de son fichier ; vous pourrez le corriger ensuite depuis Gestion des documents."
        )
        fichiers_masse = st.file_uploader(
            "Fichiers PDF", type=["pdf"], accept_multiple_files=True, key="depot_masse_fichiers"
        )
        if st.button("Importer ces fichiers", key="depot_masse_valider"):
            if not fichiers_masse:
                st.error("Veuillez joindre au moins un fichier PDF.")
            elif not filiere or not niveau:
                st.error("Veuillez renseigner la filiere et le niveau ci-dessus avant l'import massif.")
            else:
                taille_max = parametres_systeme.obtenir_parametre_entier("taille_max_pdf_mo", 25)
                resultats_masse = archive_manager.importer_documents_en_masse(
                    fichiers_televerses=fichiers_masse,
                    metadonnees_communes={
                        "type_document": type_document, "cycle": cycle, "filiere": filiere,
                        "niveau": niveau, "annee_academique": annee_academique or "-",
                        "enseignant_id": utilisateur.id if utilisateur.role == "enseignant" else None,
                        "type_acces": type_acces, "prix": int(prix),
                    },
                    ajoute_par=utilisateur.id, taille_max_pdf_mo=taille_max,
                )
                nb_succes = sum(1 for _, succes, _ in resultats_masse if succes)
                st.success(f"{nb_succes}/{len(resultats_masse)} document(s) importe(s) avec succes.")
                for nom_fichier, succes, message in resultats_masse:
                    (st.write if succes else st.error)(f"{nom_fichier} : {message}")


# =====================================================================
# Favoris et paiements personnels
# =====================================================================

def page_favoris() -> None:
    st.subheader("Mes favoris")
    utilisateur = auth.utilisateur_courant()
    documents = archive_manager.favoris_utilisateur(utilisateur.id)
    if not documents:
        st.info("Aucun document enregistre dans vos favoris.")
        return
    for document in documents:
        with st.container(border=True):
            _afficher_carte_document_compacte(document)


def page_mes_telechargements() -> None:
    """ Page "Mes telechargements" (nouveau en V4, cahier des charges point 16) : liste des documents deja telecharges par l'utilisateur, les plus recents en premier. Distincte de "Historique" (consultation, pas necessairement suivie d'un telechargement) et de "Mes favoris" (choix volontaire, independant du fait d'avoir telecharge ou non). """
    st.subheader("Mes telechargements")
    utilisateur = auth.utilisateur_courant()
    documents = archive_manager.documents_telecharges_par(utilisateur.id)
    if not documents:
        st.info("Vous n'avez encore telecharge aucun document.")
        return
    for document in documents:
        with st.container(border=True):
            _afficher_carte_document_compacte(document)


def page_historique() -> None:
    """ Page "Documents recemment consultes" (nouveau en V4, cahier des charges point 15). Un bouton permet d'effacer volontairement cet historique (effacer_historique_consultation), sans affecter ni les favoris ni les telechargements de l'utilisateur. """
    st.subheader("Historique")
    utilisateur = auth.utilisateur_courant()
    documents = archive_manager.documents_recemment_consultes(utilisateur.id)

    if documents and st.button("Effacer l'historique", icon=icone("Trash")):
        archive_manager.effacer_historique_consultation(utilisateur.id)
        st.rerun()

    if not documents:
        st.info("Aucun document consulte recemment.")
        return
    for document in documents:
        with st.container(border=True):
            _afficher_carte_document_compacte(document)


def _afficher_carte_document_compacte(document) -> None:
    """ Carte compacte d'un document, reutilisee par Mes favoris, Mes telechargements et Historique : titre, image de couverture si disponible (nouveau en V4 -- voir assets/style.css, classe .vignette-couverture, pour le rendu HD avec coins arrondis et ombre legere), et metadonnees principales. N'affecte pas l'affichage detaille de la fiche d'un document dans la Bibliotheque elle-meme. """
    if document.image_couverture:
        colonne_image, colonne_texte = st.columns([1, 4])
        with colonne_image:
            try:
                st.image(document.image_couverture, width=80)
            except Exception:
                pass
        with colonne_texte:
            _afficher_details_document_compact(document)
    else:
        _afficher_details_document_compact(document)


def _afficher_details_document_compact(document) -> None:
    st.markdown(f"**{document.titre}**")
    badge_acces = f"Payant - {document.prix} FCFA" if document.est_payant else "Gratuit"
    st.caption(f"{document.libelle_type} - {document.filiere} - {document.niveau} - {badge_acces}")


def page_mes_paiements() -> None:
    st.subheader("Mes paiements")
    utilisateur = auth.utilisateur_courant()
    historique = payments.paiements_utilisateur(utilisateur.id)
    if not historique:
        st.info("Aucune demande de paiement enregistree.")
        return
    for p in historique:
        document = archive_manager.obtenir_document(p.document_id)
        titre_document = document.titre if document else "Document supprime"
        with st.container(border=True):
            st.markdown(f"**{titre_document}**")
            st.caption(
                f"{p.montant} FCFA - {p.libelle_canal} - {p.libelle_statut} - "
                f"demande le {formater_date(p.date_demande)}"
            )


# =====================================================================
# Messagerie, annonces, notifications
# =====================================================================

def page_messagerie() -> None:
    st.subheader("Messagerie")
    utilisateur = auth.utilisateur_courant()

    colonne_liste, colonne_conversation = st.columns([1, 2])
    destinataire_id = None

    with colonne_liste:
        st.caption("Nouveau message")
        terme_recherche = st.text_input("Rechercher un destinataire", key="msg_recherche")
        if terme_recherche:
            resultats_recherche = [
                u for u in gestion_utilisateurs.rechercher_utilisateurs(terme_recherche) if u.id != utilisateur.id
            ]
            if resultats_recherche:
                choix = st.selectbox(
                    "Destinataire", resultats_recherche,
                    format_func=lambda u: f"{u.nom_complet} ({u.matricule})", key="msg_destinataire_recherche",
                )
                destinataire_id = choix.id if choix else None
            else:
                st.caption("Aucun utilisateur trouve.")

        st.divider()
        st.caption("Conversations")
        contacts = communication.correspondants(utilisateur.id)
        if not contacts:
            st.caption("Aucune conversation pour le moment.")
        for c in contacts:
            libelle = f"{c['prenom']} {c['nom']}"
            if c["non_lus"]:
                libelle += f" ({c['non_lus']})"
            if st.button(libelle, key=f"contact_{c['id']}", use_container_width=True):
                destinataire_id = c["id"]

    with colonne_conversation:
        if destinataire_id:
            correspondant = gestion_utilisateurs.obtenir_utilisateur(destinataire_id)
            if correspondant:
                colonne_avatar_corresp, colonne_nom_corresp = st.columns([1, 8])
                with colonne_avatar_corresp:
                    if correspondant.photo:
                        try:
                            st.image(correspondant.photo, width=36)
                        except Exception:
                            pass
                with colonne_nom_corresp:
                    st.markdown(f"**{correspondant.nom_complet}**")
                st.divider()

            communication.marquer_conversation_lue(utilisateur.id, destinataire_id)
            messages = communication.conversation(utilisateur.id, destinataire_id)
            for m in messages:
                auteur = "Vous" if m.expediteur_id == utilisateur.id else "Correspondant"
                st.markdown(f"**{auteur}** ({formater_date(m.date_envoi)}) : {m.contenu}")
            nouveau_message = st.text_area("Votre message", key="msg_contenu")
            if st.button("Envoyer", icon=icone("Edit"), key="msg_envoyer"):
                succes, message = communication.envoyer_message(utilisateur.id, destinataire_id, nouveau_message)
                (st.success if succes else st.error)(message)
                if succes:
                    st.rerun()
        else:
            st.info("Selectionnez une conversation existante ou recherchez un destinataire.")


def page_annonces() -> None:
    st.subheader("Annonces")
    utilisateur = auth.utilisateur_courant()
    annonces = communication.annonces_pour_role(utilisateur.role)
    if not annonces:
        st.info("Aucune annonce pour le moment.")
        return
    for a in annonces:
        with st.container(border=True):
            st.markdown(f"**{a.titre}**")
            st.caption(formater_date(a.date_publication, avec_heure=False))
            st.write(a.contenu)


def page_notifications() -> None:
    st.subheader("Notifications")
    utilisateur = auth.utilisateur_courant()
    notifs = communication.notifications_utilisateur(utilisateur.id)
    if not notifs:
        st.info("Aucune notification.")
        return
    if st.button("Tout marquer comme lu", icon=icone("Bell")):
        communication.marquer_toutes_notifications_lues(utilisateur.id)
        st.rerun()
    for n in notifs:
        with st.container(border=True):
            etat = "" if n.lu else " - nouveau"
            st.markdown(f"**{n.libelle_type}{etat}**")
            st.caption(formater_date(n.date_creation))
            st.write(n.contenu)
            if not n.lu:
                if st.button("Marquer comme lu", key=f"lu_{n.id}"):
                    communication.marquer_notification_lue(n.id)
                    st.rerun()


# =====================================================================
# Parametres personnels
# =====================================================================

def page_parametres() -> None:
    st.subheader("Parametres")
    utilisateur = auth.utilisateur_courant()

    onglet_profil, onglet_preferences, onglet_securite = st.tabs(["Profil", "Preferences", "Securite"])

    with onglet_profil:
        colonne_photo, colonne_infos = st.columns([1, 3])
        with colonne_photo:
            if utilisateur.photo:
                try:
                    st.image(utilisateur.photo, width=120)
                except Exception:
                    pass
                if st.button("Supprimer la photo", key="supprimer_photo"):
                    succes, message = gestion_utilisateurs.supprimer_photo_profil(utilisateur.id)
                    (st.success if succes else st.error)(message)
                    if succes:
                        st.session_state["utilisateur_connecte"] = gestion_utilisateurs.obtenir_utilisateur(utilisateur.id)
                        st.rerun()

            nouvelle_photo = st.file_uploader("Importer une photo", type=["jpg", "jpeg", "png"], key="upload_photo")
            if nouvelle_photo and st.button("Mettre a jour la photo"):
                photo_valide, erreur = fichier_est_photo_valide(nouvelle_photo)
                if not photo_valide:
                    st.error(erreur)
                else:
                    chemin = enregistrer_photo(nouvelle_photo)
                    gestion_utilisateurs.modifier_photo_profil(utilisateur.id, chemin)
                    st.session_state["utilisateur_connecte"] = gestion_utilisateurs.obtenir_utilisateur(utilisateur.id)
                    st.success("Photo mise a jour.")
                    st.rerun()

            photo_webcam = st.camera_input("Ou prendre une photo avec la webcam", key="webcam_photo")
            if photo_webcam and st.button("Utiliser cette photo", key="utiliser_photo_webcam"):
                photo_valide, erreur = fichier_est_photo_valide(photo_webcam)
                if not photo_valide:
                    st.error(erreur)
                else:
                    chemin = enregistrer_photo(photo_webcam)
                    gestion_utilisateurs.modifier_photo_profil(utilisateur.id, chemin)
                    st.session_state["utilisateur_connecte"] = gestion_utilisateurs.obtenir_utilisateur(utilisateur.id)
                    st.success("Photo mise a jour.")
                    st.rerun()
        with colonne_infos:
            st.write(f"**Matricule :** {utilisateur.matricule}")
            st.write(f"**Filiere :** {utilisateur.filiere or '-'}")
            st.write(f"**Niveau :** {utilisateur.niveau or '-'}")
            st.write(f"**Role :** {LIBELLES_ROLE.get(utilisateur.role, utilisateur.role)}")
            st.caption(
                f"Inscrit le {formater_date(utilisateur.date_inscription)} - "
                f"derniere connexion le {formater_date(utilisateur.derniere_connexion)}"
            )
            st.caption("Le matricule, la filiere, le niveau et le role sont geres par l'administration.")

            nouveau_nom = st.text_input("Nom", value=utilisateur.nom, key="profil_nom")
            nouveau_prenom = st.text_input("Prenom", value=utilisateur.prenom, key="profil_prenom")
            nouvel_email = st.text_input("E-mail", value=utilisateur.email, key="profil_email")
            nouvelle_bio = st.text_area(
                "Biographie", value=utilisateur.bio or "", key="profil_bio",
                placeholder="Quelques mots a votre sujet (visible par les autres utilisateurs).",
                max_chars=2000,
            )
            if st.button("Enregistrer les modifications", key="profil_enregistrer"):
                succes, message = gestion_utilisateurs.modifier_mon_profil(
                    utilisateur.id, nom=nouveau_nom, prenom=nouveau_prenom,
                    email=nouvel_email, bio=nouvelle_bio,
                )
                (st.success if succes else st.error)(message)
                if succes:
                    st.session_state["utilisateur_connecte"] = gestion_utilisateurs.obtenir_utilisateur(utilisateur.id)
                    st.rerun()

    with onglet_preferences:
        # Le theme est applique instantanement a la simple selection
        # (nouveau en V4, cahier des charges point 13) : plus besoin de
        # cliquer sur un bouton "Enregistrer" separe pour voir l'effet,
        # le rerun naturel de Streamlit au changement du radio suffit.
        # La langue, elle, reste sur un bouton explicite : son
        # changement n'a pas d'effet visuel immediat a confirmer.
        theme_choisi = st.radio(
            "Theme", THEMES_VALIDES, index=THEMES_VALIDES.index(utilisateur.theme),
            format_func=lambda t: LIBELLES_THEME.get(t, t), horizontal=True,
            key="radio_theme_utilisateur",
        )
        if theme_choisi != utilisateur.theme:
            gestion_utilisateurs.modifier_preferences(utilisateur.id, theme=theme_choisi)
            st.session_state["utilisateur_connecte"] = gestion_utilisateurs.obtenir_utilisateur(utilisateur.id)
            st.rerun()

        langue_choisie = st.radio(
            "Langue", LANGUES_VALIDES, index=LANGUES_VALIDES.index(utilisateur.langue),
            format_func=lambda l: LIBELLES_LANGUE.get(l, l), horizontal=True,
        )
        if st.button("Enregistrer les preferences"):
            succes, message = gestion_utilisateurs.modifier_preferences(
                utilisateur.id, langue=langue_choisie
            )
            (st.success if succes else st.error)(message)
            if succes:
                st.session_state["utilisateur_connecte"] = gestion_utilisateurs.obtenir_utilisateur(utilisateur.id)
                st.rerun()

    with onglet_securite:
        ancien_mdp = st.text_input("Mot de passe actuel", type="password", key="ancien_mdp")
        nouveau_mdp = st.text_input(
            "Nouveau mot de passe", type="password", key="nouveau_mdp_perso",
            help="Au moins 8 caracteres, avec au moins une lettre et un chiffre.",
        )
        confirmation_mdp = st.text_input(
            "Confirmer le nouveau mot de passe", type="password", key="confirmation_mdp_perso"
        )
        if st.button("Changer le mot de passe"):
            if nouveau_mdp != confirmation_mdp:
                st.error("Les mots de passe ne correspondent pas.")
            else:
                succes, message = gestion_utilisateurs.changer_mon_mot_de_passe(
                    utilisateur.id, ancien_mdp, nouveau_mdp
                )
                (st.success if succes else st.error)(message)

    st.divider()
    if st.button("Se deconnecter", icon=icone("LogOut")):
        jeton_cookie = _gestionnaire_cookies().get(NOM_COOKIE_SESSION)
        if jeton_cookie:
            auth.revoquer_jeton_session(jeton_cookie)
            _gestionnaire_cookies().delete(NOM_COOKIE_SESSION)
        auth.deconnecter()
        if auth.oidc_utilisateur_connecte():
            st.logout()
        else:
            st.rerun()


def page_configuration_systeme() -> None:
    """Parametres globaux de la plateforme (reserve a l'administration), distincts des Parametres personnels."""
    auth.exiger_role("administrateur")
    st.subheader("Configuration systeme")
    utilisateur = auth.utilisateur_courant()
    for parametre in parametres_systeme.lister_parametres():
        nouvelle_valeur = st.text_input(
            parametre["description"] or parametre["cle"],
            value=parametre["valeur"],
            key=f"parametre_{parametre['cle']}",
        )
        if nouvelle_valeur != parametre["valeur"]:
            parametres_systeme.definir_parametre(parametre["cle"], nouvelle_valeur, utilisateur.id)
            st.rerun()


# =====================================================================
# Navigation et routage
# =====================================================================

# =====================================================================
# Robot d'orientation (nouveau en V4)
# =====================================================================

def _afficher_robot_orientation() -> None:
    """ Petit assistant d'orientation (nouveau en V4, cahier des charges point 6), toujours disponible -- aucune cle API, aucune dependance reseau : les reponses proviennent entierement de la FAQ de navigation (models.FAQ_NAVIGATION, voir assistant.py pour le moteur de correspondance par mots-cles). L'historique de la conversation en cours est conserve dans st.session_state pour la duree de la session uniquement (jamais en base de donnees). """
    with st.popover("Assistant", icon=icone("Chat"), use_container_width=True):
        st.caption("Posez une question sur la navigation dans SOURCE ISABEE.")
        historique = st.session_state.setdefault("assistant_historique", [])

        if not historique:
            st.caption("Exemples de questions :")
            for suggestion in assistant.suggestions_questions():
                if st.button(suggestion, key=f"suggestion_{suggestion}", use_container_width=True):
                    reponse = assistant.repondre(suggestion)
                    historique.append({"role": "user", "content": suggestion})
                    historique.append({"role": "assistant", "content": reponse})
                    st.rerun()

        for echange in historique[-8:]:
            with st.chat_message("user" if echange["role"] == "user" else "assistant"):
                st.write(echange["content"])

        question = st.chat_input("Votre question...", key="assistant_question")
        if question:
            reponse = assistant.repondre(question)
            historique.append({"role": "user", "content": question})
            historique.append({"role": "assistant", "content": reponse})
            del historique[:-12]
            st.rerun()


def _menu_navigation(utilisateur) -> str:
    with st.sidebar:
        try:
            st.image(CHEMIN_LOGO, width=56)
        except Exception:
            pass
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:6px;opacity:0.7;">'
            f'{icons.svg("Home", taille=14)}<span>SOURCE ISABEE</span></div>',
            unsafe_allow_html=True,
        )
        if utilisateur.photo:
            try:
                st.image(utilisateur.photo, width=48)
            except Exception:
                pass
        st.markdown(f"**{utilisateur.nom_complet}**")
        st.caption(LIBELLES_ROLE.get(utilisateur.role, utilisateur.role))

        page_active = st.session_state.get("page_active", "Bibliotheque")

        def _bouton(libelle: str, nom_icone: str, badge: int = 0) -> None:
            """ Bouton de navigation de la sidebar. Si badge > 0, un badge numerote de type WhatsApp/Android est affiche a cote du libelle (nouveau en V4, cahier des charges point 1) : implemente en HTML/CSS juste avant le bouton plutot que dans le libelle du bouton lui-meme (Streamlit ne permet pas d'inserer du HTML dans le texte d'un st.button), avec une legere animation d'apparition (voir assets/style.css, classe .badge-notification). """
            actif = page_active == libelle
            if badge > 0:
                texte_badge = "99+" if badge > 99 else str(badge)
                st.markdown(
                    f'<div class="conteneur-bouton-badge">'
                    f'<span class="badge-notification">{texte_badge}</span></div>',
                    unsafe_allow_html=True,
                )
            if st.button(
                libelle, key=f"nav_{libelle}", icon=icone(nom_icone),
                use_container_width=True, type="primary" if actif else "secondary",
            ):
                st.session_state["page_active"] = libelle
                st.rerun()

        # Compteurs non lus (deja calcules par communication.py depuis
        # la V2/V3 ; nouveaute V4 : ils sont desormais affiches sous
        # forme de badge visuel a cote du bouton concerne, et non plus
        # seulement en texte). Les fonctions sous-jacentes ne sont pas
        # dupliquees ici.
        non_lus_notifications = communication.nombre_notifications_non_lues(utilisateur.id)
        non_lus_messages = communication.nombre_messages_non_lus(utilisateur.id)
        en_attente_validation = 0
        if auth.a_le_role("enseignant", "administrateur"):
            en_attente_validation = len(archive_manager.documents_en_attente())

        st.divider()
        st.caption("Espace")
        _bouton("Bibliotheque", "FileText")
        if auth.a_le_role("etudiant", "enseignant", "contributeur"):
            _bouton("Mes favoris", "Home")
            _bouton("Mes telechargements", "Download")
            _bouton("Historique", "History")
            _bouton("Mes paiements", "FileText")
        _bouton("Messagerie", "Users", badge=non_lus_messages)
        _bouton("Annonces", "Bell")
        _bouton("Notifications", "Bell", badge=non_lus_notifications)
        _bouton("Parametres", "Settings")

        if auth.a_le_role("enseignant", "contributeur", "administrateur"):
            st.divider()
            st.caption("Pedagogie")
            _bouton("Deposer un document", "Edit")
            if auth.a_le_role("enseignant", "administrateur"):
                _bouton("Gestion des validations", "Bell", badge=en_attente_validation)

        if auth.a_le_role("administrateur"):
            st.divider()
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:6px;opacity:0.7;">'
                f'{icons.svg("Settings", taille=14)}<span>Administration</span></div>',
                unsafe_allow_html=True,
            )
            _bouton("Tableau de bord", "BarChart")
            _bouton("Gestion des documents", "FileText")
            _bouton("Gestion des comptes", "Users")
            _bouton("Gestion des paiements", "FileText")
            _bouton("Moyens de paiement", "Wallet")
            _bouton("Corbeille", "Trash")
            _bouton("Gestion des tags", "Edit")
            _bouton("Gestion des annonces", "Bell")
            _bouton("Gestion des commentaires", "Edit")
            _bouton("Gestion des notifications", "Bell")
            _bouton("Configuration systeme", "Settings")
            _bouton("Journal systeme", "FileText")
            _bouton("Maintenance", "Settings")

        st.divider()
        st.caption("Aide")
        _bouton("Centre d'aide", "Help")
        _bouton("A propos", "Info")
        _bouton("Contact", "Mail")
        _bouton("Politique de confidentialite", "Shield")
        _bouton("Conditions d'utilisation", "Gavel")

        st.divider()
        if st.button("Se deconnecter", icon=icone("LogOut"), use_container_width=True):
            jeton_cookie = _gestionnaire_cookies().get(NOM_COOKIE_SESSION)
            if jeton_cookie:
                auth.revoquer_jeton_session(jeton_cookie)
                _gestionnaire_cookies().delete(NOM_COOKIE_SESSION)
            auth.deconnecter()
            if auth.oidc_utilisateur_connecte():
                st.logout()
            else:
                st.rerun()

        # Robot d'orientation (nouveau en V4) : moteur de regles base
        # sur la FAQ de navigation (voir assistant.py), sans aucune
        # cle API ni dependance reseau -- toujours disponible.
        st.divider()
        _afficher_robot_orientation()

    return st.session_state.get("page_active", "Bibliotheque")


def main() -> None:
    _initialiser_application()

    if _aucun_compte_existant():
        _afficher_en_tete_publique()
        page_initialisation()
        return

    if not auth.est_connecte():
        if auth.oidc_utilisateur_connecte():
            nom_complet = (getattr(st.user, "name", None) or "").strip()
            prenom_oidc = getattr(st.user, "given_name", None) or (
                nom_complet.split(" ")[0] if nom_complet else ""
            )
            nom_oidc = getattr(st.user, "family_name", None) or (
                " ".join(nom_complet.split(" ")[1:]) if " " in nom_complet else ""
            )
            email_oidc = getattr(st.user, "email", None)
            if email_oidc:
                succes, message = auth.connecter_via_oidc(email_oidc, prenom_oidc, nom_oidc)
                if succes:
                    st.rerun()
                else:
                    st.error(message)

        # Connexion persistante par cookie ("se souvenir de moi") : un
        # simple rafraichissement de la page ne doit jamais redemander
        # de connexion tant que le cookie est valide. Le composant
        # cookie a besoin d'un aller-retour navigateur pour se charger ;
        # sur le tout premier rendu apres un rafraichissement, get()
        # peut encore renvoyer None pendant une fraction de seconde --
        # dans ce cas, la page de connexion s'affiche brievement puis
        # se rafraichit automatiquement une fois le cookie disponible.
        if not auth.est_connecte():
            jeton_cookie = _gestionnaire_cookies().get(NOM_COOKIE_SESSION)
            if jeton_cookie:
                succes, message = auth.connecter_via_jeton_session(jeton_cookie)
                if succes:
                    st.rerun()

        if not auth.est_connecte():
            _afficher_en_tete_publique()
            page_connexion()
            return

    duree_session = parametres_systeme.obtenir_parametre_entier(
        "expiration_session_minutes", auth.DUREE_MAX_INACTIVITE_MINUTES
    )
    auth.verifier_session_active(duree_max_minutes=duree_session)

    utilisateur = auth.utilisateur_courant()
    if utilisateur is None:
        # La session a expire pendant verifier_session_active, qui a deja
        # arrete le rendu de la page (st.stop()). Branche defensive
        # uniquement : ne devrait jamais s'executer en pratique.
        return

    if parametres_systeme.obtenir_parametre("mode_maintenance", "non") == "oui" and utilisateur.role != "administrateur":
        _afficher_en_tete_publique()
        st.warning(parametres_systeme.obtenir_parametre(
            "message_maintenance",
            "La plateforme est temporairement en maintenance. Merci de revenir un peu plus tard.",
        ))
        if st.button("Se deconnecter", icon=icone("LogOut")):
            jeton_cookie = _gestionnaire_cookies().get(NOM_COOKIE_SESSION)
            if jeton_cookie:
                auth.revoquer_jeton_session(jeton_cookie)
                _gestionnaire_cookies().delete(NOM_COOKIE_SESSION)
            auth.deconnecter()
            if auth.oidc_utilisateur_connecte():
                st.logout()
            else:
                st.rerun()
        return

    if utilisateur.theme == "sombre":
        try:
            charger_css("assets/style-sombre.css")
        except FileNotFoundError:
            pass

    _afficher_barre_superieure()
    page_choisie = _menu_navigation(utilisateur)

    pages = {
        "Bibliotheque": page_bibliotheque,
        "Mes favoris": page_favoris,
        "Mes telechargements": page_mes_telechargements,
        "Historique": page_historique,
        "Mes paiements": page_mes_paiements,
        "Messagerie": page_messagerie,
        "Annonces": page_annonces,
        "Notifications": page_notifications,
        "Parametres": page_parametres,
        "Deposer un document": page_depot_document,
        "Gestion des validations": admin.page_moderation_documents,
        "Tableau de bord": admin.page_tableau_de_bord,
        "Gestion des documents": admin.page_gestion_documents,
        "Gestion des comptes": admin.page_gestion_utilisateurs,
        "Gestion des paiements": admin.page_gestion_paiements,
        "Moyens de paiement": admin.page_gestion_moyens_paiement,
        "Corbeille": admin.page_gestion_corbeille,
        "Gestion des tags": admin.page_gestion_tags,
        "Gestion des annonces": admin.page_gestion_annonces,
        "Gestion des commentaires": admin.page_gestion_commentaires,
        "Gestion des notifications": admin.page_gestion_notifications,
        "Configuration systeme": page_configuration_systeme,
        "Journal systeme": admin.page_journal_systeme,
        "Maintenance": admin.page_maintenance,
        "Centre d'aide": pages_institutionnelles.page_centre_aide,
        "A propos": pages_institutionnelles.page_a_propos,
        "Contact": pages_institutionnelles.page_contact,
        "Politique de confidentialite": pages_institutionnelles.page_politique_confidentialite,
        "Conditions d'utilisation": pages_institutionnelles.page_conditions_utilisation,
    }
    page_fonction = pages.get(page_choisie, page_bibliotheque)
    page_fonction()


if __name__ == "__main__":
    main()
