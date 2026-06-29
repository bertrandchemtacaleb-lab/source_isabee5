"""
pages_institutionnelles.py
---------------------------
Role : pages statiques institutionnelles attendues d'une plateforme
prete pour la commercialisation (cahier des charges V4, points 8 a 12) :
- politique de confidentialite ;
- conditions d'utilisation (CGU) ;
- centre d'aide (FAQ) ;
- a propos (presentation, version, developpeur) ;
- contact (coordonnees + formulaire).

Ce module ne contient aucune logique metier sensible (pas d'acces aux
donnees personnelles d'autres utilisateurs) : il s'agit de contenu
essentiellement statique, accessible a tout utilisateur connecte, au
meme titre que la Bibliotheque. Le formulaire de contact (page_contact)
reutilise communication.envoyer_message vers le premier administrateur
actif trouve, plutot que de dupliquer un nouveau circuit de messagerie :
aucune nouvelle table n'est necessaire pour cette fonctionnalite.
"""

import streamlit as st

from models import INFOS_DEVELOPPEUR, VERSION_APPLICATION, FAQ_NAVIGATION
from utils import icone
import communication
import users as gestion_utilisateurs
from auth import utilisateur_courant


# =====================================================================
# Politique de confidentialite
# =====================================================================

def page_politique_confidentialite() -> None:
    st.subheader("Politique de confidentialite")
    st.caption("Derniere mise a jour : voir la version de l'application en bas de cette page.")

    with st.expander("Donnees collectees", expanded=True, icon=icone("Shield")):
        st.write(
            "SOURCE ISABEE collecte uniquement les informations necessaires au "
            "fonctionnement de la plateforme pedagogique : identite (nom, prenom, "
            "matricule), coordonnees (adresse e-mail), cursus (cycle, filiere, "
            "niveau), ainsi que, de maniere facultative, une photo de profil et une "
            "biographie. Les documents que vous deposez, vos messages, commentaires "
            "et demandes de paiement sont egalement conserves pour assurer le bon "
            "fonctionnement du service."
        )

    with st.expander("Utilisation des donnees"):
        st.write(
            "Ces informations sont utilisees exclusivement pour : vous identifier "
            "et securiser votre acces, afficher votre profil aux autres utilisateurs "
            "de la plateforme (nom, photo), gerer l'acces aux documents payants, "
            "et assurer la communication interne (messagerie, annonces, "
            "notifications). Aucune donnee n'est vendue, louee ou transmise a des "
            "tiers a des fins commerciales."
        )

    with st.expander("Protection des donnees"):
        st.write(
            "Les mots de passe ne sont jamais stockes en clair : seul un hachage "
            "sale et etire (voir auth.py) est conserve. Toute saisie utilisateur "
            "affichee dans l'interface est systematiquement echappee afin de "
            "prevenir les injections de code (voir utils.echapper_html). L'acces "
            "aux fonctions d'administration est strictement reserve aux comptes "
            "ayant le role administrateur."
        )

    with st.expander("Duree de conservation"):
        st.write(
            "Vos donnees sont conservees pendant toute la duree de votre inscription "
            "sur la plateforme. Un document supprime est d'abord place en corbeille "
            "(reversible) avant suppression definitive. Le journal systeme (connexions, "
            "actions sensibles) est conserve a des fins de securite et d'audit."
        )

    with st.expander("Vos droits"):
        st.write(
            "Vous pouvez a tout moment consulter et corriger vos informations "
            "personnelles depuis Parametres > Profil, changer votre mot de passe "
            "depuis Parametres > Securite, et supprimer votre photo de profil. Pour "
            "toute demande de suppression complete de votre compte ou d'export de "
            "vos donnees, contactez l'administration depuis la page Contact."
        )

    with st.expander("Securite"):
        st.write(
            "Le nombre de tentatives de connexion infructueuses est limite et "
            "journalise independamment du navigateur utilise. Une session inactive "
            "se ferme automatiquement apres une duree configurable par "
            "l'administration. Pour un deploiement public, l'hebergeur est responsable "
            "de la mise en place du chiffrement du trafic (HTTPS)."
        )

    with st.expander("Cookies"):
        st.write(
            "Un seul cookie technique est utilise, exclusivement pour la connexion "
            "persistante (\"Se souvenir de moi\") : il contient un jeton opaque, "
            "jamais vos informations personnelles ni votre mot de passe. Aucun "
            "cookie publicitaire ou de suivi tiers n'est depose par l'application."
        )

    with st.expander("Contact"):
        st.write(
            f"Pour toute question relative a vos donnees personnelles, contactez "
            f"l'administration : {INFOS_DEVELOPPEUR['email']} ou via la page Contact."
        )

    st.divider()
    st.caption(f"SOURCE ISABEE - version {VERSION_APPLICATION}")


# =====================================================================
# Conditions d'utilisation (CGU)
# =====================================================================

def page_conditions_utilisation() -> None:
    st.subheader("Conditions d'utilisation")
    st.caption("En utilisant SOURCE ISABEE, vous acceptez les conditions ci-dessous.")

    with st.expander("Regles d'utilisation", expanded=True, icon=icone("Gavel")):
        st.write(
            "SOURCE ISABEE est reservee a la communaute pedagogique de l'ISABEE "
            "(etudiants, enseignants, contributeurs et personnel administratif). "
            "Chaque utilisateur est responsable de la confidentialite de ses "
            "identifiants de connexion et s'engage a fournir des informations "
            "exactes lors de son inscription."
        )

    with st.expander("Responsabilites"):
        st.write(
            "L'utilisateur qui depose un document est seul responsable du contenu "
            "qu'il publie et garantit detenir les droits necessaires pour le "
            "partager dans un cadre pedagogique. Tout document est soumis a "
            "validation par un enseignant, un contributeur habilite ou un "
            "administrateur avant d'etre visible des autres utilisateurs."
        )

    with st.expander("Contenus interdits"):
        st.write(
            "Sont strictement interdits : tout contenu protege par des droits "
            "d'auteur sans autorisation, tout contenu diffamatoire, injurieux, "
            "discriminatoire ou contraire a la loi, ainsi que toute tentative de "
            "contournement des mecanismes de securite de la plateforme (faux "
            "comptes, usurpation d'identite, fichiers malveillants deguises en "
            "PDF)."
        )

    with st.expander("Sanctions"):
        st.write(
            "Tout manquement aux presentes conditions peut entrainer, selon sa "
            "gravite : le retrait du contenu concerne, un avertissement, la "
            "suspension temporaire du compte, ou sa suspension definitive par un "
            "administrateur. Les actions sensibles (connexions, suppressions, "
            "validations) sont journalisees a des fins de tracabilite."
        )

    with st.expander("Propriete intellectuelle"):
        st.write(
            "Les documents pedagogiques deposes restent la propriete de leurs "
            "auteurs respectifs (enseignants, etudiants contributeurs) ; leur mise "
            "a disposition sur la plateforme ne vaut pas cession de droits. Le nom "
            "\"SOURCE ISABEE\", le logo et l'interface de l'application sont la "
            "propriete de l'etablissement et de son developpeur."
        )

    st.divider()
    st.caption(f"SOURCE ISABEE - version {VERSION_APPLICATION}")


# =====================================================================
# Centre d'aide (FAQ)
# =====================================================================


def page_centre_aide() -> None:
    st.subheader("Centre d'aide")
    st.caption("Les questions les plus frequentes. Vous ne trouvez pas votre reponse ? Contactez-nous.")

    terme = st.text_input(
        "Rechercher dans la FAQ", placeholder="ex. mot de passe, telecharger, publier...",
        icon=icone("Search"),
    )
    entrees = FAQ_NAVIGATION
    if terme:
        terme_normalise = terme.strip().lower()
        entrees = tuple(
            (q, r, mots_cles) for q, r, mots_cles in FAQ_NAVIGATION
            if terme_normalise in q.lower() or terme_normalise in r.lower()
            or any(terme_normalise in mc for mc in mots_cles)
        )
        if not entrees:
            st.info("Aucune question ne correspond a votre recherche. Essayez un autre mot-cle.")

    for question, reponse, _mots_cles in entrees:
        with st.expander(question, icon=icone("Help")):
            st.write(reponse)

    st.divider()
    st.caption("Une question reste sans reponse ? Rendez-vous sur la page Contact, ou posez-la directement au robot d'orientation (en bas de la sidebar).")


# =====================================================================
# A propos
# =====================================================================

def page_a_propos() -> None:
    st.subheader("A propos de SOURCE ISABEE")

    st.write(
        "SOURCE ISABEE est la plateforme institutionnelle de gestion des "
        "ressources pedagogiques de l'ISABEE : une bibliotheque numerique "
        "organisee par filiere, cycle et niveau, un espace communautaire "
        "(messagerie, annonces, commentaires, notifications), et un circuit "
        "complet de monetisation des ressources payantes (paiement en "
        "presentiel ou par Mobile Money)."
    )

    colonne_1, colonne_2 = st.columns(2)
    with colonne_1:
        st.markdown(f"**Version**  \n{VERSION_APPLICATION}")
        st.markdown(f"**Developpeur**  \n{INFOS_DEVELOPPEUR['nom']}")
    with colonne_2:
        st.markdown("**Objectif**  \nFaciliter l'acces aux ressources pedagogiques et "
                    "moderniser la gestion academique de l'etablissement.")

    st.divider()
    st.markdown("**Historique**")
    st.write(
        "- **V1** : bibliotheque numerique de base, depot et consultation de documents.\n"
        "- **V2** : monetisation des documents payants, espace communautaire "
        "(messagerie, annonces, notifications, commentaires), garde de session.\n"
        "- **V3** : corbeille (suppression reversible), paiement Mobile Money, "
        "connexion Google/Microsoft, inscription libre, mot de passe oublie, "
        "recherche plein texte, tags, connexion persistante.\n"
        f"- **V{VERSION_APPLICATION.split('.')[0]}** (version actuelle) : badges de "
        "notification, galerie d'images de couverture, robot d'orientation, "
        "page de maintenance complete, pages institutionnelles (confidentialite, "
        "CGU, aide, contact), historique de consultation, et renforcement general "
        "de l'experience utilisateur en vue de la commercialisation."
    )

    st.divider()
    st.caption("Coordonnees du developpeur disponibles sur la page Contact.")


# =====================================================================
# Contact
# =====================================================================

def page_contact() -> None:
    st.subheader("Contact")
    st.caption("Plusieurs moyens de nous joindre, ou un message direct via le formulaire ci-dessous.")

    colonne_coordonnees, colonne_formulaire = st.columns([1, 1.4])

    with colonne_coordonnees:
        with st.container(border=True):
            st.markdown(f"**WhatsApp**  \n{INFOS_DEVELOPPEUR['whatsapp']}")
            st.divider()
            st.markdown("**Telephones**")
            for numero in INFOS_DEVELOPPEUR["telephones"]:
                st.write(numero)
            st.divider()
            st.markdown(f"**E-mail**  \n{INFOS_DEVELOPPEUR['email']}")
            st.divider()
            st.markdown(f"**Facebook**  \n{INFOS_DEVELOPPEUR['facebook']}")

    with colonne_formulaire:
        st.markdown("**Formulaire de contact**")
        utilisateur = utilisateur_courant()
        with st.form("formulaire_contact", clear_on_submit=True):
            sujet = st.text_input("Sujet")
            message_contenu = st.text_area("Votre message", height=160)
            valide = st.form_submit_button("Envoyer", icon=icone("Mail"))
            if valide:
                if not sujet or not message_contenu or not message_contenu.strip():
                    st.error("Veuillez renseigner le sujet et votre message.")
                else:
                    administrateurs = gestion_utilisateurs.lister_utilisateurs(role="administrateur")
                    if not administrateurs:
                        st.error(
                            "Aucun compte administrateur n'est encore configure sur cette "
                            "installation. Veuillez utiliser les coordonnees ci-contre."
                        )
                    else:
                        contenu_complet = f"[Contact] {sujet.strip()}\n\n{message_contenu.strip()}"
                        succes, msg = communication.envoyer_message(
                            utilisateur.id, administrateurs[0].id, contenu_complet
                        )
                        if succes:
                            st.success("Votre message a ete transmis a l'administration.")
                        else:
                            st.error(msg)
