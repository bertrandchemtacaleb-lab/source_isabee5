-- =====================================================================
-- SOURCE ISABEE - Schema de base de donnees - VERSION 3
-- SGBD : SQLite 3
--
-- Changements V1 -> V2 :
--   - users        : ajout photo, theme, langue (profil et preferences)
--   - subjects      : ajout type_acces, prix, mode_paiement ; cycle et
--                      filiere desormais contraints par CHECK
--   - payments      : nouvelle table (monetisation, paiement presentiel)
--   - messages      : nouvelle table (messagerie interne)
--   - announcements : nouvelle table (annonces administratives)
--   - notifications : nouvelle table (notifications utilisateur)
--
-- Changements V2 -> V3 (voir audit-isabee-v2.md) :
--   - subjects             : ajout supprime, supprime_le, supprime_par
--                             (corbeille, suppression reversible)
--   - payments             : ajout operateur, capture_preuve
--                             (paiement Mobile Money, en complement du
--                             paiement en presentiel, jamais en
--                             remplacement)
--   - payment_methods      : nouvelle table (moyens de paiement Mobile
--                             Money configurables depuis l'interface,
--                             jamais codes en dur)
--   - password_reset_tokens: nouvelle table (mot de passe oublie)
--   - schema_versions      : nouvelle table (suivi des migrations,
--                             voir database/migrations/)
--
-- Changements V3 -> V4 (commercialisation, voir audit-isabee-v3.md) :
--   - subjects             : ajout image_couverture (visuel optionnel
--                             affiche dans la bibliotheque, distinct du
--                             fichier PDF lui-meme)
--   - consultations        : nouvelle table (historique des documents
--                             recemment consultes par un utilisateur,
--                             voir archive_manager.enregistrer_consultation)
--
-- Important : ce fichier definit le schema d'une base CREEE A NEUF.
-- Pour une base V1 ou V2 deja en production, ces CREATE TABLE
-- IF NOT EXISTS ne modifient pas les tables existantes. La migration
-- d'une base existante est traitee a part dans database.py (fonctions
-- _migrer_schema_v1_vers_v2 et _migrer_schema_v2_vers_v3), qui ajoutent
-- les colonnes manquantes avec ALTER TABLE sans perte de donnees.
-- =====================================================================

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- Table : users
-- Comptes de la plateforme (administrateur, enseignant, etudiant,
-- contributeur). Le mot de passe n'est jamais stocke en clair.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    matricule           TEXT    NOT NULL UNIQUE,
    nom                 TEXT    NOT NULL,
    prenom              TEXT    NOT NULL,
    email               TEXT    NOT NULL UNIQUE,
    filiere             TEXT,
    niveau              TEXT,
    role                TEXT    NOT NULL CHECK (role IN ('administrateur', 'enseignant', 'etudiant', 'contributeur')),
    mot_de_passe_hash   TEXT    NOT NULL,
    sel                 TEXT    NOT NULL,
    statut              TEXT    NOT NULL DEFAULT 'actif' CHECK (statut IN ('actif', 'suspendu')),
    photo               TEXT,
    theme               TEXT    NOT NULL DEFAULT 'clair' CHECK (theme IN ('clair', 'sombre')),
    langue              TEXT    NOT NULL DEFAULT 'fr' CHECK (langue IN ('fr', 'en')),
    date_inscription    TEXT    NOT NULL DEFAULT (datetime('now')),
    derniere_connexion  TEXT,
    bio                 TEXT
);

-- ---------------------------------------------------------------------
-- Table : subjects
-- Documents pedagogiques : epreuves, sujets de controle continu,
-- examens, corriges, travaux pratiques et supports de cours.
--
-- type_acces / prix / mode_paiement decrivent la regle d'acces au
-- document (configuree par celui qui le depose). Le suivi du
-- paiement de CHAQUE utilisateur pour CE document est, lui, stocke
-- dans la table payments : un document payant n'a pas un statut de
-- paiement unique, chaque etudiant a le sien.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS subjects (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    titre               TEXT    NOT NULL,
    description         TEXT,
    type_document       TEXT    NOT NULL CHECK (type_document IN ('examen', 'controle_continu', 'corrige', 'travaux_pratiques', 'support_cours', 'autre')),
    cycle               TEXT    NOT NULL CHECK (cycle IN ('Licence', 'Ingenieur', 'Master')),
    filiere             TEXT    NOT NULL,
    niveau              TEXT    NOT NULL,
    annee_academique    TEXT    NOT NULL,
    enseignant_id       INTEGER,
    chemin_fichier      TEXT    NOT NULL,
    taille_fichier_ko   INTEGER,
    type_acces          TEXT    NOT NULL DEFAULT 'gratuit' CHECK (type_acces IN ('gratuit', 'payant')),
    prix                INTEGER NOT NULL DEFAULT 0,
    mode_paiement       TEXT    NOT NULL DEFAULT 'presentiel' CHECK (mode_paiement IN ('presentiel')),
    statut              TEXT    NOT NULL DEFAULT 'en_attente' CHECK (statut IN ('en_attente', 'valide', 'rejete')),
    ajoute_par          INTEGER NOT NULL,
    valide_par          INTEGER,
    date_ajout          TEXT    NOT NULL DEFAULT (datetime('now')),
    date_validation     TEXT,
    motif_rejet         TEXT,
    supprime            INTEGER NOT NULL DEFAULT 0 CHECK (supprime IN (0, 1)),
    supprime_le         TEXT,
    supprime_par        INTEGER,
    image_couverture    TEXT,
    FOREIGN KEY (enseignant_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (ajoute_par)    REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (valide_par)    REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (supprime_par)  REFERENCES users(id) ON DELETE SET NULL
);

-- ---------------------------------------------------------------------
-- Table : downloads
-- Historique des telechargements, utilise pour les statistiques.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS downloads (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id         INTEGER NOT NULL,
    user_id             INTEGER NOT NULL,
    date_telechargement TEXT    NOT NULL DEFAULT (datetime('now')),
    adresse_ip          TEXT,
    FOREIGN KEY (document_id) REFERENCES subjects(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id)     REFERENCES users(id)    ON DELETE CASCADE
);

-- ---------------------------------------------------------------------
-- Table : favorites
-- Documents marques par un utilisateur pour un acces rapide.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS favorites (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL,
    document_id         INTEGER NOT NULL,
    date_ajout          TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (user_id, document_id),
    FOREIGN KEY (user_id)     REFERENCES users(id)    ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES subjects(id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------
-- Table : comments
-- Remarques et avis publics deposes sur un document, soumis a
-- moderation administrative (parametre moderation_commentaires).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS comments (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id         INTEGER NOT NULL,
    user_id             INTEGER NOT NULL,
    contenu             TEXT    NOT NULL,
    statut              TEXT    NOT NULL DEFAULT 'visible' CHECK (statut IN ('visible', 'masque')),
    date_creation       TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (document_id) REFERENCES subjects(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id)     REFERENCES users(id)    ON DELETE CASCADE
);

-- ---------------------------------------------------------------------
-- Table : payments
-- Suivi des paiements de ressources payantes. Deux circuits possibles,
-- tous deux a validation manuelle par un administrateur (aucune
-- integration d'API de paiement automatisee) :
--   - presentiel : encaissement physique au service competent ;
--   - Mobile Money (operateur = 'orange_money' ou 'mtn_momo') :
--     transfert vers un numero configure dans payment_methods, avec
--     capture de la preuve de paiement jointe (capture_preuve).
-- Une ligne par couple (document, utilisateur) : un etudiant ne paie
-- un document donne qu'une seule fois.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS payments (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id         INTEGER NOT NULL,
    user_id             INTEGER NOT NULL,
    montant             INTEGER NOT NULL,
    mode_paiement       TEXT    NOT NULL DEFAULT 'presentiel' CHECK (mode_paiement IN ('presentiel')),
    operateur           TEXT    CHECK (operateur IS NULL OR operateur IN ('orange_money', 'mtn_momo')),
    capture_preuve      TEXT,
    statut_paiement     TEXT    NOT NULL DEFAULT 'en_attente' CHECK (statut_paiement IN ('en_attente', 'valide', 'refuse')),
    reference_caisse    TEXT,
    date_demande        TEXT    NOT NULL DEFAULT (datetime('now')),
    date_validation     TEXT,
    valide_par          INTEGER,
    UNIQUE (document_id, user_id),
    FOREIGN KEY (document_id) REFERENCES subjects(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id)     REFERENCES users(id)    ON DELETE CASCADE,
    FOREIGN KEY (valide_par)  REFERENCES users(id)    ON DELETE SET NULL
);

-- ---------------------------------------------------------------------
-- Table : messages
-- Messagerie interne privee entre deux utilisateurs de la plateforme.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS messages (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    expediteur_id       INTEGER NOT NULL,
    destinataire_id     INTEGER NOT NULL,
    contenu             TEXT    NOT NULL,
    lu                  INTEGER NOT NULL DEFAULT 0 CHECK (lu IN (0, 1)),
    date_envoi          TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (expediteur_id)   REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (destinataire_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------
-- Table : announcements
-- Annonces administratives et informations publiques, diffusees a
-- tous les utilisateurs ou a un role precis.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS announcements (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    titre               TEXT    NOT NULL,
    contenu             TEXT    NOT NULL,
    role_cible          TEXT    CHECK (role_cible IS NULL OR role_cible IN ('administrateur', 'enseignant', 'etudiant', 'contributeur')),
    publie_par          INTEGER NOT NULL,
    date_publication    TEXT    NOT NULL DEFAULT (datetime('now')),
    date_expiration     TEXT,
    FOREIGN KEY (publie_par) REFERENCES users(id) ON DELETE SET NULL
);

-- ---------------------------------------------------------------------
-- Table : notifications
-- Notifications individuelles (validation de document, paiement
-- valide, nouvelle annonce, nouveau message...).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notifications (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL,
    contenu             TEXT    NOT NULL,
    type_notification   TEXT    NOT NULL DEFAULT 'info' CHECK (type_notification IN ('info', 'validation', 'paiement', 'annonce', 'message', 'systeme')),
    lu                  INTEGER NOT NULL DEFAULT 0 CHECK (lu IN (0, 1)),
    document_id         INTEGER,
    date_creation       TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id)     REFERENCES users(id)    ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES subjects(id) ON DELETE SET NULL
);

-- ---------------------------------------------------------------------
-- Table : logs
-- Journal systeme : trace toute action sensible (connexion, ajout,
-- suppression, validation, paiement, modification de parametres...).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS logs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    date_heure          TEXT    NOT NULL DEFAULT (datetime('now')),
    user_id             INTEGER,
    matricule           TEXT,
    action              TEXT    NOT NULL,
    adresse_ip          TEXT,
    resultat            TEXT    NOT NULL CHECK (resultat IN ('succes', 'echec')),
    details             TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- ---------------------------------------------------------------------
-- Table : settings
-- Parametres globaux de la plateforme, modifiables par un
-- administrateur uniquement.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS settings (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    cle                 TEXT    NOT NULL UNIQUE,
    valeur              TEXT,
    description         TEXT,
    modifie_par         INTEGER,
    date_modification   TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (modifie_par) REFERENCES users(id) ON DELETE SET NULL
);

-- ---------------------------------------------------------------------
-- Table : payment_methods   (nouveau en V3)
-- Moyens de paiement Mobile Money affiches aux etudiants (Orange
-- Money, MTN MoMo...). Entierement configurable depuis l'interface
-- d'administration : aucun numero ni titulaire n'est code en dur dans
-- l'application, conformement au cahier des charges.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS payment_methods (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    nom_affiche         TEXT    NOT NULL,
    operateur           TEXT    NOT NULL CHECK (operateur IN ('orange_money', 'mtn_momo', 'autre')),
    titulaire           TEXT    NOT NULL,
    numero              TEXT    NOT NULL,
    actif               INTEGER NOT NULL DEFAULT 1 CHECK (actif IN (0, 1)),
    ordre_affichage     INTEGER NOT NULL DEFAULT 0,
    modifie_par         INTEGER,
    date_modification   TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (modifie_par) REFERENCES users(id) ON DELETE SET NULL
);

-- ---------------------------------------------------------------------
-- Table : password_reset_tokens   (nouveau en V3)
-- Jetons de reinitialisation de mot de passe ("mot de passe oublie").
-- Seul le hachage SHA-256 du jeton est stocke, jamais le jeton en
-- clair (meme principe que les mots de passe eux-memes) ; chaque
-- jeton est a usage unique et expire apres une duree limitee (voir
-- auth.DUREE_VALIDITE_JETON_RESET_MINUTES).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL,
    jeton_hash          TEXT    NOT NULL,
    date_creation       TEXT    NOT NULL DEFAULT (datetime('now')),
    date_expiration     TEXT    NOT NULL,
    utilise             INTEGER NOT NULL DEFAULT 0 CHECK (utilise IN (0, 1)),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------
-- Table : tags / document_tags   (nouveau en V3, deuxieme vague)
-- Systeme de tags libres sur les documents, pour un filtrage plus fin
-- que le seul cycle/filiere/niveau/type (voir
-- admin.page_gestion_tags et archive_manager.py).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tags (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    nom     TEXT NOT NULL UNIQUE,
    couleur TEXT NOT NULL DEFAULT '#2563EB'
);

CREATE TABLE IF NOT EXISTS document_tags (
    document_id INTEGER NOT NULL,
    tag_id      INTEGER NOT NULL,
    PRIMARY KEY (document_id, tag_id),
    FOREIGN KEY (document_id) REFERENCES subjects(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id)      REFERENCES tags(id)     ON DELETE CASCADE
);

-- Note sur la recherche plein texte (subjects_fts, FTS5) : elle n'est
-- PAS definie ici. SQLite n'est pas garanti d'etre compile avec le
-- module FTS5 sur tous les systemes ; si elle figurait dans ce fichier,
-- une absence de FTS5 ferait echouer tout l'executescript de
-- schema.sql, donc TOUT le demarrage de l'application. Elle est donc
-- creee a part, dans database.py (_activer_recherche_plein_texte),
-- avec un repli automatique et silencieux sur la recherche LIKE
-- existante si FTS5 n'est pas disponible. Voir audit-isabee-v2.md.

-- ---------------------------------------------------------------------
-- Table : remember_tokens   (nouveau en V3, troisieme vague)
-- Jetons de connexion persistante ("rester connecte" / "se souvenir
-- de moi"), stockes cote navigateur sous forme de cookie (voir
-- auth.generer_jeton_session). Permet a un simple rafraichissement de
-- page de ne jamais redemander de connexion, et, si "se souvenir de
-- moi" est coche, de rester connecte jusqu'a 30 jours meme apres
-- fermeture du navigateur. Seul le hachage SHA-256 du jeton est
-- stocke, jamais le jeton en clair, sur le meme principe que les
-- mots de passe et les jetons de reinitialisation. La deconnexion
-- explicite supprime la ligne correspondante (voir
-- auth.revoquer_jeton_session) : un jeton vole ne peut pas etre
-- revoque a distance autrement qu'en supprimant manuellement ses
-- lignes en base, ce qui est documente comme limite connue.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS remember_tokens (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL,
    jeton_hash          TEXT    NOT NULL UNIQUE,
    date_creation       TEXT    NOT NULL DEFAULT (datetime('now')),
    date_expiration     TEXT    NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_remember_tokens_user ON remember_tokens(user_id);

-- ---------------------------------------------------------------------
-- Table : consultations   (nouveau en V4)
-- Historique des documents recemment consultes par un utilisateur
-- (page "Bibliotheque", ouverture de la fiche d'un document), distinct
-- des telechargements (table downloads) : consulter un document ne
-- signifie pas forcement le telecharger. Une ligne par consultation ;
-- l'affichage (page_historique) ne retient que les plus recentes par
-- document pour un meme utilisateur, sans qu'il soit necessaire de
-- le garantir au niveau du schema.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS consultations (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id         INTEGER NOT NULL,
    user_id             INTEGER NOT NULL,
    date_consultation   TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (document_id) REFERENCES subjects(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id)     REFERENCES users(id)    ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_consultations_user ON consultations(user_id, date_consultation);
CREATE INDEX IF NOT EXISTS idx_consultations_doc  ON consultations(document_id);

-- ---------------------------------------------------------------------
-- Table : schema_versions   (nouveau en V3)
-- Trace les migrations appliquees a cette base. Chaque migration est
-- appliquee par une fonction Python idempotente (voir database.py) ;
-- le fichier .sql correspondant sous database/migrations/ sert de
-- documentation lisible de ce que fait cette fonction, et n'est pas
-- execute directement (SQLite ne permet pas d'ajouter une colonne de
-- maniere idempotente via un script SQL brut : ALTER TABLE ADD COLUMN
-- echoue si la colonne existe deja).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_versions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    version             TEXT    NOT NULL UNIQUE,
    description         TEXT,
    date_application    TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------
-- Index utiles aux recherches multicriteres et aux statistiques
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_subjects_filiere      ON subjects(filiere);
CREATE INDEX IF NOT EXISTS idx_subjects_cycle         ON subjects(cycle);
CREATE INDEX IF NOT EXISTS idx_subjects_niveau        ON subjects(niveau);
CREATE INDEX IF NOT EXISTS idx_subjects_annee         ON subjects(annee_academique);
CREATE INDEX IF NOT EXISTS idx_subjects_type          ON subjects(type_document);
CREATE INDEX IF NOT EXISTS idx_subjects_statut        ON subjects(statut);
CREATE INDEX IF NOT EXISTS idx_users_role             ON users(role);
CREATE INDEX IF NOT EXISTS idx_logs_date              ON logs(date_heure);
CREATE INDEX IF NOT EXISTS idx_payments_statut        ON payments(statut_paiement);
CREATE INDEX IF NOT EXISTS idx_messages_destinataire  ON messages(destinataire_id, lu);
CREATE INDEX IF NOT EXISTS idx_notifications_user     ON notifications(user_id, lu);
CREATE INDEX IF NOT EXISTS idx_announcements_role     ON announcements(role_cible);
CREATE INDEX IF NOT EXISTS idx_payment_methods_actif  ON payment_methods(actif);
CREATE INDEX IF NOT EXISTS idx_password_reset_user    ON password_reset_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_document_tags_tag       ON document_tags(tag_id);
