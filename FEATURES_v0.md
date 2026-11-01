# WajhUni — Features Requirements Document
**Version:** 0.1 (v0 — MVP)  
**Last updated:** April 2026  
**Author:** WajhUni founding team  
**Status:** Locked for v0 development

---

## 1. Product vision

WajhUni is a platform that gives Tunisian high school graduates honest, student-sourced information about universities before they commit to one. Every student on the platform is a verified current student reviewing their own university — no outsiders, no fake reviews.

v0 is intentionally narrow: **browse universities, see photos and structured info, read verified student ratings.** Nothing more. Features grow based on real user needs after launch.

---

## 2. Target users

| User type | Description | Primary goal |
|---|---|---|
| Prospective student | High school graduate choosing a university | Browse and compare universities before committing |
| Current student | Enrolled university student (verified by email) | Rate their university and share their experience |
| Parent | Browsing on behalf of their child | Evaluate safety, location, and overall quality |
| Platform admin | You (the founder) | Moderate ratings, approve photos, manage universities |

> **Note on parents:** Parents are read-only users — they browse but do not register. The platform must be readable without an account. Safety ratings are the feature most relevant to this audience.

---

## 3. v0 scope — what is and is not included

### In v0
- University listing and detail pages (Tunis governorate only at launch)
- Structured university information seeded manually by admin
- Photo gallery per university (admin-seeded + user uploads)
- Student registration with university email verification
- JWT-based authentication and session management
- Rating submission (own university only, one per student)
- 9 rating categories with sub-scores and optional written comments
- Featured comments (testimonials) selected by admin
- Admin moderation panel for ratings and photos
- Search and basic filter on the university listing page

### Explicitly deferred (not in v0)
| Feature | Target version |
|---|---|
| Forum / posts / community feed | v1 |
| Student housing & dorms info | v1 |
| University comparison tool (side by side) | v1 |
| Majors & programs per university | v1 |
| AI chatbot | v2 |
| Career outcomes per major | v2 |
| Notifications system | v1 |
| Mobile app | post-v1 |
| Universities outside Tunis governorate | v1 rollout |

---

## 4. Feature specifications

---

### 4.1 University listing page

**Purpose:** Entry point for prospective students. Browse all active universities.

**Behavior:**
- Accessible without an account (fully public)
- Displays a card per university showing: name (Arabic + French), acronym, type badge (Public / Private / Grandes Écoles), governorate, overall grade (A+ to F), headline photo, and number of ratings
- Filter options: university type, governorate (for when we expand beyond Tunis)
- Search by name or acronym
- Cards sorted by overall rating score descending by default
- Universities with zero ratings are shown last with a "No reviews yet" label instead of a grade

**Edge cases:**
- If a university has fewer than 5 ratings, display the score with a warning: "Based on fewer than 5 reviews — treat with caution"
- Inactive universities (`is_active = false`) are hidden from listing

---

### 4.2 University detail page

**Purpose:** The core product page. Everything a prospective student needs to evaluate a university.

**Sections (in order):**

**Header**
- University full name in Arabic and French, acronym
- Type badge, governorate, neighborhood
- Overall grade (large, prominent — letter grade A+ to F)
- Total number of verified ratings
- Nearest transport info (e.g. "Metro line 1 — Mourouj stop, 8 min walk")

**Photo gallery**
- Minimum 1 photo required for a university to be listed as active
- Photos categorized: Campus, Library, Sports, Canteen, Other
- Admin-approved photos shown first, ordered by `display_order`

**Map embed**
- Google Maps embed using stored lat/lng coordinates
- Shows campus pin + nearest metro/bus stop (if coordinates provided)

**Rating breakdown**
- 9 category cards, each showing:
  - Category name and letter grade
  - Bar chart of sub-scores
  - Number of ratings for this category
- Categories displayed in fixed order (see section 5)

**Student testimonials**
- 3–5 featured comments selected by admin (`is_featured = true`)
- Shown with: category label, anonymized name (or "Anonymous"), year of submission
- Safety category testimonials shown first if featured

**All reviews section**
- Paginated list of approved rating submissions
- Each shows: overall score, written comments per category (if provided), date, anonymous or first name only
- Sorted by most recent by default

---

### 4.3 User registration and email verification

**Purpose:** Ensure only real current students can submit ratings.

**Flow:**
1. User enters full name, university email, password
2. System extracts domain from email (e.g. `tbs.u-tunis.tn`)
3. Domain is checked against `email_domains` table
4. If domain matches → send verification email with 24-hour expiry token
5. If domain not found → show error: "Your university is not yet on WajhUni. Contact us to add it."
6. User clicks verification link → `verification_status` set to `verified`, `university_id` auto-assigned from domain match
7. User is now able to submit a rating

**Constraints:**
- One account per email address
- Unverified accounts cannot submit ratings but can browse
- Verification tokens expire after 24 hours and can be resent once per hour

---

### 4.4 Authentication

**Technology:** JWT with refresh tokens

**Access token:** 15-minute expiry — short to limit exposure if leaked  
**Refresh token:** 7-day expiry, stored in Redis, rotated on each use  
**Password hashing:** bcrypt with cost factor 12

**Sessions:**
- Refresh token invalidated on explicit logout
- All sessions invalidated if admin suspends a user

---

### 4.5 Rating submission

**Purpose:** Collect honest, structured student evaluations.

**Constraints (all enforced at both API and database level):**
- User must be verified (`verification_status = verified`)
- User can only rate their own university (`submission.university_id == user.university_id`)
- One submission per user per university (`UNIQUE(user_id, university_id)`)
- One update allowed after 6 months from original submission date
- Review is permanently locked after the update (`is_locked = true`)

**Rating form UX:**
- One category per screen (mobile-first — reduces abandonment)
- For each category: headline question, 1–5 star sub-questions, optional written comment (max 280 characters)
- Student can save progress and return later (draft state) — but draft is not visible to other users
- Anonymous toggle: student can hide their name from their review (their `user_id` is still stored internally for moderation)
- Submit button only active when all 9 category headline scores are filled (sub-scores and comments are optional)

**After submission:**
- Submission enters `moderation_status = pending`
- Admin reviews and approves or flags
- Student receives email confirmation when their review goes live
- Student can see their own pending review on the university page (visible only to them)

**Update flow:**
- After 6 months: "Update your review" button appears on the student's profile
- Student can revise any score or comment
- On save: `updated_at` is refreshed, `is_locked` set to `true`
- No further updates possible

---

### 4.6 Rating categories and sub-questions

**Display order and category definitions:**

| Order | Category | Slug | Headline question |
|---|---|---|---|
| 1 | Overall experience | `overall_experience` | "Would you choose this university again?" |
| 2 | Safety | `safety` | "How safe is this university and its surroundings?" |
| 3 | Location & accessibility | `location_accessibility` | "How accessible is the university by public transport?" |
| 4 | Campus & facilities | `campus_facilities` | "How would you rate the campus and its facilities?" |
| 5 | Academics & teaching | `academics_teaching` | "How would you rate the quality of teaching?" |
| 6 | Professor engagement | `professor_engagement` | "How engaged and accessible are professors?" |
| 7 | Student life & atmosphere | `student_life` | "How would you describe student life here?" |
| 8 | Sports & recreation | `sports_recreation` | "How good are the sports and recreation facilities?" |
| 9 | Food & canteen | `food_canteen` | "How would you rate the food options on campus?" |

**Sub-questions per category:**

*Safety*
- "How safe do you feel on campus during the day?" (1–5)
- "How safe is the area immediately outside the university?" (1–5)
- "How safe do you feel on campus after hours or during quiet periods?" (1–5)
- Comment prompt: "Describe a situation that shaped your safety rating."

*Location & accessibility*
- "How frequent and direct is public transport to this university?" (1–5)
- "How useful are the shops and services around the university?" (1–5)
- Comment prompt: "How do you get to university and how long does it take?"

*Campus & facilities*
- "How would you rate the classrooms and lecture halls?" (1–5)
- "How would you rate the library?" (1–5)
- "How would you rate the availability of study spaces?" (1–5)

*Academics & teaching*
- "How relevant and well-structured are the courses?" (1–5)
- "How fair is the workload?" (1–5)

*Professor engagement*
- "How accessible are professors outside class?" (1–5)
- "How clearly do professors explain material?" (1–5)

*Student life, Sports, Food, Overall* — single 1–5 score (no sub-questions in v0)

---

### 4.7 Photo upload

**Who can upload:** Verified students (for their own university only)  
**Admin:** Can upload for any university, sets `display_order`

**Constraints:**
- File types: JPG, PNG, WebP only
- Max file size: 5MB per photo
- Max 10 uploads per user (prevents abuse)
- Photos enter `is_approved = false` on upload — admin must approve before they appear publicly
- Storage: Azure Blob Storage

---

### 4.8 Admin moderation panel

**Access:** Role `admin` only — separate login, not exposed in public nav

**Capabilities:**
- View all pending rating submissions
- Approve / flag / reject individual submissions
- Flag specific comments within an approved submission
- Mark comments as featured (`is_featured = true`)
- Approve or reject user-uploaded photos
- Set `display_order` on photos
- Manage universities (add, edit, activate/deactivate)
- Manage email domains (add new university email domains)
- Suspend user accounts

**Moderation queue priority:**
1. Pending ratings (by submission date, oldest first)
2. Pending photos
3. Flagged content (user-reported)

---

## 5. Grade calculation

**Letter grade mapping from average score:**

| Score range | Grade |
|---|---|
| 4.7 – 5.0 | A+ |
| 4.3 – 4.6 | A |
| 4.0 – 4.2 | A- |
| 3.7 – 3.9 | B+ |
| 3.3 – 3.6 | B |
| 3.0 – 3.2 | B- |
| 2.7 – 2.9 | C+ |
| 2.3 – 2.6 | C |
| 2.0 – 2.2 | C- |
| 1.7 – 1.9 | D+ |
| 1.3 – 1.6 | D |
| 1.0 – 1.2 | D- |
| below 1.0 | F |

**Category score** = average of its sub-scores (or single score if no sub-questions)  
**Overall grade** = weighted average of all 8 non-overall categories (equal weight in v0)

---

## 6. Non-functional requirements

| Requirement | Target |
|---|---|
| Page load time | < 2 seconds on 4G mobile |
| Uptime | 99% (Azure SLA covers this) |
| Language | Arabic + French (bilingual UI in v1 — English-only UI acceptable in v0) |
| Mobile responsiveness | Required — majority of Tunisian students browse on mobile |
| Accessibility | Basic WCAG AA compliance |
| Data retention | User data retained for 3 years after account inactivity |

---

## 7. v1 and v2 backlog (parking lot)

| Feature | Version | Notes |
|---|---|---|
| Forum / community posts | v1 | Per-university feed, text + images |
| Student housing & dorms | v1 | Needs enough dorm residents to be useful |
| University comparison tool | v1 | Side-by-side up to 3 universities |
| Majors & programs listing | v1 | Admin-seeded structured data |
| Bilingual UI (Arabic / French) | v1 | English-only acceptable for v0 |
| AI chatbot | v2 | RAG on university data + ratings |
| Career outcomes per major | v2 | Needs alumni crowdsourcing or LinkedIn data |
| Expand beyond Tunis governorate | v1 rollout | Sfax, Sousse, Monastir next |
| Mobile app (React Native) | post-v1 | Web-first, then app |
| University official responses | v2 | Let universities respond to ratings |
