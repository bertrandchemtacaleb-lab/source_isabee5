-- =====================================================================
-- Migration 006_tags
-- =====================================================================
-- Documentation de la migration appliquee par schema.sql (tables
-- entierement nouvelles : CREATE TABLE IF NOT EXISTS est deja
-- naturellement idempotent, rien a faire cote
-- _migrer_v3_phase2). Ce fichier n'est pas execute automatiquement
-- (voir la note dans 001_initial.sql).
--
-- Objectif : systeme de tags libres sur les documents, pour un
-- filtrage plus fin que le seul cycle/filiere/niveau/type (voir
-- admin.page_gestion_tags et archive_manager.py).
-- =====================================================================

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

CREATE INDEX IF NOT EXISTS idx_document_tags_tag ON document_tags(tag_id);
