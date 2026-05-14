# Frontend API Guide: Guides & Blog Endpoints

This document describes how frontend applications should interact with the LegalWatch public APIs for:
1. **Guides API** - Public-facing compliance guide listings (industry → region → jurisdiction)
2. **Blog API** - Raw blog posts for SSG/SSR rendering

---

## Base URL

```
Production: https://legalwatch.dog/api/v1
Staging:    https://staging.legalwatch.dog/api/v1
```

---

## 1. Guides API

Public endpoints for browsing compliance guides by industry, region, and jurisdiction.

**How to determine the industry slug:**

The industry slug is derived from either:
1. **Campaign.industry** - Each campaign can have its own industry (recommended)
2. **Organization.industry** - The organization's primary industry

Convert to slug by: lowercase + replace spaces with hyphens.

| Campaign/Org Industry | Slug |
|----------------------|------|
| Human Resources | `human-resources` |
| EOR | `eor` |
| Financial Services | `financial-services` |
| Fintech | `fintech` |
| Healthcare | `healthcare` |
| Technology | `technology` |
| Sustainability | `sustainability` |

### 1.1 List Industries / Get Industry Regions

**Endpoint:** `GET /guides/{industry}/`

Returns all regions for a given industry with jurisdiction counts.

```http
GET /api/v1/guides/eor/
GET /api/v1/guides/fintech/
GET /api/v1/guides/healthcare/
```

**Response:**

```json
{
  "status": "SUCCESS",
  "status_code": 200,
  "message": "Industry listing retrieved successfully",
  "data": {
    "industry": "eor",
    "industry_display_name": "EOR",
    "total_jurisdictions": 150,
    "last_updated": "2026-04-25T10:30:00Z",
    "regions": [
      {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "name": "United States",
        "slug": "united-states",
        "jurisdiction_count": 52,
        "latest_update": "2026-04-25T10:30:00Z",
        "url": "https://legalwatch.dog/guides/eor/united-states/"
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total_pages": 3,
      "total_items": 45
    }
  }
}
```

**Query Parameters:**

| Parameter  | Type    | Default | Description                    |
|------------|---------|---------|--------------------------------|
| `page`     | integer | 1       | Page number (1-indexed)       |
| `per_page` | integer | 20      | Items per page (max 100)      |

### 1.2 List Region Jurisdictions

**Endpoint:** `GET /guides/{industry}/{region}/`

Returns all jurisdictions within a region for a specific industry.

```http
GET /api/v1/guides/eor/united-states/
```

**Response:**

```json
{
  "status": "SUCCESS",
  "status_code": 200,
  "message": "Region listing retrieved successfully",
  "data": {
    "industry": "eor",
    "region_id": "123e4567-e89b-12d3-a456-426614174000",
    "region_name": "United States",
    "region_slug": "united-states",
    "jurisdictions": [
      {
        "id": "789e4567-e89b-12d3-a456-426614174001",
        "name": "California",
        "slug": "california",
        "post_url": "https://legalwatch.dog/guides/eor/united-states/california/",
        "summary": "Comprehensive EOR compliance guide for California covering minimum wage, PTO, and termination rules.",
        "updated_at": "2026-04-25T10:30:00Z",
        "key_topics": ["minimum wage", "PTO", "termination", "payroll"]
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total_pages": 3,
      "total_items": 52
    }
  }
}
```

**Query Parameters:**

| Parameter  | Type    | Default | Description                              |
|------------|---------|---------|------------------------------------------|
| `page`     | integer | 1       | Page number (1-indexed)                  |
| `per_page` | integer | 20      | Items per page (max 100)                 |
| `sort`     | string  | name    | Sort field: `name`, `updated`            |
| `order`    | string  | asc     | Sort order: `asc`, `desc`                |

**Sorting Examples:**

```http
GET /api/v1/guides/eor/united-states/?sort=updated&order=desc
GET /api/v1/guides/eor/united-states/?sort=name&order=asc
```

### 1.3 Get Jurisdiction Detail

**Endpoint:** `GET /guides/{industry}/{region}/{jurisdiction}/`

Returns detailed metadata for a specific jurisdiction's guide.

```http
GET /api/v1/guides/eor/united-states/california/
```

**Response:**

```json
{
  "status": "SUCCESS",
  "status_code": 200,
  "message": "Jurisdiction detail retrieved successfully",
  "data": {
    "id": "789e4567-e89b-12d3-a456-426614174001",
    "name": "California",
    "slug": "california",
    "industry": "eor",
    "post_url": "https://legalwatch.dog/guides/eor/united-states/california/",
    "breadcrumbs": [
      {
        "name": "United States",
        "url": "https://legalwatch.dog/guides/eor/united-states/"
      },
      {
        "name": "California",
        "url": "https://legalwatch.dog/guides/eor/united-states/california/"
      }
    ],
    "title": "California EOR Compliance Guide 2026",
    "meta_description": "Comprehensive EOR compliance guide for California covering minimum wage, PTO, and termination rules.",
    "keywords": ["California", "EOR", "employment law", "compliance"],
    "published_at": "2026-04-01T12:00:00Z",
    "updated_at": "2026-04-25T10:30:00Z"
  }
}
```

---

## 2. Blog API (Raw Content)

Public endpoints for fetching full blog post content (Markdown/HTML).

### 2.1 List Published Posts

**Endpoint:** `GET /blog/posts`

Returns paginated list of all published blog posts.

```http
GET /api/v1/blog/posts?page=1&limit=20
```

**Response:**

```json
{
  "status": "SUCCESS",
  "status_code": 200,
  "message": "Published blog posts retrieved successfully",
  "data": {
    "items": [
      {
        "id": "789e4567-e89b-12d3-a456-426614174001",
        "title": "California EOR Compliance Guide",
        "slug": "california-eor-compliance-guide",
        "content": "## Executive Summary\n\nThis guide provides...",
        "content_html": "<h2>Executive Summary</h2><p>This guide provides...</p>",
        "meta_description": "Comprehensive EOR compliance guide for California",
        "keywords": ["California", "EOR", "employment law"],
        "is_published": true,
        "version": 2,
        "generated_at": "2026-04-25T10:30:00Z",
        "published_at": "2026-04-01T12:00:00Z",
        "resource_path": "/resources/human-resources-global-seo-compliance-country-depth/sri-lanka/technology-guide-sri-lanka/",
        "public_url": "https://legalwatch.dog/resources/human-resources-global-seo-compliance-country-depth/sri-lanka/technology-guide-sri-lanka/"
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total_pages": 10,
      "total_items": 200
    }
  }
}
```

### 2.2 Get Post by Slug

**Endpoint:** `GET /blog/posts/{slug}`

Returns a single published blog post by its slug.

```http
GET /api/v1/blog/posts/california-eor-compliance-guide
```

**Query Parameters:**

| Parameter              | Type    | Default | Description                                      |
|------------------------|---------|---------|--------------------------------------------------|
| `redirect_to_public_url` | boolean | false   | If true, redirects to canonical public URL      |

**Response:**

```json
{
  "status": "SUCCESS",
  "status_code": 200,
  "message": "Blog post retrieved successfully",
  "data": {
    "id": "789e4567-e89b-12d3-a456-426614174001",
    "title": "California EOR Compliance Guide",
    "slug": "california-eor-compliance-guide",
    "content": "## Executive Summary\n\nThis guide provides...",
    "content_html": "<h2>Executive Summary</h2><p>This guide provides...</p>",
    "meta_description": "Comprehensive EOR compliance guide for California",
    "keywords": ["California", "EOR", "employment law"],
    "breadcrumbs": [
      {
        "name": "California",
        "url": "https://legalwatch.dog/guides/eor/united-states/california/"
      }
    ],
    "is_published": true,
    "version": 2,
    "generated_at": "2026-04-25T10:30:00Z",
    "published_at": "2026-04-01T12:00:00Z",
    "resource_path": "/resources/...",
    "public_url": "https://legalwatch.dog/resources/..."
  }
}
```

---

## 3. URL Structure

The system uses two URL patterns:

### Pattern A: `/guides/` (Recommended for new implementation)

```
/guides/{industry}/{region}/{jurisdiction}/
Example: /guides/eor/united-states/california/
```

- **Industry:** `eor`, `fintech`, `healthcare`, `sustainability`, etc.
- **Region:** Country or region name (slugified)
- **Jurisdiction:** Specific jurisdiction (slugified)

### Pattern B: `/resources/` (Legacy)

```
/resources/{project}/{jurisdiction}/{slug}/
```

This is the legacy pattern returned in `resource_path` and `public_url` from the Blog API.

---

## 4. Error Responses

All endpoints return consistent error responses:

```json
{
  "error_code": "NOT_FOUND",
  "message": "Resource not found",
  "status_code": 404,
  "errors": {}
}
```

**Common Status Codes:**

| Code | Meaning                      |
|------|------------------------------|
| 200  | Success                      |
| 400  | Bad Request (invalid params)|
| 404  | Resource Not Found          |
| 500  | Internal Server Error       |

---

## 5. Integration Recommendations

### 5.1 Static Site Generation (SSG)

For build-time rendering:

1. **Fetch all published posts:**
   ```bash
   GET /api/v1/blog/posts?page=1&limit=100
   ```

2. **Parse slugs and generate routes** based on `resource_path`

3. **Fetch full content** per slug:
   ```bash
   GET /api/v1/blog/posts/{slug}
   ```

4. **Use `content_html`** directly in page templates

### 5.2 Client-Side Navigation

For SPA/SSR with client-side navigation:

1. **Industry listing:** `GET /guides/{industry}/`
2. **Region listing:** `GET /guides/{industry}/{region}/`
3. **Jurisdiction detail:** `GET /guides/{industry}/{region}/{jurisdiction}/`

### 5.3 SEO Considerations

- Use `meta_description` from API responses for `<meta name="description">`
- Use `keywords` array for `<meta name="keywords">`
- Generate `canonical_url` using `public_url` from API
- Breadcrumbs in API response can be rendered as JSON-LD schema markup

---

## 6. Available Industries

The industry slug is determined from either:
- **Campaign.industry** (per-campaign, recommended)
- **Organization.industry** (fallback)

Common industry slugs:

- `human-resources` - Human Resources / HR Compliance
- `eor` - Employer of Record / Employment
- `technology` - Technology
- `fintech` - Financial Services / Fintech
- `healthcare` - Healthcare
- `sustainability` - Environmental/ESG
- Other custom industries based on campaign configurations

---

## 7. Pagination

All list endpoints support pagination:

```json
{
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total_pages": 5,
    "total_items": 100
  }
}
```

**Page calculation:** `total_pages = ceil(total_items / per_page)`

---

## 10. Admin API - Campaign Management

The following endpoints require **superadmin authentication** (`Authorization: Bearer <token>`).

### 10.1 Create Campaign

**Endpoint:** `POST /api/v1/campaigns/`

```http
POST /api/v1/campaigns/
Authorization: Bearer <superadmin_token>
Content-Type: application/json

{
  "name": "Global EOR Compliance 2026",
  "organization_id": "uuid",
  "industry": "eor"
}
```

### 10.2 List Campaigns

**Endpoint:** `GET /api/v1/campaigns/`

```http
GET /api/v1/campaigns/?status=DRAFT&industry=eor&page=1&limit=20
Authorization: Bearer <superadmin_token>
```

### 10.3 Get Campaign

**Endpoint:** `GET /api/v1/campaigns/{campaign_id}/`

```http
GET /api/v1/campaigns/0ed17188-abb3-4459-8047-8c898d10674c/
Authorization: Bearer <superadmin_token>
```

### 10.4 Update Campaign

**Endpoint:** `PATCH /api/v1/campaigns/{campaign_id}/`

```http
PATCH /api/v1/campaigns/0ed17188-abb3-4459-8047-8c898d10674c/
Authorization: Bearer <superadmin_token>
Content-Type: application/json

{
  "name": "Updated Campaign Name"
}
```

### 10.5 Delete Campaign

**Endpoint:** `DELETE /api/v1/campaigns/{campaign_id}/`

```http
DELETE /api/v1/campaigns/0ed17188-abb3-4459-8047-8c898d10674c/
Authorization: Bearer <superadmin_token>
```

### 10.6 Launch Campaign

**Endpoint:** `POST /api/v1/campaigns/{campaign_id}/launch`

Starts the full campaign pipeline (discovery → scraping → content generation).

```http
POST /api/v1/campaigns/0ed17188-abb3-4459-8047-8c898d10674c/launch
Authorization: Bearer <superadmin_token>
```

### 10.7 Get Campaign Status

**Endpoint:** `GET /api/v1/campaigns/{campaign_id}/status`

```http
GET /api/v1/campaigns/0ed17188-abb3-4459-8047-8c898d10674c/status
Authorization: Bearer <superadmin_token>
```

### 10.8 Pause Campaign

**Endpoint:** `POST /api/v1/campaigns/{campaign_id}/pause`

```http
POST /api/v1/campaigns/0ed17188-abb3-4459-8047-8c898d10674c/pause
Authorization: Bearer <superadmin_token>
```

### 10.9 Resume Campaign

**Endpoint:** `POST /api/v1/campaigns/{campaign_id}/resume`

```http
POST /api/v1/campaigns/0ed17188-abb3-4459-8047-8c898d10674c/resume
Authorization: Bearer <superadmin_token>
```

### 10.10 Cancel Campaign

**Endpoint:** `POST /api/v1/campaigns/{campaign_id}/cancel`

```http
POST /api/v1/campaigns/0ed17188-abb3-4459-8047-8c898d10674c/cancel
Authorization: Bearer <superadmin_token>
```

### 10.11 Generate Content (Run)

**Endpoint:** `POST /api/v1/campaigns/{campaign_id}/content/run`

Generate content for jurisdictions with state data.

```http
POST /api/v1/campaigns/0ed17188-abb3-4459-8047-8c898d10674c/content/run
Authorization: Bearer <superadmin_token>
```

### 10.12 Retry Failed Content

**Endpoint:** `POST /api/v1/campaigns/{campaign_id}/content/retry-failed`

Retry content generation for jurisdictions that previously failed.

```http
POST /api/v1/campaigns/0ed17188-abb3-4459-8047-8c898d10674c/content/retry-failed
Authorization: Bearer <superadmin_token>
```

### 10.13 Backfill Missing Content

**Endpoint:** `POST /api/v1/campaigns/{campaign_id}/content/backfill-missing`

Generate blogs for all jurisdictions with state data, even if they already have blogs.

```http
POST /api/v1/campaigns/0ed17188-abb3-4459-8047-8c898d10674c/content/backfill-missing
Authorization: Bearer <superadmin_token>
```

### 10.14 List Campaign Blogs

**Endpoint:** `GET /api/v1/campaigns/{campaign_id}/blogs/`

```http
GET /api/v1/campaigns/0ed17188-abb3-4459-8047-8c898d10674c/blogs/
Authorization: Bearer <superadmin_token>
```

### 10.15 Publish Campaign Blogs

**Endpoint:** `POST /api/v1/campaigns/{campaign_id}/blogs/publish`

```http
POST /api/v1/campaigns/0ed17188-abb3-4459-8047-8c898d10674c/blogs/publish
Authorization: Bearer <superadmin_token>
Content-Type: application/json

{
  "is_published": true,
  "publish_all": true
}
```

**Request body options:**

| Action | Body |
|--------|------|
| Publish all | `{"is_published": true, "publish_all": true}` |
| Unpublish all | `{"is_published": false, "publish_all": true}` |
| Publish specific | `{"is_published": true, "blog_ids": ["uuid1", "uuid2"]}` |
| Unpublish specific | `{"is_published": false, "blog_ids": ["uuid1"]}` |

### 10.16 Preview Campaign Blog

**Endpoint:** `GET /api/v1/campaigns/{campaign_id}/blogs/{blog_id}/preview`

Returns HTML preview (not published).

```http
GET /api/v1/campaigns/0ed17188-abb3-4459-8047-8c898d10674c/blogs/abc-123/preview
Authorization: Bearer <superadmin_token>
```

### 10.17 Retry Failed Scrapes

**Endpoint:** `POST /api/v1/campaigns/{campaign_id}/retry-failed-jobs`

```http
POST /api/v1/campaigns/0ed17188-abb3-4459-8047-8c898d10674c/retry-failed-jobs
Authorization: Bearer <superadmin_token>
```

### 10.18 Stream Campaign Progress (SSE)

**Endpoint:** `GET /api/v1/campaigns/{campaign_id}/progress-stream`

Real-time progress via Server-Sent Events.

```http
GET /api/v1/campaigns/0ed17188-abb3-4459-8047-8c898d10674c/progress-stream
Authorization: Bearer <superadmin_token>
```

---

## 12. Campaign Status Values

| Status | Description |
|--------|-------------|
| `DRAFT` | Campaign created but not launched |
| `LAUNCHING` | Pipeline starting |
| `DISCOVERING_SOURCES` | Finding regulatory sources |
| `HYDRATING` | Populating jurisdictions |
| `SCRAPING` | Scraping content |
| `GENERATING_CONTENT` | Generating blog posts |
| `PAUSED` | Campaign paused |
| `COMPLETED` | All phases done |
| `FAILED` | Pipeline failed |

---

## 13. Frontend Integration Guide

### 13.1 Navigation & Breadcrumbs

The Guides API provides breadcrumb data in the jurisdiction detail response:

```json
{
  "breadcrumbs": [
    {"name": "United States", "url": "https://legalwatch.dog/guides/eor/united-states/"},
    {"name": "California", "url": "https://legalwatch.dog/guides/eor/united-states/california/"}
  ]
}
```

**Frontend implementation:**
```javascript
// Render breadcrumbs in UI
function renderBreadcrumbs(breadcrumbs) {
  const html = breadcrumbs.map((crumb, index) => {
    const isLast = index === breadcrumbs.length - 1;
    if (isLast) {
      return `<span class="current">${crumb.name}</span>`;
    }
    return `<a href="${crumb.url}">${crumb.name}</a>`;
  }).join(' > ');
  return `<nav class="breadcrumbs">${html}</nav>`;
}

// Use in JSON-LD for SEO
function generateBreadcrumbSchema(breadcrumbs) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": breadcrumbs.map((crumb, index) => ({
      "@type": "ListItem",
      "position": index + 1,
      "name": crumb.name,
      "item": crumb.url
    }))
  };
}
```

### 10.2 Sorting

All list endpoints support sorting via query parameters:

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `sort` | `name`, `updated` | `name` | Sort field |
| `order` | `asc`, `desc` | `asc` | Sort order |

**Examples:**
```http
# Sort by name (A-Z)
GET /api/v1/guides/eor/united-states/?sort=name&order=asc

# Sort by last updated (newest first)
GET /api/v1/guides/eor/united-states/?sort=updated&order=desc
```

**Frontend sorting UI:**
```javascript
// Sorting dropdown
<select onchange="loadRegions(this.value)">
  <option value="?sort=name&order=asc">Name (A-Z)</option>
  <option value="?sort=name&order=desc">Name (Z-A)</option>
  <option value="?sort=updated&order=desc">Recently Updated</option>
  <option value="?sort=updated&order=asc">Oldest Updated</option>
</select>
```

### 10.3 Pagination

Pagination info is returned in every list response:

```json
{
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total_pages": 5,
    "total_items": 100
  }
}
```

**Frontend pagination:**
```javascript
function renderPagination(pagination) {
  const { page, total_pages } = pagination;
  let html = '';
  
  // Previous button
  if (page > 1) {
    html += `<a href="?page=${page - 1}">Previous</a>`;
  }
  
  // Page numbers
  for (let i = 1; i <= total_pages; i++) {
    if (i === page) {
      html += `<span class="current">${i}</span>`;
    } else {
      html += `<a href="?page=${i}">${i}</a>`;
    }
  }
  
  // Next button
  if (page < total_pages) {
    html += `<a href="?page=${page + 1}">Next</a>`;
  }
  
  return html;
}
```

### 10.4 URL Structure for SPA Routing

Map API responses to client-side routes:

```
API Response                          → Client Route
──────────────────────────────────────────────────────
industry_slug: "human-resources"     → /guides/human-resources/
region_slug: "united-states"         → /guides/human-resources/united-states/
jurisdiction_slug: "california"      → /guides/human-resources/united-states/california/
```

```javascript
// Build URLs from API data
function buildGuideUrl(industry, region, jurisdiction) {
  let url = `/guides/${industry}/`;
  if (region) url += `${region}/`;
  if (jurisdiction) url += `${jurisdiction}/`;
  return url;
}
```

---

## 14. Example: Full Page Load Flow

```javascript
// 1. Load industry page
fetch('/api/v1/guides/eor/')
  .then(r => r.json())
  .then(data => {
    // Render regions list
    renderRegions(data.data.regions);
  });

// 2. User clicks "United States"
fetch('/api/v1/guides/eor/united-states/')
  .then(r => r.json())
  .then(data => {
    // Render jurisdictions list
    renderJurisdictions(data.data.jurisdictions);
  });

// 3. User clicks "California"
// Option A: Use Guides API for metadata
fetch('/api/v1/guides/eor/united-states/california/')
  .then(r => r.json())
  .then(data => {
    renderMetadata(data.data); // SEO tags, breadcrumbs
  });

// Option B: Get full content from Blog API
fetch('/api/v1/blog/posts/california-eor-compliance-guide')
  .then(r => r.json())
  .then(data => {
    renderContent(data.data.content_html);
  });
```

---

## Changelog

- **2026-04-26:** Added `breadcrumbs` field to jurisdiction detail
- **2026-04-26:** Added sorting (`sort`, `order` params) to region listing
- **2026-04-26:** Guides API now returns industry-generic content (no org references)