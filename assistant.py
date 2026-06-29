"""
assistant.py
------------
Role : robot d'orientation ("ou trouver les documents ?", "comment
publier ?", "ou modifier mon profil ?", "comment contacter
l'administration ?"...), cahier des charges V4, point 6.

Principe retenu : un moteur de regles simple, base entierement sur le
contenu deja present dans l'application (la FAQ de navigation
centralisee dans models.FAQ_NAVIGATION, partagee avec la page Centre
d'aide -- voir pages_institutionnelles.page_centre_aide), PAS sur un
appel a une intelligence artificielle externe. Aucune cle API, aucune
dependance reseau, aucun cout par question posee : le robot fonctionne
entierement hors-ligne, a partir des donnees deja chargees en memoire.

Methode de mise en correspondance : pour chaque question posee par
l'utilisateur, on calcule un score de pertinence pour chaque entree de
la FAQ (nombre de mots-cles ou de mots de la question qui apparaissent
dans le texte saisi), et on retourne la reponse de l'entree au score
le plus eleve. Si aucune entree n'atteint un score minimal, le robot
repond honnetement qu'il n'a pas trouve, plutot que de proposer une
reponse non pertinente, et oriente vers le Centre d'aide ou la page
Contact.
"""

import re

from models import FAQ_NAVIGATION

SCORE_MINIMAL_PERTINENCE = 2

# Mots trop frequents pour etre discriminants dans le calcul de score
# (articles, prepositions courantes...) : ignores lors de la
# comparaison mot a mot de la question posee, afin que "comment" ou
# "je" ne faussent pas la pertinence calculee.
_MOTS_VIDES = frozenset({
    "le", "la", "les", "un", "une", "des", "de", "du", "et", "ou", "a",
    "je", "tu", "il", "elle", "nous", "vous", "ils", "mon", "ma", "mes",
    "comment", "est", "ce", "que", "qui", "pour", "dans", "sur", "avec",
    "se", "sa", "son", "ses", "au", "aux", "en", "ne", "pas", "fait",
})


def _normaliser(texte: str) -> str:
    """Minuscules, sans ponctuation, espaces simplifies -- pour une comparaison robuste."""
    texte = texte.lower()
    texte = re.sub(r"[^\w\s]", " ", texte)
    return re.sub(r"\s+", " ", texte).strip()


def _mots_significatifs(texte_normalise: str) -> set[str]:
    return {mot for mot in texte_normalise.split() if mot not in _MOTS_VIDES and len(mot) > 1}


def _score_entree(question_normalisee: str, mots_question: set[str], mots_cles: tuple[str, ...]) -> int:
    """
    Score de pertinence d'une entree de FAQ pour la question posee :
    +2 par mot-cle (potentiellement compose de plusieurs mots) trouve
    tel quel dans le texte de la question, +1 par mot significatif de
    la question qui correspond exactement a un mot entier d'un des
    mots-cles de l'entree. La comparaison se fait toujours sur des
    mots entiers, avec des limites de mot explicites (\\b), jamais une
    simple inclusion de sous-chaine : "ca" est par exemple une
    sous-chaine de "publication" sans aucun rapport de sens, et
    inversement "mot de passe" ne doit pas matcher juste parce que
    "de" apparait quelque part dans la question.
    """
    score = 0
    for mot_cle in mots_cles:
        motif = r"\b" + re.escape(mot_cle) + r"\b"
        if re.search(motif, question_normalisee):
            score += 2
    mots_des_mots_cles: set[str] = set()
    for mot_cle in mots_cles:
        mots_des_mots_cles.update(mot_cle.split())
    for mot in mots_question:
        if mot in mots_des_mots_cles:
            score += 1
    return score


def repondre(question: str) -> str:
    """
    Trouve, parmi la FAQ de navigation (models.FAQ_NAVIGATION), la
    reponse la plus pertinente a la question posee, par simple
    correspondance de mots-cles (aucun appel reseau, aucune IA
    externe). Retourne toujours une chaine non vide : soit la reponse
    trouvee, soit un message d'orientation honnete si rien de
    suffisamment pertinent n'a ete trouve.
    """
    question = (question or "").strip()
    if not question:
        return "Posez-moi une question sur la navigation dans SOURCE ISABEE (ex. \"comment telecharger un document ?\")."

    question_normalisee = _normaliser(question)
    mots_question = _mots_significatifs(question_normalisee)

    meilleur_score = 0
    meilleure_reponse = None
    for _question_faq, reponse_faq, mots_cles in FAQ_NAVIGATION:
        score = _score_entree(question_normalisee, mots_question, mots_cles)
        if score > meilleur_score:
            meilleur_score = score
            meilleure_reponse = reponse_faq

    if meilleur_score >= SCORE_MINIMAL_PERTINENCE and meilleure_reponse:
        return meilleure_reponse

    return (
        "Je n'ai pas trouve de reponse precise a cette question dans mes repères de "
        "navigation. Consultez le \"Centre d'aide\" pour la liste complete des "
        "questions frequentes, ou contactez l'administration depuis la page "
        "\"Contact\" si vous ne trouvez pas votre reponse."
    )


def suggestions_questions(nombre: int = 4) -> list[str]:
    """
    Quelques questions d'exemple a afficher comme suggestions cliquables
    sous le robot (pour orienter une personne qui ne sait pas quoi
    demander). Toujours les memes premieres entrees de la FAQ, dans
    leur ordre de declaration -- pas un tirage aleatoire, afin que les
    suggestions les plus utiles (creation de compte, publication,
    telechargement, contact) restent prioritaires.
    """
    return [question for question, _reponse, _mots_cles in FAQ_NAVIGATION[:nombre]]
