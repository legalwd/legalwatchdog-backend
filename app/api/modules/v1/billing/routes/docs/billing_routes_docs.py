# CREATE BILLING ACCOUNT DOCS
create_billing_account_responses = {
    201: {
        "description": "Billing account created successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Billing account created",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 201,
                            "message": "Billing account created",
                            "data": {
                                "id": "3f7be7d0-5c7f-4a52-9f87-7fd970000001",
                                "organization_id": "0c7c9f2b-7a67-4b37-9f42-5ff000000001",
                                "status": "TRIALING",
                                "currency": "USD",
                                "stripe_customer_id": "cus_123456789",
                                "trial_starts_at": "2025-11-30T02:20:18.667467Z",
                                "trial_ends_at": "2025-12-14T02:20:18.667467Z",
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Validation or business rule error",
        "content": {
            "application/json": {
                "examples": {
                    "validation_error": {
                        "summary": "Validation / business rule failure",
                        "value": {
                            "error": "ERROR",
                            "message": "Currency XYZ is not supported",
                            "status_code": 400,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Request validation failed",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_payload": {
                        "summary": "Invalid request payload",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "organization_id": ["value is not a valid uuid"],
                                "currency": ["value is not a valid string"],
                            },
                        },
                    }
                }
            }
        },
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "examples": {
                    "server_error": {
                        "summary": "Failed to create billing account",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to create billing account",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

create_billing_account_custom_errors = ["400", "422", "500"]
create_billing_account_custom_success = {
    "status_code": 201,
    "description": "Billing account created successfully.",
}


# GET BILLING ACCOUNT DOCS
get_billing_account_responses = {
    200: {
        "description": "Billing account retrieved successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Billing account found",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Billing account retrieved",
                            "data": {
                                "id": "3f7be7d0-5c7f-4a52-9f87-7fd970000001",
                                "organization_id": "0c7c9f2b-7a67-4b37-9f42-5ff000000001",
                                "status": "ACTIVE",
                                "currency": "USD",
                                "default_payment_method_id": "e5b2dd4b-9a71-4d4f-9c11-bc4100000001",
                                "stripe_customer_id": "cus_123456789",
                                "stripe_subscription_id": "sub_123456789",
                                "cancel_at_period_end": False,
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Billing account not found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "No billing account for organisation",
                        "value": {
                            "error": "ERROR",
                            "message": "Billing account not found for organisation",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Request validation failed",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_organisation_id": {
                        "summary": "Invalid organisation ID",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "organization_id": ["value is not a valid uuid"],
                            },
                        },
                    }
                }
            }
        },
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "examples": {
                    "server_error": {
                        "summary": "Failed to fetch billing account",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to fetch billing account",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_billing_account_custom_errors = ["404", "422", "500"]
get_billing_account_custom_success = {
    "status_code": 200,
    "description": "Billing account retrieved successfully.",
}

# CREATE CHECKOUT SESSION DOCS
create_checkout_responses = {
    200: {
        "description": "Checkout session created successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Checkout session created",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Checkout session created",
                            "data": {
                                "checkout_url": "https://checkout.stripe.com/c/test_123",
                                "session_id": "cs_test_1234567890",
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Invalid plan or request",
        "content": {
            "application/json": {
                "examples": {
                    "unsupported_plan": {
                        "summary": "Unsupported billing plan",
                        "value": {
                            "error": "ERROR",
                            "message": "Unsupported billing plan",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "invalid_request": {
                        "summary": "Invalid request payload",
                        "value": {
                            "error": "ERROR",
                            "message": "Invalid request",
                            "status_code": 400,
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
                    "validation_error": {
                        "summary": "Request Validation Failed",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "plan": ["Field required"],
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
                    "stripe_customer_error": {
                        "summary": "Failed to create Stripe customer",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to create Stripe customer",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "checkout_error": {
                        "summary": "Checkout session creation failed",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to create checkout session",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "config_error": {
                        "summary": "Billing configuration invalid",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": (
                                "Billing is not correctly configured. Please contact support."
                            ),
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

create_checkout_custom_errors = ["400", "422", "500"]
create_checkout_custom_success = {
    "status_code": 200,
    "description": "Checkout session created successfully.",
}

# GET SUBSCRIPTION STATUS DOCS
subscription_status_responses = {
    200: {
        "description": "Subscription status retrieved successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Subscription active",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Subscription status retrieved",
                            "data": {
                                "billing_account_id": "3f7be7d0-5c7f-4a52-9f87-7fd970000001",
                                "stripe_customer_id": "cus_123456789",
                                "stripe_subscription_id": "sub_123456789",
                                "status": "ACTIVE",
                                "cancel_at_period_end": False,
                                "current_period_start": "2025-01-01T00:00:00Z",
                                "current_period_end": "2025-02-01T00:00:00Z",
                                "next_billing_at": "2025-02-01T00:00:00Z",
                                "current_plan": {
                                    "id": "1a2b3c4d-5e6f-7g8h-9i10-j11k12l13m14",
                                    "code": "ESSENTIAL_YEARLY",
                                    "tier": "ESSENTIAL",
                                    "label": "Essential (Yearly)",
                                    "interval": "year",
                                    "currency": "USD",
                                    "amount": 27840,
                                    "description": "Best for individual consultants & small teams. \
                                        Billed yearly with a 20% discount.",
                                    "features": [
                                        "Up to 1 projects",
                                        "Up to 2 jurisdictions",
                                        "1-day snapshot history",
                                        "20 monthly scans",
                                        "Email summaries",
                                        "AI summaries",
                                    ],
                                    "is_most_popular": False,
                                    "is_active": True,
                                },
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Billing account not found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "No billing account",
                        "value": {
                            "error": "ERROR",
                            "message": "Billing account not found",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Validation Failed",
        "content": {
            "application/json": {
                "examples": {
                    "validation_error": {
                        "summary": "Invalid organisation id",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "organization_id": ["value is not a valid uuid"],
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
                    "server_error": {
                        "summary": "Failed to get subscription status",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to get subscription status",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

subscription_status_custom_errors = ["404", "422", "500"]
subscription_status_custom_success = {
    "status_code": 200,
    "description": "Subscription status retrieved successfully.",
}


# CHANGE SUBSCRIPTION PLAN DOCS
change_subscription_plan_responses = {
    200: {
        "description": "Subscription plan changed successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success_monthly": {
                        "summary": "Changed to monthly plan",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Subscription plan changed to ESSENTIAL_YEARLY",
                            "data": {
                                "billing_account_id": "3f7be7d0-5c7f-4a52-9f87-7fd970000001",
                                "stripe_customer_id": "cus_123456789",
                                "stripe_subscription_id": "sub_123456789",
                                "status": "ACTIVE",
                                "cancel_at_period_end": False,
                                "current_period_start": "2025-01-01T00:00:00Z",
                                "current_period_end": "2025-02-01T00:00:00Z",
                                "next_billing_at": "2025-02-01T00:00:00Z",
                                "current_plan": {
                                    "id": "1a2b3c4d-5e6f-7g8h-9i10-j11k12l13m14",
                                    "code": "ESSENTIAL_YEARLY",
                                    "tier": "ESSENTIAL",
                                    "label": "Essential (Yearly)",
                                    "interval": "year",
                                    "currency": "USD",
                                    "amount": 27840,
                                    "description": "Best for individual consultants & small teams. \
                                        Billed yearly with a 20% discount.",
                                    "features": [
                                        "Up to 1 projects",
                                        "Up to 2 jurisdictions",
                                        "1-day snapshot history",
                                        "20 monthly scans",
                                        "Email summaries",
                                        "AI summaries",
                                    ],
                                    "is_most_popular": False,
                                    "is_active": True,
                                },
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Invalid request or no active subscription",
        "content": {
            "application/json": {
                "examples": {
                    "no_active_subscription": {
                        "summary": "No active subscription",
                        "value": {
                            "error": "ERROR",
                            "message": "No active subscription to change",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "unsupported_plan": {
                        "summary": "Unsupported billing plan",
                        "value": {
                            "error": "ERROR",
                            "message": "Unsupported billing plan",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "validation_error": {
                        "summary": "Invalid request payload",
                        "value": {
                            "error": "ERROR",
                            "message": "Invalid request",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Billing account not found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "No billing account",
                        "value": {
                            "error": "ERROR",
                            "message": "Billing account not found",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Validation Failed",
        "content": {
            "application/json": {
                "examples": {
                    "validation_error": {
                        "summary": "Invalid plan code",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "plan": ["value is not a valid enumeration member"],
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
                    "config_error": {
                        "summary": "Billing configuration invalid",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": (
                                "Billing is not correctly configured. Please contact support."
                            ),
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "server_error": {
                        "summary": "Failed to change subscription plan",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to change subscription plan",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

change_subscription_plan_custom_errors = ["400", "404", "422", "500"]
change_subscription_plan_custom_success = {
    "status_code": 200,
    "description": "Subscription plan changed successfully.",
}


# CANCEL SUBSCRIPTION DOCS
cancel_subscription_responses = {
    200: {
        "description": "Subscription scheduled for cancellation successfully",
        "content": {
            "application/json": {
                "examples": {
                    "cancel_at_period_end": {
                        "summary": "Cancelled immediately",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Subscription set to cancel at period end",
                            "data": {
                                "billing_account_id": "3f7be7d0-5c7f-4a52-9f87-7fd970000001",
                                "stripe_customer_id": "cus_123456789",
                                "stripe_subscription_id": "sub_123456789",
                                "status": "ACTIVE",
                                "cancel_at_period_end": True,
                                "current_period_start": "2025-01-01T00:00:00Z",
                                "current_period_end": "2025-02-01T00:00:00Z",
                                "current_plan": {
                                    "id": "99810fed-ec37-49ac-8818-5b135b409199",
                                    "code": "ESSENTIAL_YEARLY",
                                    "tier": "ESSENTIAL",
                                    "label": "Essential (Yearly)",
                                    "interval": "year",
                                    "currency": "USD",
                                    "amount": 27840,
                                    "description": "Best for individual consultants & small teams. \
                                        Billed yearly with a 20% discount.",
                                    "features": [
                                        "Up to 1 projects",
                                        "Up to 2 jurisdictions",
                                        "1-day snapshot history",
                                        "20 monthly scans",
                                        "Email summaries",
                                        "AI summaries",
                                    ],
                                    "is_most_popular": False,
                                    "is_active": True,
                                },
                            },
                        },
                    },
                }
            }
        },
    },
    400: {
        "description": "Bad Request - No active subscription or invalid request",
        "content": {
            "application/json": {
                "examples": {
                    "no_active_subscription": {
                        "summary": "No active subscription",
                        "value": {
                            "error": "ERROR",
                            "message": "No active subscription to cancel",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "validation_error": {
                        "summary": "Invalid request payload",
                        "value": {
                            "error": "ERROR",
                            "message": "Invalid request",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Billing account not found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "No billing account",
                        "value": {
                            "error": "ERROR",
                            "message": "Billing account not found",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Validation Failed",
        "content": {
            "application/json": {
                "examples": {
                    "validation_error": {
                        "summary": "Invalid cancel_at_period_end flag or organisation id",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "organization_id": ["value is not a valid uuid"],
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
                    "server_error": {
                        "summary": "Failed to cancel subscription",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to cancel subscription",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

cancel_subscription_custom_errors = ["400", "404", "422", "500"]
cancel_subscription_custom_success = {
    "status_code": 200,
    "description": "Subscription cancelled or scheduled for cancellation successfully.",
}


# LIST PAYMENT METHODS DOCS
list_payment_methods_responses = {
    200: {
        "description": "Payment methods retrieved successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Multiple payment methods",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Payment methods retrieved",
                            "data": [
                                {
                                    "id": "e5b2dd4b-9a71-4d4f-9c11-bc4100000001",
                                    "billing_account_id": "3f7be7d0-5c7f-4a52-9f87-7fd970000001",
                                    "stripe_payment_method_id": "pm_1PvABCDEF12345678",
                                    "card_brand": "visa",
                                    "last4": "4242",
                                    "exp_month": 12,
                                    "exp_year": 2030,
                                    "is_default": True,
                                },
                                {
                                    "id": "c7a3e0af-9d3e-4c55-8b97-cc4100000002",
                                    "billing_account_id": "3f7be7d0-5c7f-4a52-9f87-7fd970000001",
                                    "stripe_payment_method_id": "pm_1PvXYZ1234567890",
                                    "card_brand": "mastercard",
                                    "last4": "5100",
                                    "exp_month": 11,
                                    "exp_year": 2029,
                                    "is_default": False,
                                },
                            ],
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Billing account not found",
        "content": {
            "application/json": {
                "examples": {
                    "billing_not_found": {
                        "summary": "No billing account",
                        "value": {
                            "error": "ERROR",
                            "message": "Billing account not found",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Request validation failed",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_organisation_id": {
                        "summary": "Invalid organisation ID",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "organization_id": ["value is not a valid uuid"],
                            },
                        },
                    }
                }
            }
        },
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "examples": {
                    "server_error": {
                        "summary": "Failed to list payment methods",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to list payment methods",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

list_payment_methods_custom_errors = ["404", "422", "500"]
list_payment_methods_custom_success = {
    "status_code": 200,
    "description": "Payment methods retrieved successfully.",
}


# DELETE PAYMENT METHOD DOCS
delete_payment_method_responses = {
    204: {
        "description": "Payment method deleted successfully (no content)",
    },
    404: {
        "description": "Payment method not found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "No such payment method",
                        "value": {
                            "error": "ERROR",
                            "message": "Payment method not found",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Request validation failed",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_ids": {
                        "summary": "Invalid organisation or payment method ID",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "organization_id": ["value is not a valid uuid"],
                                "payment_method_id": ["value is not a valid uuid"],
                            },
                        },
                    }
                }
            }
        },
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "examples": {
                    "server_error": {
                        "summary": "Failed to delete payment method",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to delete payment method",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

delete_payment_method_custom_errors = ["404", "422", "500"]
delete_payment_method_custom_success = {
    "status_code": 204,
    "description": "Payment method deleted successfully.",
}


# LIST INVOICES DOCS
list_invoices_responses = {
    200: {
        "description": "Invoices retrieved successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Invoice list",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Payment history retrieved",
                            "data": [
                                {
                                    "id": "a2b3c4d5-0000-0000-0000-000000000001",
                                    "billing_account_id": "3f7be7d0-5c7f-4a52-9f87-7fd970000001",
                                    "amount_due": 27840,
                                    "amount_paid": 27840,
                                    "currency": "USD",
                                    "status": "PAID",
                                    "stripe_invoice_id": "in_123456789",
                                    "hosted_invoice_url": "https://invoice.stripe.com/i/acct_1SWbBeIwSrzpxfjK/test_YWNjdF8xU1diQmVJd1NyenB4ZmpLLF9UVzJrWmE3TWJ6ZUkyVm50R3VSN2FmdFdMclNiY0ZGLDE1NTAxMTYxNA02007aJx30o9?s=ap",
                                    "invoice_pdf_url": "https://pay.stripe.com/invoice/acct_1SWbBeIwSrzpxfjK/test_YWNjdF8xU1diQmVJd1NyenB4ZmpLLF9UVzJrWmE3TWJ6ZUkyVm50R3VSN2FmdFdMclNiY0ZGLDE1NTAxMTYxNA02007aJx30o9/pdf?s=ap",
                                    "plan_code": "ESSENTIAL_YEARLY",
                                    "plan_interval": "year",
                                    "created_at": "2025-01-01T00:00:00Z",
                                },
                                {
                                    "id": "a2b3c4d5-0000-0000-0000-000000000002",
                                    "billing_account_id": "3f7be7d0-5c7f-4a52-9f87-7fd970000001",
                                    "amount_due": 27840,
                                    "amount_paid": 27840,
                                    "currency": "USD",
                                    "status": "PAID",
                                    "stripe_invoice_id": "in_987654321",
                                    "hosted_invoice_url": "https://invoice.stripe.com/i/acct_1SWbBeIwSrzpxfjK/test_YWNjdF8xU1diQmVJd1NyenB4ZmpLLF9UVzJrWmE3TWJ6ZUkyVm50R3VSN2FmdFdMclNiY0ZGLDE1NTAxMTYxNA02007aJx30o9?s=ap",
                                    "invoice_pdf_url": "https://pay.stripe.com/invoice/acct_1SWbBeIwSrzpxfjK/test_YWNjdF8xU1diQmVJd1NyenB4ZmpLLF9UVzJrWmE3TWJ6ZUkyVm50R3VSN2FmdFdMclNiY0ZGLDE1NTAxMTYxNA02007aJx30o9/pdf?s=ap",
                                    "plan_code": "ESSENTIAL_YEARLY",
                                    "plan_interval": "year",
                                    "created_at": "2025-01-15T00:00:00Z",
                                },
                            ],
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Billing account not found",
        "content": {
            "application/json": {
                "examples": {
                    "billing_not_found": {
                        "summary": "No billing account",
                        "value": {
                            "error": "ERROR",
                            "message": "Billing account not found",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Request validation failed",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_organisation_id": {
                        "summary": "Invalid organisation ID",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "organization_id": ["value is not a valid uuid"],
                            },
                        },
                    }
                }
            }
        },
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "examples": {
                    "server_error": {
                        "summary": "Failed to list invoices",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to list invoices",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

list_invoices_custom_errors = ["404", "422", "500"]
list_invoices_custom_success = {
    "status_code": 200,
    "description": "Invoices retrieved successfully.",
}


# LIST PLANS DOCS
list_plans_responses = {
    200: {
        "description": "Subscription plans retrieved successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Available plans",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Plans retrieved",
                            "data": [
                                {
                                    "id": "00000000-0000-0000-0000-000000000001",
                                    "code": "ESSENTIAL_MONTHLY",
                                    "tier": "ESSENTIAL",
                                    "label": "Essential",
                                    "interval": "month",
                                    "currency": "USD",
                                    "amount": 2900,
                                    "description": "Best for individual consultants & small teams.",
                                    "features": [
                                        "Up to 1 projects",
                                        "Up to 2 jurisdictions",
                                        "1-day snapshot history",
                                        "20 monthly scans",
                                        "Email summaries",
                                        "AI summaries",
                                    ],
                                    "is_most_popular": False,
                                    "is_active": True,
                                },
                                {
                                    "id": "00000000-0000-0000-0000-000000000002",
                                    "code": "PRO_MONTHLY",
                                    "tier": "PROFESSIONAL",
                                    "label": "Professional",
                                    "interval": "month",
                                    "currency": "USD",
                                    "amount": 10000,
                                    "description": "Designed for growing legal & compliance teams.",
                                    "features": [
                                        "Up to 20 projects",
                                        "Up to 50 jurisdictions",
                                        "Unlimited scans",
                                        "Priority AI summaries",
                                        "Team notifications",
                                        "API access",
                                        "1-year snapshot history",
                                    ],
                                    "is_most_popular": True,
                                    "is_active": True,
                                },
                                {
                                    "id": "00000000-0000-0000-0000-000000000003",
                                    "code": "ENTERPRISE_MONTHLY",
                                    "tier": "ENTERPRISE",
                                    "label": "Enterprise",
                                    "interval": "month",
                                    "currency": "USD",
                                    "amount": 29900,
                                    "description": "For large organizations \
                                        with complex regulatory needs.",
                                    "features": [
                                        "Unlimited projects and jurisdictions",
                                        "Dedicated CSM",
                                        "Custom AI configuration",
                                        "SSO & advanced roles",
                                        "Unlimited snapshot history",
                                        "Full audit logs",
                                    ],
                                    "is_most_popular": False,
                                    "is_active": True,
                                },
                            ],
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Request validation failed",
        "content": {
            "application/json": {
                "examples": {
                    "validation_error": {
                        "summary": "Validation failed",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "body": ["Request payload is invalid"],
                            },
                        },
                    }
                }
            }
        },
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "examples": {
                    "server_error": {
                        "summary": "Failed to list plans",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to list billing plans",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

list_plans_custom_errors = ["422", "500"]
list_plans_custom_success = {
    "status_code": 200,
    "description": "Subscription plans retrieved successfully.",
}
