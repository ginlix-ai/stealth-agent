-- Migration: 001_add_thread_title
-- Description: Add title column to conversation_thread table
-- Date: 2025-02-05

ALTER TABLE conversation_thread ADD COLUMN IF NOT EXISTS title VARCHAR(255)
