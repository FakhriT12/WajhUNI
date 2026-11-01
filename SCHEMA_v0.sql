-- =============================================================
-- WajhUni v0 — PostgreSQL Database Schema
-- PostgreSQL 16+
-- =============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- =============================================================
-- UNIVERSITIES
-- Seeded manually by admin. One row per university.
-- =============================================================
CREATE TABLE universities (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name_ar             VARCHAR(255) NOT NULL,              -- Arabic name
    name_fr             VARCHAR(255) NOT NULL,              -- French name
    acronym             VARCHAR(20)  NOT NULL UNIQUE,       -- e.g. TBS, ESEN, IHEC
    type                VARCHAR(50)  NOT NULL               -- 'public', 'private', 'grandes_ecoles'
                        CHECK (type IN ('public', 'private', 'grandes_ecoles')),
    governorate         VARCHAR(100) NOT NULL DEFAULT 'Tunis',
    neighborhood        VARCHAR(100),                       -- e.g. 'El Mourouj', 'Carthage'
    address             TEXT,
    latitude            DECIMAL(10, 7),
    longitude           DECIMAL(10, 7),
    nearest_transport   TEXT,                              -- e.g. 'Metro line 1 — Mourouj stop, 8 min walk'
    website_url         VARCHAR(500),
    description         TEXT,
    is_active           BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- =============================================================
-- EMAIL DOMAINS
-- Maps email domains to universities. Used at registration to
-- auto-assign university_id and validate student status.
-- =============================================================
CREATE TABLE email_domains (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    university_id   UUID NOT NULL REFERENCES universities(id) ON DELETE CASCADE,
    domain          VARCHAR(255) NOT NULL UNIQUE,          -- e.g. 'tbs.u-tunis.tn'
    is_active       BOOLEAN NOT NULL DEFAULT true
);

-- =============================================================
-- USERS
-- All platform users. Role determines access level.
-- university_id is auto-assigned from email domain at registration.
-- =============================================================
CREATE TABLE users (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name               VARCHAR(255) NOT NULL,
    email                   VARCHAR(255) NOT NULL UNIQUE,
    password_hash           VARCHAR(255) NOT NULL,
    role                    VARCHAR(20)  NOT NULL DEFAULT 'student'
                            CHECK (role IN ('student', 'admin')),
    verification_status     VARCHAR(20)  NOT NULL DEFAULT 'pending'
                            CHECK (verification_status IN ('pending', 'verified', 'suspended')),
    university_id           UUID REFERENCES universities(id) ON DELETE SET NULL,
    profile_picture_url     VARCHAR(500),
    created_at              TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_login              TIMESTAMP WITH TIME ZONE
);

-- =============================================================
-- EMAIL VERIFICATION TOKENS
-- Short-lived tokens for email verification flow.
-- =============================================================
CREATE TABLE email_verification_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(255) NOT NULL UNIQUE,
    expires_at  TIMESTAMP WITH TIME ZONE NOT NULL,
    used_at     TIMESTAMP WITH TIME ZONE,                  -- NULL = not yet used
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- =============================================================
-- RATING CATEGORIES
-- Seeded at migration time. 9 fixed categories for v0.
-- display_order controls the UI ordering on the detail page.
-- =============================================================
CREATE TABLE rating_categories (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL,
    slug            VARCHAR(100) NOT NULL UNIQUE,
    headline_question TEXT NOT NULL,
    description     TEXT,
    display_order   SMALLINT NOT NULL UNIQUE,
    is_active       BOOLEAN NOT NULL DEFAULT true
);

-- =============================================================
-- RATING CATEGORY SUB-QUESTIONS
-- Defines the sub-questions for each category.
-- sub_key is used as the identifier in rating_sub_scores.
-- =============================================================
CREATE TABLE rating_sub_questions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id     UUID NOT NULL REFERENCES rating_categories(id) ON DELETE CASCADE,
    sub_key         VARCHAR(100) NOT NULL,                 -- e.g. 'campus_day', 'after_hours'
    question_text   TEXT NOT NULL,
    display_order   SMALLINT NOT NULL,
    UNIQUE (category_id, sub_key)
);

-- =============================================================
-- RATING SUBMISSIONS
-- One row per student per university. The parent record for
-- all scores and comments within a single student's review.
-- =============================================================
CREATE TABLE rating_submissions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    university_id       UUID NOT NULL REFERENCES universities(id) ON DELETE CASCADE,
    moderation_status   VARCHAR(20) NOT NULL DEFAULT 'pending'
                        CHECK (moderation_status IN ('pending', 'approved', 'flagged', 'rejected')),
    is_anonymous        BOOLEAN NOT NULL DEFAULT false,
    is_locked           BOOLEAN NOT NULL DEFAULT false,    -- true after one update used
    lock_reason         VARCHAR(50),                       -- 'update_used', 'admin_locked'
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Core business rule: one submission per student per university
    CONSTRAINT uq_user_university UNIQUE (user_id, university_id)
);

-- =============================================================
-- RATING SCORES
-- One row per category per submission.
-- Queried to compute per-category averages per university.
-- =============================================================
CREATE TABLE rating_scores (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id   UUID NOT NULL REFERENCES rating_submissions(id) ON DELETE CASCADE,
    category_id     UUID NOT NULL REFERENCES rating_categories(id) ON DELETE CASCADE,
    score           SMALLINT NOT NULL CHECK (score >= 1 AND score <= 5),

    UNIQUE (submission_id, category_id)
);

-- =============================================================
-- RATING SUB-SCORES
-- One row per sub-question per submission.
-- sub_key matches rating_sub_questions.sub_key.
-- =============================================================
CREATE TABLE rating_sub_scores (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id   UUID NOT NULL REFERENCES rating_submissions(id) ON DELETE CASCADE,
    category_id     UUID NOT NULL REFERENCES rating_categories(id) ON DELETE CASCADE,
    sub_key         VARCHAR(100) NOT NULL,
    score           SMALLINT NOT NULL CHECK (score >= 1 AND score <= 5),

    UNIQUE (submission_id, category_id, sub_key)
);

-- =============================================================
-- COMMENTS
-- One optional comment per category per submission.
-- is_featured = true means admin selected it as a testimonial.
-- =============================================================
CREATE TABLE comments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id       UUID NOT NULL REFERENCES rating_submissions(id) ON DELETE CASCADE,
    category_id         UUID NOT NULL REFERENCES rating_categories(id) ON DELETE CASCADE,
    body                TEXT NOT NULL CHECK (char_length(body) <= 280),
    comment_prompt      TEXT,                              -- The prompt shown to the student when they wrote this
    is_featured         BOOLEAN NOT NULL DEFAULT false,   -- Admin-selected testimonial
    is_anonymous        BOOLEAN NOT NULL DEFAULT false,
    moderation_status   VARCHAR(20) NOT NULL DEFAULT 'pending'
                        CHECK (moderation_status IN ('pending', 'approved', 'flagged', 'rejected')),
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    UNIQUE (submission_id, category_id)
);

-- =============================================================
-- UNIVERSITY PHOTOS
-- Admin-seeded and user-uploaded photos.
-- display_order controls gallery ordering on the detail page.
-- category is a label for future tabbed gallery (v1).
-- =============================================================
CREATE TABLE university_photos (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    university_id   UUID NOT NULL REFERENCES universities(id) ON DELETE CASCADE,
    uploaded_by     UUID REFERENCES users(id) ON DELETE SET NULL,
    url             VARCHAR(1000) NOT NULL,               -- Azure Blob Storage URL
    caption         VARCHAR(255),
    category        VARCHAR(50) NOT NULL DEFAULT 'campus'
                    CHECK (category IN ('campus', 'library', 'sports', 'canteen', 'other')),
    is_approved     BOOLEAN NOT NULL DEFAULT false,       -- Admin must approve before public display
    display_order   SMALLINT,                             -- Admin-set ordering
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- =============================================================
-- INDEXES
-- Covering the most common query patterns in v0.
-- =============================================================

-- University listing: filter by type, governorate
CREATE INDEX idx_universities_type ON universities(type);
CREATE INDEX idx_universities_governorate ON universities(governorate);
CREATE INDEX idx_universities_is_active ON universities(is_active);

-- Email domain lookup at registration (hot path)
CREATE INDEX idx_email_domains_domain ON email_domains(domain);
CREATE INDEX idx_email_domains_university ON email_domains(university_id);

-- Rating queries: aggregate scores per university per category
CREATE INDEX idx_rating_submissions_university ON rating_submissions(university_id);
CREATE INDEX idx_rating_submissions_user ON rating_submissions(user_id);
CREATE INDEX idx_rating_submissions_status ON rating_submissions(moderation_status);
CREATE INDEX idx_rating_scores_submission ON rating_scores(submission_id);
CREATE INDEX idx_rating_scores_category ON rating_scores(category_id);

-- Comment queries: featured testimonials per university
CREATE INDEX idx_comments_submission ON comments(submission_id);
CREATE INDEX idx_comments_featured ON comments(is_featured) WHERE is_featured = true;
CREATE INDEX idx_comments_status ON comments(moderation_status);

-- Photo queries: approved photos per university
CREATE INDEX idx_photos_university ON university_photos(university_id);
CREATE INDEX idx_photos_approved ON university_photos(is_approved) WHERE is_approved = true;

-- Verification token lookup (hot path during email verification)
CREATE INDEX idx_verification_tokens_hash ON email_verification_tokens(token_hash);
CREATE INDEX idx_verification_tokens_user ON email_verification_tokens(user_id);

-- =============================================================
-- SEED DATA — RATING CATEGORIES (9 rows, v0)
-- Run once at initial migration.
-- =============================================================
INSERT INTO rating_categories (id, name, slug, headline_question, description, display_order) VALUES

(gen_random_uuid(),
 'Overall experience',
 'overall_experience',
 'Would you choose this university again?',
 'A holistic score reflecting your entire experience as a student at this university.',
 1),

(gen_random_uuid(),
 'Safety',
 'safety',
 'How safe is this university and its surroundings?',
 'Campus safety during the day, after hours, and safety of the surrounding neighborhood.',
 2),

(gen_random_uuid(),
 'Location & accessibility',
 'location_accessibility',
 'How accessible is the university by public transport?',
 'Public transport links, proximity to services, and ease of getting to and from campus.',
 3),

(gen_random_uuid(),
 'Campus & facilities',
 'campus_facilities',
 'How would you rate the campus and its facilities?',
 'Quality of classrooms, library, study spaces, and general maintenance.',
 4),

(gen_random_uuid(),
 'Academics & teaching',
 'academics_teaching',
 'How would you rate the quality of teaching?',
 'Course quality, curriculum relevance, and fairness of workload.',
 5),

(gen_random_uuid(),
 'Professor engagement',
 'professor_engagement',
 'How engaged and accessible are professors?',
 'Professor availability outside class, teaching clarity, and responsiveness to students.',
 6),

(gen_random_uuid(),
 'Student life & atmosphere',
 'student_life',
 'How would you describe student life here?',
 'Social environment, student clubs, events, and the general vibe of being a student.',
 7),

(gen_random_uuid(),
 'Sports & recreation',
 'sports_recreation',
 'How good are the sports and recreation facilities?',
 'Sports fields, gym access, and availability of recreational activities and teams.',
 8),

(gen_random_uuid(),
 'Food & canteen',
 'food_canteen',
 'How would you rate the food options on campus?',
 'Quality, price, and variety of food. In Tunisia, CROUS canteen quality is a key daily factor.',
 9);

-- =============================================================
-- SEED DATA — SUB-QUESTIONS
-- Linked to categories by slug for readability.
-- =============================================================

-- Safety sub-questions
INSERT INTO rating_sub_questions (id, category_id, sub_key, question_text, display_order)
SELECT gen_random_uuid(), rc.id, 'campus_day',
       'How safe do you feel on campus during the day?', 1
FROM rating_categories rc WHERE rc.slug = 'safety';

INSERT INTO rating_sub_questions (id, category_id, sub_key, question_text, display_order)
SELECT gen_random_uuid(), rc.id, 'surroundings',
       'How safe is the area immediately outside the university?', 2
FROM rating_categories rc WHERE rc.slug = 'safety';

INSERT INTO rating_sub_questions (id, category_id, sub_key, question_text, display_order)
SELECT gen_random_uuid(), rc.id, 'after_hours',
       'How safe do you feel on campus after hours or during quiet periods?', 3
FROM rating_categories rc WHERE rc.slug = 'safety';

-- Location sub-questions
INSERT INTO rating_sub_questions (id, category_id, sub_key, question_text, display_order)
SELECT gen_random_uuid(), rc.id, 'transport',
       'How frequent and direct is public transport to this university?', 1
FROM rating_categories rc WHERE rc.slug = 'location_accessibility';

INSERT INTO rating_sub_questions (id, category_id, sub_key, question_text, display_order)
SELECT gen_random_uuid(), rc.id, 'services',
       'How useful are the shops and services around the university?', 2
FROM rating_categories rc WHERE rc.slug = 'location_accessibility';

-- Campus sub-questions
INSERT INTO rating_sub_questions (id, category_id, sub_key, question_text, display_order)
SELECT gen_random_uuid(), rc.id, 'classrooms',
       'How would you rate the classrooms and lecture halls?', 1
FROM rating_categories rc WHERE rc.slug = 'campus_facilities';

INSERT INTO rating_sub_questions (id, category_id, sub_key, question_text, display_order)
SELECT gen_random_uuid(), rc.id, 'library',
       'How would you rate the library?', 2
FROM rating_categories rc WHERE rc.slug = 'campus_facilities';

INSERT INTO rating_sub_questions (id, category_id, sub_key, question_text, display_order)
SELECT gen_random_uuid(), rc.id, 'study_spaces',
       'How would you rate the availability of quiet study spaces?', 3
FROM rating_categories rc WHERE rc.slug = 'campus_facilities';

-- Academics sub-questions
INSERT INTO rating_sub_questions (id, category_id, sub_key, question_text, display_order)
SELECT gen_random_uuid(), rc.id, 'course_quality',
       'How relevant and well-structured are the courses?', 1
FROM rating_categories rc WHERE rc.slug = 'academics_teaching';

INSERT INTO rating_sub_questions (id, category_id, sub_key, question_text, display_order)
SELECT gen_random_uuid(), rc.id, 'workload',
       'How fair is the workload?', 2
FROM rating_categories rc WHERE rc.slug = 'academics_teaching';

-- Professor sub-questions
INSERT INTO rating_sub_questions (id, category_id, sub_key, question_text, display_order)
SELECT gen_random_uuid(), rc.id, 'accessibility',
       'How accessible are professors outside of class?', 1
FROM rating_categories rc WHERE rc.slug = 'professor_engagement';

INSERT INTO rating_sub_questions (id, category_id, sub_key, question_text, display_order)
SELECT gen_random_uuid(), rc.id, 'clarity',
       'How clearly do professors explain the material?', 2
FROM rating_categories rc WHERE rc.slug = 'professor_engagement';

-- =============================================================
-- SEED DATA — EXAMPLE UNIVERSITY (TBS)
-- Replace with real data. Coordinates are approximate.
-- =============================================================
INSERT INTO universities (
    name_ar, name_fr, acronym, type,
    governorate, neighborhood, address,
    latitude, longitude,
    nearest_transport, website_url, description, is_active
) VALUES (
    'معهد إدارة الأعمال بتونس',
    'Tunis Business School',
    'TBS',
    'public',
    'Ben Arous',
    'El Mourouj',
    'Campus Universitaire, El Mourouj, Ben Arous',
    36.6979, 10.1836,
    'Metro line 1 — Mourouj stop, 8 min walk',
    'https://utunis.rnu.tn/tbs/',
    'Tunis Business School is the first public English-language business school in Tunisia, established in 2010 under the University of Tunis.',
    true
);

-- Register TBS email domain
INSERT INTO email_domains (university_id, domain, is_active)
SELECT id, 'tbs.u-tunis.tn', true FROM universities WHERE acronym = 'TBS';

-- =============================================================
-- USEFUL QUERIES FOR REFERENCE
-- Not part of the migration — kept here for developer reference.
-- =============================================================

-- Average score per category for a given university
-- SELECT
--     rc.name AS category,
--     rc.slug,
--     ROUND(AVG(rs.score)::numeric, 2) AS avg_score,
--     COUNT(rs.id) AS num_ratings
-- FROM rating_scores rs
-- JOIN rating_submissions rsub ON rs.submission_id = rsub.id
-- JOIN rating_categories rc ON rs.category_id = rc.id
-- WHERE rsub.university_id = '<university_uuid>'
--   AND rsub.moderation_status = 'approved'
-- GROUP BY rc.id, rc.name, rc.slug
-- ORDER BY rc.display_order;

-- Fetch featured comments for a university's safety category
-- SELECT
--     c.body,
--     c.is_anonymous,
--     CASE WHEN c.is_anonymous THEN 'Anonymous'
--          ELSE u.full_name END AS author,
--     c.created_at
-- FROM comments c
-- JOIN rating_submissions rsub ON c.submission_id = rsub.id
-- JOIN users u ON rsub.user_id = u.id
-- JOIN rating_categories rc ON c.category_id = rc.id
-- WHERE rsub.university_id = '<university_uuid>'
--   AND rc.slug = 'safety'
--   AND c.is_featured = true
--   AND c.moderation_status = 'approved'
-- ORDER BY c.created_at DESC;
