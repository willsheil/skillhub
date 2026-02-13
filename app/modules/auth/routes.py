"""
Authentication routes for login and logout.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.modules.auth.dependencies import (
    get_current_user,
    require_admin,
    require_auth,
    verify_admin_credentials
)
from app.modules.auth.services import authenticate_user
from app.modules.auth.schemas import LoginRequest, UserResponse

logger = logging.getLogger("skillhub.auth")

# Create router
router = APIRouter(prefix="/auth", tags=["authentication"])

# Templates - configure at app level
templates = None


def set_templates(templates_obj):
    """Set the templates object for the auth module.

    Args:
        templates_obj: Jinja2Templates instance
    """
    global templates
    templates = templates_obj


@router.get("/login", response_class=type(templates) if templates else object)
async def login_page(request: Request, error: Optional[str] = None):
    """Display user login page.

    Args:
        request: FastAPI Request object
        error: Optional error message parameter

    Returns:
        Template response with login page
    """
    error_msg = None
    if error == "invalid":
        error_msg = "工号或 API 密钥错误"

    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": error_msg
    })


@router.post("/login")
async def login(
    request: Request,
    employee_id: str = Form(...),
    api_key: str = Form(...)
):
    """User login endpoint.

    Accepts employee_id and api_key as form parameters.
    Sets session variables on success.
    Updates last login timestamp.
    Returns success response or redirects on failure.

    Args:
        request: FastAPI Request object
        employee_id: Employee ID from form
        api_key: API key from form

    Returns:
        RedirectResponse to homepage or login page with error
    """
    # Authenticate user
    user = authenticate_user(employee_id, api_key)

    if user:
        # Set session variables
        request.session["user_id"] = user["id"]
        request.session["employee_id"] = user["employee_id"]
        request.session["role"] = user["role"]

        logger.info(f"User logged in: employee_id={employee_id}, user_id={user['id']}, role={user['role']}")

        # Redirect to homepage after login
        return RedirectResponse(url="/", status_code=302)
    else:
        logger.warning(f"Failed login attempt: employee_id={employee_id}")
        return RedirectResponse(
            url="/auth/login?error=invalid",
            status_code=302
        )


@router.post("/api/login")
async def api_login(
    request: Request,
    employee_id: str = Form(...),
    api_key: str = Form(...)
):
    """User login API endpoint (alias for /auth/login).

    This endpoint maintains backward compatibility with the original /api/login route.

    Args:
        request: FastAPI Request object
        employee_id: Employee ID from form
        api_key: API key from form

    Returns:
        RedirectResponse to homepage or login page with error
    """
    return await login(request, employee_id, api_key)


@router.get("/logout")
async def logout(request: Request):
    """Logout and clear session.

    Args:
        request: FastAPI Request object

    Returns:
        RedirectResponse to homepage
    """
    user_id = request.session.get("user_id")
    request.session.clear()
    logger.info(f"User logged out: user_id={user_id}")

    return RedirectResponse(url="/", status_code=302)


@router.get("/me")
async def get_me(request: Request):
    """Get current user information.

    Returns the current authenticated user's details.
    Raises HTTP 401 if not authenticated.

    Args:
        request: FastAPI Request object

    Returns:
        User information dictionary

    Raises:
        HTTPException: If user is not authenticated
    """
    user = get_current_user(request)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    return {
        "id": user["id"],
        "employee_id": user["employee_id"],
        "role": user["role"],
        "created_at": user["created_at"],
        "last_login": user["last_login"]
    }


@router.get("/admin/login")
async def admin_login_page(request: Request, error: Optional[str] = None):
    """Display admin login page (redirects to user login for unified experience).

    Args:
        request: FastAPI Request object
        error: Optional error message parameter

    Returns:
        RedirectResponse to user login page
    """
    return RedirectResponse(url="/auth/login", status_code=302)


@router.post("/admin/login")
async def admin_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    """Process admin login (legacy endpoint, redirects to unified login).

    This endpoint is maintained for backward compatibility.
    New users should use the unified login at /auth/login.

    Args:
        request: FastAPI Request object
        username: Admin username
        password: Admin password

    Returns:
        RedirectResponse to upload page or login page with error
    """
    if verify_admin_credentials(username, password):
        request.session["user"] = username
        request.session["role"] = "admin"
        logger.info(f"Admin logged in: username={username}")
        return RedirectResponse(url="/admin/upload", status_code=302)

    logger.warning(f"Failed admin login attempt: username={username}")
    return RedirectResponse(url="/auth/admin/login?error=invalid", status_code=302)


# Legacy route handlers for backward compatibility
# These map the old routes to the new auth module routes

def register_legacy_routes(app):
    """Register legacy route aliases for backward compatibility.

    Args:
        app: FastAPI application instance
    """
    @app.get("/login", response_class=type(templates) if templates else object)
    async def legacy_login_page(request: Request, error: Optional[str] = None):
        """Legacy login page route - redirects to /auth/login."""
        return await login_page(request, error)

    @app.post("/api/login")
    async def legacy_api_login(
        request: Request,
        employee_id: str = Form(...),
        api_key: str = Form(...)
    ):
        """Legacy API login route - forwards to /auth/login."""
        return await login(request, employee_id, api_key)

    @app.get("/logout")
    async def legacy_logout(request: Request):
        """Legacy logout route - forwards to /auth/logout."""
        return await logout(request)

    @app.get("/api/me")
    async def legacy_api_me(request: Request):
        """Legacy /api/me route - forwards to /auth/me."""
        return await get_me(request)

    @app.get("/admin/login")
    async def legacy_admin_login_page(request: Request, error: Optional[str] = None):
        """Legacy admin login page route - redirects to /auth/login."""
        return await admin_login_page(request, error)

    @app.post("/admin/login")
    async def legacy_admin_login(
        request: Request,
        username: str = Form(...),
        password: str = Form(...)
    ):
        """Legacy admin login route - forwards to /auth/admin/login."""
        return await admin_login(request, username, password)
