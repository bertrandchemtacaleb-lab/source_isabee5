-- =====================================================================
-- Migration 008_connexion_persistante
-- =====================================================================
-- Documentation de la migration appliquee par schema.sql (table
-- entierement nouvelle : CREATE TABLE IF NOT EXISTS est deja
-- naturellement idempotent). Ce fichier n'est pas execute
-- automatiquement (voir la note dans 001_initial.sql).
--
-- Objectif : connexion persistante par cookie ("se souvenir de moi"),
-- pour qu'un simple rafraichissement de page ne redemande jamais de
-- connexion, et que la session survive jusqu'a 30 jours si demande
-- (voir auth.py et app.page_connexion).
-- =====================================================================

CREATE TABLE IF NOT EXISTS remember_tokens (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL,
    jeton_hash          TEXT    NOT NULL UNIQUE,
    date_creation       TEXT    NOT NULL DEFAULT (datetime('now')),
    date_expiration     TEXT    NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_remember_tokens_user ON remember_tokens(user_id);

-- Note de securite : seul le hachage SHA-256 du jeton est stocke,
-- jamais le jeton en clair, sur le meme principe que les mots de
-- passe et les jetons de reinitialisation (voir password_reset_tokens,
-- migration 004).
