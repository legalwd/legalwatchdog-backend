"""Assembles and exports the versioned API router for v1."""

from fastapi import APIRouter, Depends

from app.api.core.dependencies.auth import require_approved_user, require_superadmin
from app.api.modules.v1.admin.routes.customers import router as customers_router
from app.api.modules.v1.admin.routes.dashboard import router as dashboard_router
from app.api.modules.v1.admin.routes.llm_monitoring import router as llm_monitoring_router
from app.api.modules.v1.admin.routes.organizations import router as organizations_router
from app.api.modules.v1.admin.routes.parallel_monitoring import router as parallel_monitoring_router
from app.api.modules.v1.admin.routes.scraping_admin import router as scraping_admin_router
from app.api.modules.v1.api_access.routes.api_key_route import router as api_key_router
from app.api.modules.v1.api_access.routes.external_extracted_data_route import (
    router as external_extracted_router,
)
from app.api.modules.v1.api_access.routes.webhook_route import router as api_webhook_router
from app.api.modules.v1.auth.routes.apple_auth_route import router as apple_auth_router
from app.api.modules.v1.auth.routes.auth_routes import router as register_router
from app.api.modules.v1.auth.routes.login_route import router as auth_router
from app.api.modules.v1.auth.routes.oauth_google import router as oauth_google_router
from app.api.modules.v1.auth.routes.oauth_microsoft import router as oauth_microsoft_router
from app.api.modules.v1.auth.routes.reset_password import router as password_reset_router
from app.api.modules.v1.billing.routes import billing_router
from app.api.modules.v1.campaigns.routes.campaign_remediation_routes import (
    router as campaign_remediation_router,
)
from app.api.modules.v1.campaigns.routes.campaign_routes import router as campaigns_router
from app.api.modules.v1.campaigns.routes.taxonomy_routes import router as taxonomy_router
from app.api.modules.v1.contact_us.routes.contact_us import router as contact_us_router
from app.api.modules.v1.hire_specialists.routes.specialist_routes import router as specialist_router
from app.api.modules.v1.jurisdictions.routes.blog_routes import router as blog_router
from app.api.modules.v1.jurisdictions.routes.guides_routes import router as guides_router
from app.api.modules.v1.jurisdictions.routes.jurisdiction_route import router as juridiction_router
from app.api.modules.v1.jurisdictions.routes.public_blog_routes import router as public_blog_router
from app.api.modules.v1.notifications.routes.notification_route import router as notification_router
from app.api.modules.v1.organization.routes import router as organization_router
from app.api.modules.v1.projects.routes.project_routes import router as project_router
from app.api.modules.v1.scraping.routes import router as scraping_router
from app.api.modules.v1.scraping.routes.output_routes import router as output_router
from app.api.modules.v1.search.routes import data_revision_search_router
from app.api.modules.v1.tickets.routes import (
    comment_router,
    guest_access_router,
    participant_router,
)
from app.api.modules.v1.tickets.routes.close_ticket_routes import router as close_ticket_router
from app.api.modules.v1.tickets.routes.ticket_routes import router as ticket_router
from app.api.modules.v1.users.routes.users_route import router as users_router
from app.api.modules.v1.waitlist.routes.waitlist_route import router as waitlist_router

router = APIRouter(prefix="/v1")

router.include_router(public_blog_router)
router.include_router(guides_router)
router.include_router(waitlist_router)
router.include_router(contact_us_router)
router.include_router(register_router)
router.include_router(auth_router)
router.include_router(password_reset_router)
router.include_router(oauth_microsoft_router)
router.include_router(oauth_google_router)
router.include_router(apple_auth_router)
router.include_router(guest_access_router)

router.include_router(users_router)
router.include_router(organization_router)
router.include_router(project_router, dependencies=[Depends(require_approved_user)])
router.include_router(juridiction_router, dependencies=[Depends(require_approved_user)])
router.include_router(scraping_router, dependencies=[Depends(require_approved_user)])
router.include_router(ticket_router, dependencies=[Depends(require_approved_user)])
router.include_router(close_ticket_router, dependencies=[Depends(require_approved_user)])
router.include_router(comment_router, dependencies=[Depends(require_approved_user)])
router.include_router(notification_router, dependencies=[Depends(require_approved_user)])
router.include_router(specialist_router, dependencies=[Depends(require_approved_user)])
router.include_router(billing_router, dependencies=[Depends(require_approved_user)])
router.include_router(data_revision_search_router, dependencies=[Depends(require_approved_user)])
router.include_router(participant_router, dependencies=[Depends(require_approved_user)])
router.include_router(api_key_router, dependencies=[Depends(require_approved_user)])
router.include_router(output_router, dependencies=[Depends(require_approved_user)])

router.include_router(external_extracted_router)
router.include_router(api_webhook_router)

router.include_router(
    llm_monitoring_router,
    dependencies=[Depends(require_approved_user), Depends(require_superadmin)],
)
router.include_router(
    parallel_monitoring_router,
    dependencies=[Depends(require_approved_user), Depends(require_superadmin)],
)
router.include_router(
    dashboard_router,
    dependencies=[Depends(require_approved_user), Depends(require_superadmin)],
)
router.include_router(
    customers_router,
    dependencies=[Depends(require_approved_user), Depends(require_superadmin)],
)
router.include_router(
    scraping_admin_router,
    dependencies=[Depends(require_approved_user), Depends(require_superadmin)],
)
router.include_router(
    organizations_router,
    dependencies=[Depends(require_approved_user), Depends(require_superadmin)],
)
router.include_router(
    blog_router,
    dependencies=[Depends(require_approved_user), Depends(require_superadmin)],
)
router.include_router(
    campaigns_router,
    dependencies=[Depends(require_approved_user), Depends(require_superadmin)],
)
router.include_router(
    taxonomy_router,
    dependencies=[Depends(require_approved_user), Depends(require_superadmin)],
)
router.include_router(
    campaign_remediation_router,
    dependencies=[Depends(require_approved_user), Depends(require_superadmin)],
)
