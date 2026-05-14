get_user_profile_responses = {
    200: {
        "description": "User Profile Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success_oauth": {
                        "summary": "User Profile with Google OAuth",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "User profile retrieved successfully",
                            "data": {
                                "user": {
                                    "id": "123e4567-e89b-12d3-a456-426614174000",
                                    "email": "john.doe@gmail.com",
                                    "name": "John Doe",
                                    "auth_provider": "google",
                                    "profile_picture_url": "https://lh3.googleusercontent.com/a/photo.jpg",
                                    "provider_user_id": "107563041634719123456",
                                    "provider_profile_data": {
                                        "name": "John Doe",
                                        "picture": "https://lh3.googleusercontent.com/a/photo.jpg",
                                        "email_verified": True,
                                        "locale": "en",
                                    },
                                    "is_verified": True,
                                    "is_active": True,
                                    "is_superadmin": False,
                                    "created_at": "2024-01-15T10:30:00Z",
                                    "updated_at": "2024-01-15T10:30:00Z",
                                },
                                "organizations": [
                                    {
                                        "organization_id": "456e7890-e89b-12d3-a456-426614174001",
                                        "name": "Acme Corporation",
                                        "industry": "Technology",
                                        "is_active": True,
                                        "membership_active": True,
                                        "role": {
                                            "id": "789f1234-e89b-12d3-a456-426614174002",
                                            "name": "Admin",
                                            "permissions": {"manage_organization": True},
                                        },
                                        "joined_at": "2024-01-15T10:30:00Z",
                                    }
                                ],
                                "statistics": {
                                    "total_organizations": 1,
                                    "active_memberships": 1,
                                    "admin_roles": 1,
                                },
                            },
                        },
                    },
                    "success_local": {
                        "summary": "User Profile with Email/Password Auth",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "User profile retrieved successfully",
                            "data": {
                                "user": {
                                    "id": "987e6543-e21b-34d5-a678-426614174999",
                                    "email": "jane.smith@company.com",
                                    "name": "Jane Smith",
                                    "auth_provider": "local",
                                    "profile_picture_url": "https://minio.example.com/profiles/avatar.jpg",
                                    "provider_user_id": None,
                                    "provider_profile_data": None,
                                    "is_verified": True,
                                    "is_active": True,
                                    "is_superadmin": False,
                                    "created_at": "2024-02-01T08:00:00Z",
                                    "updated_at": "2024-02-15T14:30:00Z",
                                },
                                "organizations": [
                                    {
                                        "organization_id": "abc12345-e89b-12d3-a456-426614174abc",
                                        "name": "Legal Partners LLP",
                                        "industry": "Legal Services",
                                        "is_active": True,
                                        "membership_active": True,
                                        "role": {
                                            "id": "def67890-e89b-12d3-a456-426614174def",
                                            "name": "Member",
                                            "permissions": {"view_documents": True},
                                        },
                                        "joined_at": "2024-02-01T08:00:00Z",
                                    },
                                    {
                                        "organization_id": "ghi11111-e89b-12d3-a456-426614174ghi",
                                        "name": "Consulting Group Inc",
                                        "industry": "Consulting",
                                        "is_active": True,
                                        "membership_active": True,
                                        "role": {
                                            "id": "jkl22222-e89b-12d3-a456-426614174jkl",
                                            "name": "Admin",
                                            "permissions": {"manage_organization": True},
                                        },
                                        "joined_at": "2024-03-10T11:00:00Z",
                                    },
                                ],
                                "statistics": {
                                    "total_organizations": 2,
                                    "active_memberships": 2,
                                    "admin_roles": 1,
                                },
                            },
                        },
                    },
                    "success_no_orgs": {
                        "summary": "New User with No Organizations",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "User profile retrieved successfully",
                            "data": {
                                "user": {
                                    "id": "new12345-e89b-12d3-a456-426614174new",
                                    "email": "newuser@example.com",
                                    "name": "New User",
                                    "auth_provider": "local",
                                    "profile_picture_url": None,
                                    "provider_user_id": None,
                                    "provider_profile_data": None,
                                    "is_verified": True,
                                    "is_active": True,
                                    "is_superadmin": False,
                                    "created_at": "2024-06-01T12:00:00Z",
                                    "updated_at": "2024-06-01T12:00:00Z",
                                },
                                "organizations": [],
                                "statistics": {
                                    "total_organizations": 0,
                                    "active_memberships": 0,
                                    "admin_roles": 0,
                                },
                            },
                        },
                    },
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Authentication Required",
        "content": {
            "application/json": {
                "examples": {
                    "not_authenticated": {
                        "summary": "User Not Authenticated",
                        "value": {
                            "error_code": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Not Found - Profile Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "profile_not_found": {
                        "summary": "Profile Not Found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "Your profile could not be found. Please log in again.",
                            "status_code": 404,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "examples": {
                    "processing_error": {
                        "summary": "Processing Error",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "We're unable to load your profile at this time. \
                                 Please refresh the page or try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "internal_server_error": {
                        "summary": "Internal Server Error",
                        "value": {
                            "error_code": "INTERNAL_SERVER_ERROR",
                            "message": "An unexpected error occurred. Please try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_user_profile_custom_errors = ["401", "404", "500"]
get_user_profile_custom_success = {
    "status_code": 200,
    "description": "User profile retrieved successfully with all organization memberships.",
}

update_user_profile_responses = {
    200: {
        "description": "Profile Updated Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success_full_update": {
                        "summary": "Full Profile Update",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Profile updated successfully",
                            "data": {
                                "id": "123e4567-e89b-12d3-a456-426614174000",
                                "email": "user@example.com",
                                "name": "John Updated",
                                "avatar_url": "https://example.com/new-avatar.png",
                                "is_active": True,
                                "is_verified": True,
                                "created_at": "2024-01-15T10:30:00Z",
                                "updated_at": "2024-01-16T12:00:00Z",
                            },
                        },
                    },
                    "success_name_only": {
                        "summary": "Name Only Update",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Profile updated successfully",
                            "data": {
                                "id": "123e4567-e89b-12d3-a456-426614174000",
                                "email": "user@example.com",
                                "name": "Jane Smith-Johnson",
                                "avatar_url": None,
                                "is_active": True,
                                "is_verified": True,
                                "created_at": "2024-01-15T10:30:00Z",
                                "updated_at": "2024-01-17T09:45:00Z",
                            },
                        },
                    },
                    "success_avatar_only": {
                        "summary": "Avatar Only Update",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Profile updated successfully",
                            "data": {
                                "id": "123e4567-e89b-12d3-a456-426614174000",
                                "email": "user@example.com",
                                "name": "John Doe",
                                "avatar_url": "https://cdn.example.com/avatars/professional.jpg",
                                "is_active": True,
                                "is_verified": True,
                                "created_at": "2024-01-15T10:30:00Z",
                                "updated_at": "2024-01-18T15:20:00Z",
                            },
                        },
                    },
                }
            }
        },
    },
    400: {
        "description": "Bad Request - No Fields to Update",
        "content": {
            "application/json": {
                "examples": {
                    "no_fields": {
                        "summary": "No Fields Provided",
                        "value": {
                            "error_code": "NO_FIELDS_TO_UPDATE",
                            "message": "No fields to update",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Authentication Required",
        "content": {
            "application/json": {
                "examples": {
                    "not_authenticated": {
                        "summary": "User Not Authenticated",
                        "value": {
                            "error_code": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Not Found - User Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "User Not Found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "The user account you're trying to update doesn't exist.",
                            "status_code": 404,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "examples": {
                    "processing_error": {
                        "summary": "Processing Error",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Failed to update profile",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "internal_server_error": {
                        "summary": "Internal Server Error",
                        "value": {
                            "error_code": "INTERNAL_SERVER_ERROR",
                            "message": "An unexpected error occurred. Please try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

update_user_profile_custom_errors = ["400", "401", "404", "500"]
update_user_profile_custom_success = {
    "status_code": 200,
    "description": "User profile fields updated successfully.",
}

upload_profile_picture_responses = {
    200: {
        "description": "Profile Picture Uploaded Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Picture Uploaded",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Profile picture uploaded successfully",
                            "data": {
                                "profile_picture_url": "https://minio.example.com/bucket/path/to/image.jpg"
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Validation Failed",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_type": {
                        "summary": "Invalid File Type",
                        "value": {
                            "error_code": "INVALID_FILE_TYPE",
                            "message": "Invalid file type. Only JPEG, PNG, GIF & WebP images \
                                 are allowed.",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "file_too_large": {
                        "summary": "File Too Large",
                        "value": {
                            "error_code": "FILE_TOO_LARGE",
                            "message": "File too large. Maximum size is 5MB.",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Authentication Required",
        "content": {
            "application/json": {
                "examples": {
                    "not_authenticated": {
                        "summary": "User Not Authenticated",
                        "value": {
                            "error_code": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Not Found - User Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "User Not Found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "The user account you're trying to update doesn't exist.",
                            "status_code": 404,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "examples": {
                    "processing_error": {
                        "summary": "Processing Error",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Failed to upload profile picture",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "internal_server_error": {
                        "summary": "Internal Server Error",
                        "value": {
                            "error_code": "INTERNAL_SERVER_ERROR",
                            "message": "An unexpected error occurred. Please try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

upload_profile_picture_custom_errors = ["400", "401", "404", "500"]
upload_profile_picture_custom_success = {
    "status_code": 200,
    "description": "Profile picture uploaded and URL updated successfully.",
}

get_user_organizations_responses = {
    200: {
        "description": "User Organizations Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "User Organizations List",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Organizations retrieved successfully",
                            "data": {
                                "items": [
                                    {
                                        "organization_id": "123e4567-e89b-12d3-a456-426614174000",
                                        "name": "Acme Corporation",
                                        "industry": "Technology",
                                        "is_active": True,
                                        "user_role": "Admin",
                                        "created_at": "2024-01-15T10:30:00Z",
                                        "updated_at": "2024-01-15T10:30:00Z",
                                    },
                                    {
                                        "organization_id": "456e7890-e89b-12d3-a456-426614174001",
                                        "name": "Tech Innovations Ltd",
                                        "industry": "Software Development",
                                        "is_active": True,
                                        "user_role": "Member",
                                        "created_at": "2024-02-01T09:15:00Z",
                                        "updated_at": "2024-02-01T09:15:00Z",
                                    },
                                ],
                                "pagination": {
                                    "total": 2,
                                    "page": 1,
                                    "limit": 10,
                                    "pages": 1,
                                },
                            },
                        },
                    },
                    "success_empty": {
                        "summary": "User Has No Organizations",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Organizations retrieved successfully",
                            "data": {
                                "items": [],
                                "pagination": {
                                    "total": 0,
                                    "page": 1,
                                    "limit": 10,
                                    "pages": 0,
                                },
                            },
                        },
                    },
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Authentication Required",
        "content": {
            "application/json": {
                "examples": {
                    "not_authenticated": {
                        "summary": "User Not Authenticated",
                        "value": {
                            "error_code": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Access Denied",
        "content": {
            "application/json": {
                "examples": {
                    "cannot_view_other_users": {
                        "summary": "Cannot View Other User's Organizations",
                        "value": {
                            "error_code": "PERMISSION_DENIED",
                            "message": "You can only view your own organizations",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Validation Failed",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_uuid": {
                        "summary": "Invalid User ID Format",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "user_id": ["Invalid UUID format"],
                            },
                        },
                    },
                }
            }
        },
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "examples": {
                    "processing_error": {
                        "summary": "Processing Error",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Failed to retrieve organizations",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "internal_server_error": {
                        "summary": "Internal Server Error",
                        "value": {
                            "error_code": "INTERNAL_SERVER_ERROR",
                            "message": "An unexpected error occurred. Please try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_user_organizations_custom_errors = ["401", "403", "422", "500"]
get_user_organizations_custom_success = {
    "status_code": 200,
    "description": "User organizations retrieved successfully with role information.",
}

get_my_invitations_responses = {
    200: {
        "description": "Pending Invitations Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Multiple Pending Invitations",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Pending invitations retrieved successfully",
                            "data": {
                                "items": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174000",
                                        "organization_id": "456e7890-e89b-12d3-a456-426614174001",
                                        "organization_name": "Acme Corporation",
                                        "invited_email": "user@example.com",
                                        "role_id": "789f1234-e89b-12d3-a456-426614174002",
                                        "role_name": "Member",
                                        "status": "pending",
                                        "invited_by": "admin@acme.com",
                                        "expires_at": "2024-02-15T10:30:00Z",
                                        "created_at": "2024-01-15T10:30:00Z",
                                        "updated_at": "2024-01-15T10:30:00Z",
                                    },
                                    {
                                        "id": "abc12345-e89b-12d3-a456-426614174abc",
                                        "organization_id": "def67890-e89b-12d3-a456-426614174def",
                                        "organization_name": "Legal Partners LLP",
                                        "invited_email": "user@example.com",
                                        "role_id": "ghi11111-e89b-12d3-a456-426614174ghi",
                                        "role_name": "Admin",
                                        "status": "pending",
                                        "invited_by": "partner@legalpartners.com",
                                        "expires_at": "2024-02-20T14:00:00Z",
                                        "created_at": "2024-01-20T14:00:00Z",
                                        "updated_at": "2024-01-20T14:00:00Z",
                                    },
                                ],
                                "pagination": {
                                    "total": 2,
                                    "page": 1,
                                    "limit": 20,
                                    "pages": 1,
                                },
                            },
                        },
                    },
                    "success_single": {
                        "summary": "Single Pending Invitation",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Pending invitations retrieved successfully",
                            "data": {
                                "items": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174000",
                                        "organization_id": "456e7890-e89b-12d3-a456-426614174001",
                                        "organization_name": "Tech Startup Inc",
                                        "invited_email": "developer@example.com",
                                        "role_id": "789f1234-e89b-12d3-a456-426614174002",
                                        "role_name": "Developer",
                                        "status": "pending",
                                        "invited_by": "cto@techstartup.com",
                                        "expires_at": "2024-02-10T16:00:00Z",
                                        "created_at": "2024-01-10T16:00:00Z",
                                        "updated_at": "2024-01-10T16:00:00Z",
                                    }
                                ],
                                "pagination": {
                                    "total": 1,
                                    "page": 1,
                                    "limit": 20,
                                    "pages": 1,
                                },
                            },
                        },
                    },
                    "success_empty": {
                        "summary": "No Pending Invitations",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Pending invitations retrieved successfully",
                            "data": {
                                "items": [],
                                "pagination": {
                                    "total": 0,
                                    "page": 1,
                                    "limit": 20,
                                    "pages": 0,
                                },
                            },
                        },
                    },
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Authentication Required",
        "content": {
            "application/json": {
                "examples": {
                    "not_authenticated": {
                        "summary": "User Not Authenticated",
                        "value": {
                            "error_code": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "examples": {
                    "processing_error": {
                        "summary": "Processing Error",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Failed to retrieve pending invitations",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "internal_server_error": {
                        "summary": "Internal Server Error",
                        "value": {
                            "error_code": "INTERNAL_SERVER_ERROR",
                            "message": "An unexpected error occurred. Please try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_my_invitations_custom_errors = ["401", "500"]
get_my_invitations_custom_success = {
    "status_code": 200,
    "description": "Pending organization invitations for the current user.",
}

get_user_organization_details_responses = {
    200: {
        "description": "Organization Details Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success_admin": {
                        "summary": "Organization Details - Admin Role",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Organization details retrieved successfully",
                            "data": {
                                "organization": {
                                    "id": "456e7890-e89b-12d3-a456-426614174001",
                                    "name": "Acme Corporation",
                                    "industry": "Technology",
                                    "website": "https://acme.example.com",
                                    "description": "Leading provider of innovative solutions",
                                    "is_active": True,
                                    "created_at": "2024-01-01T00:00:00Z",
                                    "updated_at": "2024-01-15T10:30:00Z",
                                },
                                "membership": {
                                    "joined_at": "2024-01-15T10:30:00Z",
                                    "is_active": True,
                                },
                                "role": {
                                    "id": "789f1234-e89b-12d3-a456-426614174002",
                                    "name": "Admin",
                                    "permissions": {
                                        "manage_organization": True,
                                        "manage_members": True,
                                        "manage_roles": True,
                                        "view_billing": True,
                                    },
                                },
                                "billing": {
                                    "plan": "Professional",
                                    "status": "active",
                                    "next_billing_date": "2024-02-01T00:00:00Z",
                                },
                            },
                        },
                    },
                    "success_member": {
                        "summary": "Organization Details - Member Role",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Organization details retrieved successfully",
                            "data": {
                                "organization": {
                                    "id": "abc12345-e89b-12d3-a456-426614174abc",
                                    "name": "Legal Partners LLP",
                                    "industry": "Legal Services",
                                    "website": "https://legalpartners.example.com",
                                    "description": "Full-service law firm",
                                    "is_active": True,
                                    "created_at": "2023-06-15T00:00:00Z",
                                    "updated_at": "2024-01-10T09:00:00Z",
                                },
                                "membership": {
                                    "joined_at": "2024-02-01T08:00:00Z",
                                    "is_active": True,
                                },
                                "role": {
                                    "id": "def67890-e89b-12d3-a456-426614174def",
                                    "name": "Member",
                                    "permissions": {
                                        "view_documents": True,
                                        "create_documents": True,
                                        "manage_organization": False,
                                    },
                                },
                            },
                        },
                    },
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Authentication Required",
        "content": {
            "application/json": {
                "examples": {
                    "not_authenticated": {
                        "summary": "User Not Authenticated",
                        "value": {
                            "error_code": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Access Denied",
        "content": {
            "application/json": {
                "examples": {
                    "cannot_view_other_users": {
                        "summary": "Cannot View Other User's Organization Details",
                        "value": {
                            "error_code": "PERMISSION_DENIED",
                            "message": "You can only view your own organization details",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Organization or Membership Not Found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "Organization details could not be found.",
                            "status_code": 404,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "examples": {
                    "processing_error": {
                        "summary": "Processing Error",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Failed to retrieve organization details",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "internal_server_error": {
                        "summary": "Internal Server Error",
                        "value": {
                            "error_code": "INTERNAL_SERVER_ERROR",
                            "message": "An unexpected error occurred. Please try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_user_organization_details_custom_errors = ["401", "403", "404", "500"]
get_user_organization_details_custom_success = {
    "status_code": 200,
    "description": "Detailed organization membership information for a specific user.",
}
