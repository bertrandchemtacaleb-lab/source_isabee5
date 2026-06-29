"""
database.py
-----------
Role : couche d'acces unique a la base de donnees SQLite.

Ce module est le seul point d'entree autorise vers le fichier .db.
Aucun autre module ne doit ouvrir une connexion sqlite3 directement :
tous passent par get_connection() ou par les fonctions execute_*
definies ici. Cela garantit un comportement homogene (cles etrangeres
actives, formats de date, gestion des erreurs) et facilite la migration
future vers un autre moteur (PostgreSQL, par exemple) si la plateforme
doit etre deployee a plus grande echelle.

Nouveau en V2 : migration automatique et non destructive des bases
V1 deja en production (voir _migrer_schema_v1_vers_v2), et dossier de
stockage des photos de profil (PHOTOS_DIR).

Nouveau en V3 : migration V2 -> V3 (_migrer_schema_v2_vers_v3, voir
audit-isabee-v2.md : corbeille, paiement Mobile Money), dossier de
stockage des preuves de paiement (PREUVES_DIR), et suivi des versions
de schema appliquees (table schema_versions, voir
_enregistrer_version et database/migrations/).
"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "source_isabee.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"
DOCUMENTS_DIR = BASE_DIR / "data" / "documents"
PHOTOS_DIR = BASE_DIR / "data" / "photos"
PREUVES_DIR = BASE_DIR / "data" / "preuves_paiement"
COUVERTURES_DIR = BASE_DIR / "data" / "couvertures"
BACKUPS_DIR = BASE_DIR / "data" / "sauvegardes"


def _ensure_directories() -> None:
    """Cree les dossiers de donnees s'ils n'existent pas encore."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    PREUVES_DIR.mkdir(parents=True, exist_ok=True)
    COUVERTURES_DIR.mkdir(parents=True, exist_ok=True)
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_connection():
    """
    Fournit une connexion SQLite configuree correctement.

    A utiliser systematiquement avec un bloc 'with' :

        with get_connection() as conn:
            conn.execute(...)

    Le commit est realise automatiquement a la sortie du bloc si aucune
    exception n'a ete levee ; en cas d'erreur, un rollback est effectue.
    """
    _ensure_directories()
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _colonnes_existantes(conn: sqlite3.Connection, table: str) -> set[str]:
    """
    Liste les colonnes actuelles d'une table. Utilise un acces
    positionnel (ligne[1]) plutot que par nom de colonne, afin de
    fonctionner quelle que soit la configuration de row_factory sur
    la connexion recue en parametre (cette fonction ne presuppose pas
    que l'appelant a regle conn.row_factory = sqlite3.Row).
    """
    return {ligne[1] for ligne in conn.execute(f"PRAGMA table_info({table})")}


def _migrer_schema_v1_vers_v2(conn: sqlite3.Connection) -> None:
    """
    Ajoute aux bases V1 deja existantes les colonnes introduites en V2,
    sans aucune perte de donnees. Idempotent : ne fait rien si les
    colonnes sont deja presentes, que ce soit parce que la base vient
    d'etre creee a neuf via schema.sql, ou parce que cette migration a
    deja ete executee a un demarrage precedent.

    Limite assumee : SQLite ne permet pas d'ajouter une contrainte
    CHECK a une table existante sans la reconstruire entierement.
    Les nouvelles contraintes definies dans schema.sql (cycle,
    type_acces...) s'appliquent donc pleinement aux bases creees a
    neuf, mais pas retroactivement aux lignes d'une base V1 migree.
    La validation cote application (models.py, formulaires de saisie)
    reste donc la garantie principale pour ces bases migrees.
    """
    colonnes_a_ajouter: dict[str, list[tuple[str, str]]] = {
        "users": [
            ("photo", "TEXT"),
            ("theme", "TEXT NOT NULL DEFAULT 'clair'"),
            ("langue", "TEXT NOT NULL DEFAULT 'fr'"),
        ],
        "subjects": [
            ("type_acces", "TEXT NOT NULL DEFAULT 'gratuit'"),
            ("prix", "INTEGER NOT NULL DEFAULT 0"),
            ("mode_paiement", "TEXT NOT NULL DEFAULT 'presentiel'"),
        ],
    }
    tables_existantes = {
        ligne[0] for ligne in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    for table, colonnes in colonnes_a_ajouter.items():
        if table not in tables_existantes:
            continue
        existantes = _colonnes_existantes(conn, table)
        for nom_colonne, definition in colonnes:
            if nom_colonne not in existantes:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {nom_colonne} {definition}")

    # Cet index porte sur une colonne qui n'existe pas forcement encore
    # au moment ou schema.sql s'execute sur une base V1 preexistante
    # (CREATE TABLE IF NOT EXISTS ne modifie pas une table deja
    # presente). Il est donc cree ici, une fois la colonne garantie
    # presente ci-dessus, plutot que dans schema.sql. Idempotent et
    # sans effet sur une base fraichement creee, ou la colonne existe
    # deja et l'index est simplement ignore (IF NOT EXISTS).
    if "subjects" in tables_existantes:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_subjects_type_acces ON subjects(type_acces)")


def _migrer_schema_v2_vers_v3(conn: sqlite3.Connection) -> None:
    """
    Ajoute aux bases V2 deja existantes les colonnes introduites en V3
    (corbeille, paiement Mobile Money), sans aucune perte de donnees.
    Suit exactement le meme principe que _migrer_schema_v1_vers_v2 :
    idempotent, et n'agit que sur les colonnes manquantes des tables
    deja presentes.

    Les nouvelles tables de la V3 (payment_methods,
    password_reset_tokens, schema_versions) n'ont pas besoin de ce
    traitement : elles sont creees par schema.sql via
    CREATE TABLE IF NOT EXISTS, deja naturellement idempotent et sans
    risque sur une base existante.
    """
    colonnes_a_ajouter: dict[str, list[tuple[str, str]]] = {
        "subjects": [
            ("supprime", "INTEGER NOT NULL DEFAULT 0"),
            ("supprime_le", "TEXT"),
            ("supprime_par", "INTEGER"),
        ],
        "payments": [
            ("operateur", "TEXT"),
            ("capture_preuve", "TEXT"),
        ],
    }
    tables_existantes = {
        ligne[0] for ligne in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    for table, colonnes in colonnes_a_ajouter.items():
        if table not in tables_existantes:
            continue
        existantes = _colonnes_existantes(conn, table)
        for nom_colonne, definition in colonnes:
            if nom_colonne not in existantes:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {nom_colonne} {definition}")

    if "subjects" in tables_existantes:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_subjects_supprime ON subjects(supprime)")


def _enregistrer_version(conn: sqlite3.Connection, version: str, description: str) -> None:
    """
    Enregistre dans schema_versions qu'une migration a ete appliquee,
    sans erreur si elle l'avait deja ete a un demarrage precedent
    (INSERT OR IGNORE, la colonne version est UNIQUE). A appeler une
    fois la migration Python correspondante executee avec succes.
    """
    conn.execute(
        "INSERT OR IGNORE INTO schema_versions (version, description) VALUES (?, ?)",
        (version, description),
    )


def _migrer_v3_phase2(conn: sqlite3.Connection) -> None:
    """
    Deuxieme vague d'ajouts V3 (voir audit-isabee-v2.md) : biographie
    de profil. Suit le meme principe idempotent que les migrations
    precedentes -- ALTER TABLE ADD COLUMN uniquement si la colonne
    n'existe pas deja. Les tables tags/document_tags n'ont pas besoin
    de ce traitement (CREATE TABLE IF NOT EXISTS dans schema.sql,
    deja naturellement idempotent).
    """
    if "users" in {ligne[0] for ligne in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
        if "bio" not in _colonnes_existantes(conn, "users"):
            conn.execute("ALTER TABLE users ADD COLUMN bio TEXT")


def _migrer_schema_v3_vers_v4(conn: sqlite3.Connection) -> None:
    """
    Ajoute aux bases V3 deja existantes la colonne introduite en V4
    (visuel de couverture optionnel sur un document), sans aucune perte
    de donnees. Suit exactement le meme principe idempotent que les
    migrations precedentes.

    La nouvelle table de la V4 (consultations) n'a pas besoin de ce
    traitement : elle est creee par schema.sql via
    CREATE TABLE IF NOT EXISTS, deja naturellement idempotent et sans
    risque sur une base existante.
    """
    tables_existantes = {
        ligne[0] for ligne in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if "subjects" in tables_existantes:
        if "image_couverture" not in _colonnes_existantes(conn, "subjects"):
            conn.execute("ALTER TABLE subjects ADD COLUMN image_couverture TEXT")


RECHERCHE_PLEIN_TEXTE_DISPONIBLE = False


def _activer_recherche_plein_texte(conn: sqlite3.Connection) -> bool:
    """
    Active la recherche plein texte (SQLite FTS5) sur les documents,
    si le module FTS5 est compile dans cette installation de SQLite --
    ce qui n'est pas garanti sur 100% des systemes. En cas
    d'indisponibilite, echoue silencieusement (capture l'exception,
    journalise une seule fois) : la recherche reste alors assuree par
    l'ancienne methode LIKE, exactement comme avant cette
    fonctionnalite (voir archive_manager._construire_conditions). Ne
    fait jamais echouer le demarrage de l'application.

    Retourne True si la recherche plein texte est active, False sinon.
    """
    global RECHERCHE_PLEIN_TEXTE_DISPONIBLE
    try:
        table_existait_deja = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name = 'subjects_fts'"
        ).fetchone() is not None

        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS subjects_fts USING fts5("
            "titre, description, content='subjects', content_rowid='id')"
        )
        conn.execute(
            "CREATE TRIGGER IF NOT EXISTS subjects_fts_ai AFTER INSERT ON subjects BEGIN "
            "INSERT INTO subjects_fts(rowid, titre, description) VALUES (new.id, new.titre, new.description); "
            "END"
        )
        conn.execute(
            "CREATE TRIGGER IF NOT EXISTS subjects_fts_ad AFTER DELETE ON subjects BEGIN "
            "INSERT INTO subjects_fts(subjects_fts, rowid, titre, description) "
            "VALUES ('delete', old.id, old.titre, old.description); "
            "END"
        )
        conn.execute(
            "CREATE TRIGGER IF NOT EXISTS subjects_fts_au AFTER UPDATE ON subjects BEGIN "
            "INSERT INTO subjects_fts(subjects_fts, rowid, titre, description) "
            "VALUES ('delete', old.id, old.titre, old.description); "
            "INSERT INTO subjects_fts(rowid, titre, description) VALUES (new.id, new.titre, new.description); "
            "END"
        )

        if not table_existait_deja:
            # Premiere creation : indexer les documents deja presents.
            # Ne se reproduit jamais ensuite (les triggers ci-dessus
            # prennent le relais pour tout INSERT/UPDATE/DELETE futur).
            conn.execute(
                "INSERT INTO subjects_fts(rowid, titre, description) "
                "SELECT id, titre, description FROM subjects"
            )

        RECHERCHE_PLEIN_TEXTE_DISPONIBLE = True
        return True
    except sqlite3.OperationalError:
        RECHERCHE_PLEIN_TEXTE_DISPONIBLE = False
        return False


def recherche_plein_texte_disponible() -> bool:
    """Vrai si la recherche plein texte (FTS5) est active sur cette installation."""
    return RECHERCHE_PLEIN_TEXTE_DISPONIBLE


def initialiser_base() -> None:
    """
    Cree les tables si elles n'existent pas, a partir de schema.sql,
    puis applique les migrations V1 -> V2 puis V2 -> V3 sur les
    tables deja existantes. Doit etre appelee une fois au demarrage
    de l'application (app.py).
    """
    _ensure_directories()
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with get_connection() as conn:
        conn.executescript(schema_sql)
        _migrer_schema_v1_vers_v2(conn)
        _migrer_schema_v2_vers_v3(conn)
        _migrer_v3_phase2(conn)
        _migrer_schema_v3_vers_v4(conn)
        _activer_recherche_plein_texte(conn)
        _enregistrer_version(
            conn, "001_initial",
            "Schema de reference V2 (point de depart du suivi de versions). "
            "Voir database/migrations/001_initial.sql.",
        )
        _enregistrer_version(
            conn, "002_corbeille",
            "Ajout de la corbeille (suppression reversible des documents). "
            "Voir database/migrations/002_corbeille.sql.",
        )
        _enregistrer_version(
            conn, "003_paiement_mobile_money",
            "Ajout des moyens de paiement Mobile Money configurables. "
            "Voir database/migrations/003_paiement_mobile_money.sql.",
        )
        _enregistrer_version(
            conn, "004_mot_de_passe_oublie",
            "Ajout de la reinitialisation de mot de passe par jeton. "
            "Voir database/migrations/004_mot_de_passe_oublie.sql.",
        )
        _enregistrer_version(
            conn, "005_profil_bio",
            "Ajout de la biographie de profil. Voir database/migrations/005_profil_bio.sql.",
        )
        _enregistrer_version(
            conn, "006_tags",
            "Ajout du systeme de tags sur les documents. Voir database/migrations/006_tags.sql.",
        )
        _enregistrer_version(
            conn, "007_recherche_plein_texte",
            "Activation de la recherche plein texte (FTS5) si disponible, repli "
            "automatique sur la recherche existante sinon. "
            "Voir database/migrations/007_recherche_plein_texte.sql.",
        )
        _enregistrer_version(
            conn, "008_connexion_persistante",
            "Ajout de la connexion persistante par cookie (se souvenir de moi). "
            "Voir database/migrations/008_connexion_persistante.sql.",
        )
        _enregistrer_version(
            conn, "009_couverture_et_historique",
            "Ajout du visuel de couverture optionnel sur un document et de "
            "l'historique des documents recemment consultes. "
            "Voir database/migrations/009_couverture_et_historique.sql.",
        )


def executer(requete: str, parametres: tuple = ()) -> int:
    """
    Execute une requete de modification (INSERT/UPDATE/DELETE).
    Retourne l'id de la derniere ligne inseree (utile pour les INSERT).
    """
    with get_connection() as conn:
        curseur = conn.execute(requete, parametres)
        return curseur.lastrowid


def recuperer_un(requete: str, parametres: tuple = ()) -> sqlite3.Row | None:
    """Execute une requete SELECT et retourne une seule ligne (ou None)."""
    with get_connection() as conn:
        return conn.execute(requete, parametres).fetchone()


def recuperer_tous(requete: str, parametres: tuple = ()) -> list[sqlite3.Row]:
    """Execute une requete SELECT et retourne toutes les lignes."""
    with get_connection() as conn:
        return conn.execute(requete, parametres).fetchall()
