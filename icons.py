"""
icons.py
--------
Role : fournir les veritables icones Lucide (pixel-parfaites), via le
paquet Python "python-lucide" (PyPI, import : from lucide import
lucide_icon -- voir requirements.txt), pour la sidebar et les
en-tetes de page personnalises de l'application.

Ce n'est plus une approximation dessinee a la main : ce paquet
embarque une base de donnees generee directement a partir du depot
officiel lucide-icons/lucide (meme source que lucide-react), et
restitue le SVG d'origine tel quel -- aucune approximation. Licence
MIT (le paquet et les icones Lucide elles-memes). Voir
https://pypi.org/project/python-lucide/.

Chaque nom de cle ci-dessous a ete verifie individuellement contre la
fiche de l'icone sur https://lucide.dev/icons/<nom> avant integration
(Lucide renomme parfois ses icones d'une version a l'autre ; les noms
retenus ici sont les noms canoniques actuels, pas des alias) :
- house        (anciennement nomme "home")
- file-text
- users
- search
- download
- settings
- bell
- trash-2      (variante avec couvercle/lignes, pas le simple "trash")
- pencil       (anciennement nomme "edit"/"edit-2")
- chart-bar
- log-out
- qr-code
- wallet

IMPORTANT -- limitation de la plate-forme Streamlit, pas de ce module :
les widgets natifs qui imposent leur propre systeme d'icone (st.button,
st.download_button, st.expander, st.form_submit_button, st.popover)
n'acceptent qu'un emoji ou un nom Material Symbols pour leur parametre
icon= ; ils ne peuvent recevoir aucun SVG personnalise, Lucide ou
autre. Voir utils.icone() pour ces cas precis. Les fonctions de ce
module s'utilisent uniquement via st.markdown(..., unsafe_allow_html=True).
"""

from lucide import lucide_icon

_NOMS_LUCIDE = {
    "Home": "house",
    "FileText": "file-text",
    "Users": "users",
    "Search": "search",
    "Download": "download",
    "Settings": "settings",
    "Bell": "bell",
    "Trash": "trash-2",
    "Edit": "pencil",
    "BarChart": "chart-bar",
    "LogOut": "log-out",
    "QrCode": "qr-code",
    "Wallet": "wallet",
}

NOMS_DISPONIBLES = tuple(_NOMS_LUCIDE.keys())


def svg(nom: str, taille: int = 20, couleur: str = "currentColor") -> str:
    """
    Retourne le balisage SVG inline d'une icone Lucide authentique,
    destine a etre insere dans du HTML via st.markdown(...,
    unsafe_allow_html=True).

    Retourne l'icone "circle" (cercle simple) si le nom demande
    n'existe pas dans notre table de correspondance, plutot que de
    lever une exception qui casserait l'affichage de toute une page
    pour une simple faute de frappe sur un nom d'icone.
    """
    nom_lucide = _NOMS_LUCIDE.get(nom, "circle")
    return lucide_icon(
        nom_lucide,
        width=str(taille),
        height=str(taille),
        stroke=couleur,
        stroke_width="1.8",
        stroke_linecap="round",
        stroke_linejoin="round",
        fallback_text="",
    )
