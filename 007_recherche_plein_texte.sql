-- =====================================================================
-- Migration 007_recherche_plein_texte
-- =====================================================================
-- Documentation de la migration appliquee par
-- database._activer_recherche_plein_texte(). Ce fichier n'est pas
-- execute automatiquement (voir la note dans 001_initial.sql) -- et
-- pour cette migration en particulier, il ne le pourrait pas de toute
-- facon sans risque : voir l'avertissement ci-dessous.
--
-- Objectif : recherche plein texte sur le titre et la description des
-- documents (table virtuelle FTS5 "subjects_fts", synchronisee par
-- triggers a chaque insertion/modification/suppression). Repli
-- automatique et silencieux sur l'ancienne recherche LIKE si le
-- module FTS5 n'est pas compile dans l'installation SQLite cible (non
-- garanti sur 100% des systemes) -- voir
-- archive_manager._construire_conditions.
-- =====================================================================

CREATE VIRTUAL TABLE IF NOT EXISTS subjects_fts USING fts5(
    titre, description, content='subjects', content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS subjects_fts_ai AFTER INSERT ON subjects BEGIN
    INSERT INTO subjects_fts(rowid, titre, description) VALUES (new.id, new.titre, new.description);
END;

CREATE TRIGGER IF NOT EXISTS subjects_fts_ad AFTER DELETE ON subjects BEGIN
    INSERT INTO subjects_fts(subjects_fts, rowid, titre, description)
    VALUES ('delete', old.id, old.titre, old.description);
END;

CREATE TRIGGER IF NOT EXISTS subjects_fts_au AFTER UPDATE ON subjects BEGIN
    INSERT INTO subjects_fts(subjects_fts, rowid, titre, description)
    VALUES ('delete', old.id, old.titre, old.description);
    INSERT INTO subjects_fts(rowid, titre, description) VALUES (new.id, new.titre, new.description);
END;

-- Indexation initiale des documents deja presents au moment de la
-- toute premiere activation (une seule fois ; les triggers ci-dessus
-- prennent le relais ensuite) :
-- INSERT INTO subjects_fts(rowid, titre, description) SELECT id, titre, description FROM subjects;
