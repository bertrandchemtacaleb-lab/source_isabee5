-- =====================================================================
-- Migration 009_couverture_et_historique
-- =====================================================================
-- Documentation de la migration appliquee par schema.sql et
-- database._migrer_schema_v3_vers_v4 (voir database.py). Ce fichier
-- n'est pas execute automatiquement (voir la note dans 001_initial.sql) :
-- SQLite ne permet pas d'ajouter une colonne de maniere idempotente via
-- un script SQL brut (ALTER TABLE ADD COLUMN echoue si la colonne
-- existe deja), donc la migration reelle est en Python.
--
-- Objectif : ameliorer la presentation visuelle de la bibliotheque
-- (image de couverture optionnelle par document, affichee en plus du
-- fichier PDF lui-meme) et offrir une page "Documents recemment
-- consultes" (voir archive_manager.enregistrer_consultation et
-- app.page_historique).
-- =====================================================================

-- Ajout sur une base existante (idempotent en Python, voir
-- _migrer_schema_v3_vers_v4) :
ALTER TABLE subjects ADD COLUMN image_couverture TEXT;

-- Nouvelle table (CREATE TABLE IF NOT EXISTS deja idempotent) :
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

-- Note : aucune donnee existante n'est modifiee ni supprimee. Les
-- documents deja en base ont simplement image_couverture = NULL
-- (aucun visuel de couverture), ce que l'affichage doit traiter comme
-- un cas normal (pas d'erreur, simple absence d'image).
